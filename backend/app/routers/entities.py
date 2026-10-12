from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import (
    AUTH_ERRORS,
    VISIBLE_TO_DOC,
    Ok,
    Visibility,
    default_visibility,
    error_responses,
    vis_field,
)
from ..db import get_db
from ..deps import editor, viewer
from ..i18n import ctr, tr
from ..models import (
    Attachment,
    BoardCard,
    CampaignMember,
    Clock,
    ContentBlock,
    Entity,
    EntityLink,
    MapMarker,
    MapNode,
    Message,
    News,
    now,
    uid,
)
from ..schema_defs import KINDS, MULTI, REF, STANCES, initial_status
from ..visibility import (
    HIDEABLE,
    NEVER_HIDDEN,
    SCOPES,
    Viewer,
    apply_scope,
    can_see,
    entity_editable,
    hidden_keys,
    public_entity,
    strip_gm_fields,
)
from .files import drop_files

router = APIRouter(prefix="/api/campaigns/{campaign_id}", responses=AUTH_ERRORS)

PLAYER_SCOPES = ("owner", "selected", "crew")
ALIAS_KINDS = ("character", "npc")
LABEL_LEN = 120
AFFILIATION_MAX = 24  # фракций/мест на сущность
HIDDEN_MAX = 40  # закрытых полей на карточку

Kind = Literal["character", "npc", "faction", "ship", "location", "job", "item"]
BlockType = Literal["text", "image", "attachment", "quote", "rumor", "secret", "warning", "map note"]
BlockParent = Literal["entity", "clock", "marker", "map"]

FIELDS_DOC = (
    "Per-kind data: keys and allowed values are defined by `GET /api/meta` → `kinds[kind].fields` "
    "(`select` = one of `options`, `multi` = list of options, `ref` = id of an entity of `kinds`). "
    "Keys starting with `gm_` are never shown to players."
)
OWNER_DOC = (
    "Member id of the owner (the player who may edit the card), `\"*\"` = any player may edit, "
    "`null` = GM only. GM sets it; a player's own card gets the player automatically."
)
HIDDEN_DOC = (
    "Card columns (`summary`, `image_url`, `faction_ids`, `location_ids`) and `fields` keys hidden "
    "from players: they see \"unknown\" instead. GM only. New cards start with the kind's `secret` fields hidden."
)
STATUS_DOC = "One of `kinds[kind].statuses` from `GET /api/meta`; omitted or unknown → the kind's first status (factions and locations have none)."


class EntityIn(BaseModel):
    kind: Kind = Field(description="What the record is; decides its `fields` and `statuses` (see `GET /api/meta`).", examples=["npc"])
    name: str = Field(examples=["Gregor Varg"])
    alias: str = Field(default="", description="Nickname or handle; kept only for `character` and `npc`.")
    summary: str = Field(default="", description="One paragraph the table may read (unless hidden).")
    image_url: str = Field(default="", description="Portrait URL, usually `/api/campaigns/{id}/files/{attachment_id}`; image jobs set it on pick.")
    status: str = Field(default="", description=STATUS_DOC)
    faction_ids: list[str] = Field(default=[], description="Ids of `faction` entities this record belongs to (unknown ids are dropped).")
    location_ids: list[str] = Field(default=[], description="Ids of `location` entities where it is found (unknown ids are dropped).")
    fields: dict = Field(default={}, description=FIELDS_DOC, examples=[{"rank": "2", "gm_appearance": "scar over the left eye"}])
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)
    owner_member_id: str | None = Field(default=None, description=OWNER_DOC)
    hidden_fields: list[str] = Field(default=[], description=HIDDEN_DOC)


class EntityPatch(BaseModel):
    """Only the keys sent are changed."""

    name: str | None = None
    alias: str | None = None
    summary: str | None = None
    image_url: str | None = None
    status: str | None = Field(default=None, description=STATUS_DOC)
    faction_ids: list[str] | None = None
    location_ids: list[str] | None = None
    fields: dict | None = Field(default=None, description="Merged key by key into the stored `fields`; a `null` value removes the key. " + FIELDS_DOC)
    visibility: Visibility | None = Field(default=None, description="Players may not set `gm`.")
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)
    owner_member_id: str | None = Field(default=None, description=OWNER_DOC + " GM only.")
    archived: bool | None = Field(default=None, description="`false` restores an archived record.")
    hidden_fields: list[str] | None = Field(default=None, description=HIDDEN_DOC)


class EntityOut(BaseModel):
    """A record as this viewer sees it: hidden columns come back blank, `gm_*` keys are stripped for players."""

    id: str
    kind: str = Field(description="One of `GET /meta` → `kinds`; archived legacy cards may carry an older kind.")
    name: str
    alias: str
    summary: str
    image_url: str
    status: str
    faction_ids: list[str]
    location_ids: list[str]
    fields: dict = Field(description=FIELDS_DOC)
    owner_member_id: str | None = Field(description=OWNER_DOC)
    archived: bool
    created_at: datetime
    updated_at: datetime
    peer_names: dict[str, str] | None = Field(default=None, description="Names of linked entities (`faction_ids`, `location_ids`, `ref` fields) by id — readable even when the linked card itself is closed to the viewer.")
    hidden_fields: list[str] = Field(description="Keys hidden from players; a player sees them listed so it can show \"unknown\".")
    visibility: Visibility | None = Field(default=None, description="Present only when the viewer may edit the card (GM, owner).")
    visible_to: list[str] | None = Field(default=None, description="Present only when the viewer may edit the card.")


class OkDiscard(Ok):
    discarded: bool | None = Field(default=None, description="With `?discard=1`: `true` if the empty card was deleted, `false` if it had content and was left as is.")


def normalize_affiliation(db: Session, v: Viewer, raw, kind: str, keep=()) -> list[str]:
    """Дедуп + проверка, что каждый id — видимая сущность нужного типа в этой кампании.
    `keep` — то, что уже стоит на карточке: игрок его не видит, но и снять не должен."""
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        if not isinstance(item, str) or item in seen or not UUID_RE.fullmatch(item):
            continue
        seen.add(item)
        if len(out) >= AFFILIATION_MAX:
            break
        peer = db.get(Entity, item)
        if (peer and peer.campaign_id == v.campaign_id and peer.kind == kind
                and (item in keep or can_see(peer, v))):
            out.append(item)
    return out


def visible_refs(db: Session, v: Viewer, kind: str, fields: dict, before: dict | None = None) -> dict:
    """Ссылка от игрока — только на видимую ему карточку: иначе по id он узнаёт имя закрытой."""
    if v.is_gm:
        return fields
    out = dict(fields)
    for f in KINDS.get(kind, {}).get("fields", []):
        val = out.get(f["key"])
        if f["type"] != REF or not val or val == (before or {}).get(f["key"]):
            continue
        peer = db.get(Entity, val) if isinstance(val, str) and UUID_RE.fullmatch(val) else None
        if not peer or peer.campaign_id != v.campaign_id or not can_see(peer, v):
            out.pop(f["key"])
    return out


def normalize_hidden(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        key = str(item).strip()
        if key and key not in out and key not in NEVER_HIDDEN and len(key) <= 64:
            out.append(key)
        if len(out) >= HIDDEN_MAX:
            break
    return out


def normalize_fields(kind: str, fields: dict) -> dict:
    """Поле-множество — список строк без повторов, не длиннее max из описания поля.
    Старое значение-строку не трогаем: фронт читает его списком из одного."""
    out = dict(fields)
    for fd in KINDS.get(kind, {}).get("fields", []):
        val = out.get(fd["key"])
        if fd.get("type") != MULTI or not isinstance(val, list):
            continue
        picked: list[str] = []
        for item in val:
            item = str(item).strip()
            if item and item not in picked:
                picked.append(item)
        out[fd["key"]] = picked[: fd["max"]] if fd.get("max") else picked
    return out


def writable(v: Viewer) -> bool:
    """Наблюдатель не пишет; ГМ «глазами игрока» пишет в правах этого игрока."""
    return v.role in ("gm", "player")


def get_visible_entity(db: Session, v: Viewer, entity_id: str) -> Entity:
    e = db.get(Entity, entity_id)
    if not e or e.campaign_id != v.campaign_id or not can_see(e, v):
        raise HTTPException(404, tr("entities.not_found"))
    return e


# к чему привязаны записи, заметки и вложения: скрытый от зрителя родитель прячет и их
PARENTS = {"entity": Entity, "clock": Clock, "marker": MapMarker, "map": MapNode}


def parent_visible(db: Session, v: Viewer, kind: str, parent_id: str) -> bool:
    model = PARENTS.get(kind)
    if model is None:
        return True
    row = db.get(model, parent_id)
    if not row or row.campaign_id != v.campaign_id or not can_see(row, v):
        return False
    return kind != "marker" or parent_visible(db, v, "map", row.map_id)


AFFILIATION_KEYS = ("faction_ids", "location_ids")


UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def ref_keys(e) -> list[str]:
    return [f["key"] for f in KINDS.get(e.kind, {}).get("fields", []) if f["type"] == REF]


def ref_ids(e) -> list[str]:
    defs = KINDS.get(e.kind, {}).get("fields", [])
    vals = [(e.fields or {}).get(f["key"]) for f in defs if f["type"] == REF]
    return [v for v in vals if isinstance(v, str) and UUID_RE.fullmatch(v)]


def peer_names(db: Session, campaign_id: str, rows) -> dict[str, str]:
    """Имена привязанных карточек одним запросом: связь читается и тогда,
    когда сама карточка закрыта от стола."""
    ids: set[str] = set()
    for e in rows:
        for key in AFFILIATION_KEYS:
            ids.update(x for x in (getattr(e, key, None) or []) if isinstance(x, str))
        ids.update(ref_ids(e))
    if not ids:
        return {}
    found = db.query(Entity.id, Entity.name, Entity.alias).filter(
        Entity.campaign_id == campaign_id, Entity.id.in_(ids)).all()
    return {eid: name or (f"«{alias}»" if alias else "") for eid, name, alias in found}


def member_names(db: Session, campaign_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in db.query(CampaignMember).filter_by(campaign_id=campaign_id).all():
        name = (m.display_name or "").strip()
        if not name and m.user is not None:
            name = (m.user.display_name or m.user.login or "").strip()
        out[m.id] = name
    return out


@router.get("/entities", summary="List records", tags=["entities"], response_model=list[EntityOut])
def list_entities(
    v: Viewer = Depends(viewer),
    db: Session = Depends(get_db),
    kind: str | None = Query(default=None, description="One kind or several comma-separated: `npc,faction`."),
    status: str | None = Query(default=None, description="Exact status value."),
    q: str | None = Query(default=None, description="Case-insensitive substring of name, alias or summary — the way to find an id by name."),
    archived: bool = Query(default=False, description="`true` lists archived records instead of live ones."),
    order: str | None = Query(default=None, description="`recent` = newest first; default = by kind, then name."),
    limit: int = Query(500, le=2000),
):
    """Records visible to the viewer. Players get only what is open to them, with hidden
    columns blanked and `gm_*` field keys stripped. No offset: narrow with `kind`, `q` or `status`."""
    query = db.query(Entity).filter(Entity.campaign_id == v.campaign_id,
                                    Entity.archived == archived)
    if kind:
        query = query.filter(Entity.kind.in_(kind.split(",")))
    if status:
        query = query.filter(Entity.status == status)
    if q:
        like = f"%{q}%"
        by_summary = Entity.summary.ilike(like)
        if not v.is_gm:
            by_summary = by_summary & ~Entity.hidden_fields.contains(["summary"])
        query = query.filter(or_(Entity.name.ilike(like), Entity.alias.ilike(like), by_summary))
    query = apply_scope(query, Entity, v)
    order_by = ((Entity.created_at.desc(), Entity.id) if order == "recent"
                else (Entity.kind, Entity.name))
    rows = query.order_by(*order_by).limit(limit).all()
    peers = peer_names(db, v.campaign_id, rows)
    return [public_entity(e, v, peers) for e in rows]


@router.post("/entities", summary="Create a record", tags=["entities"], response_model=EntityOut,
             responses=error_responses(400, 403))
def create_entity(body: EntityIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Create a record of any kind. A GM's record is `gm`-only unless `visibility` is sent;
    a player's record is `crew` and owned by that player. `status` defaults to the kind's first
    status; `fields` are checked against the kind (multi-selects deduplicated and capped);
    `secret` fields of the kind start hidden. Writes a journal entry. Returns the record as the
    caller sees it. 400: unknown kind. 403: a player asked for `gm` visibility."""
    if body.kind not in KINDS:
        raise HTTPException(400, tr("entities.unknown_kind", kind=body.kind))
    if not v.is_gm and body.visibility in ("gm",):
        raise HTTPException(403, tr("entities.player_no_gm_vis"))
    data = body.model_dump()
    # карточка ГМа заводится закрытой: стол увидит её, когда ГМ сам откроет.
    # Явно присланная видимость сильнее умолчания — форма и скиллы её шлют
    data["visibility"] = default_visibility(v, body.visibility)
    # прозвище живёт у людей стола — своих и чужих; у прочих типов роль читается из описания
    if body.kind not in ALIAS_KINDS:
        data["alias"] = ""
    if not data["status"] or not KINDS[body.kind].get("statuses"):
        data["status"] = initial_status(body.kind)
    data["faction_ids"] = normalize_affiliation(db, v, data.get("faction_ids"), "faction")
    data["location_ids"] = normalize_affiliation(db, v, data.get("location_ids"), "location")
    data["fields"] = normalize_fields(body.kind, visible_refs(db, v, body.kind, data.get("fields") or {}))
    data["hidden_fields"] = normalize_hidden(data.get("hidden_fields")) or [
        f["key"] for f in KINDS[body.kind].get("fields", []) if f.get("secret")
    ]
    if not v.is_gm:
        # автор карточки — её владелец, иначе сам не сможет её потом править
        data["owner_member_id"] = v.member_id
        # что закрыто от стола — решает только ГМ
        data["hidden_fields"] = []
    e = Entity(campaign_id=v.campaign_id, **data)
    db.add(e)
    db.flush()
    journal.log(db, v, "entity", "create", target_id=e.id, title=e.name,
                entity_id=e.id, detail=e.kind, visibility=e.visibility)
    db.commit()
    return public_entity(e, v, peer_names(db, v.campaign_id, [e]))


@router.get("/entities/{entity_id}", summary="Get a record", tags=["entities"], response_model=EntityOut)
def get_entity(entity_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """One record as the viewer sees it. 404 also when the record exists but is closed to the viewer."""
    e = get_visible_entity(db, v, entity_id)
    return public_entity(e, v, peer_names(db, v.campaign_id, [e]))


@router.patch("/entities/{entity_id}", summary="Update a record", tags=["entities"], response_model=EntityOut,
              responses=error_responses(403))
def patch_entity(
    entity_id: str, body: EntityPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Change only the keys sent. `fields` merges into the stored dict (`null` removes a key), so
    send just the changed keys. GM edits anything; a player edits own cards (`owner_member_id` =
    their member id or `"*"`, any `ship`) and may not touch `owner_member_id`, `hidden_fields`,
    hidden columns or set `gm`. Writes a journal entry when something changed."""
    e = get_visible_entity(db, v, entity_id)
    patch = body.model_dump(exclude_unset=True)
    hidden = hidden_keys(e)
    if not v.is_gm:
        if not entity_editable(e, v):
            raise HTTPException(403, tr("entities.edit_denied"))
        if patch.get("visibility") == "gm":
            raise HTTPException(403, tr("entities.player_no_gm_vis"))
        if "owner_member_id" in patch:
            raise HTTPException(403, tr("entities.owner_gm_only"))
        if "hidden_fields" in patch:
            raise HTTPException(403, tr("entities.hidden_gm_only"))
        # закрытое поле игрок получил пустым: его правку по нему не принимаем, иначе затрёт
        for key in HIDEABLE:
            if key in hidden:
                patch.pop(key, None)
    if "alias" in patch and e.kind not in ALIAS_KINDS:
        patch.pop("alias")
    if "hidden_fields" in patch:
        patch["hidden_fields"] = normalize_hidden(patch["hidden_fields"])
    for key, kind in (("faction_ids", "faction"), ("location_ids", "location")):
        if key in patch:
            patch[key] = normalize_affiliation(db, v, patch[key], kind, keep=getattr(e, key) or [])
    if "fields" in patch:
        # приходят только изменённые ключи: сливаем с текущими, null убирает ключ.
        # Чужая правка соседнего поля так не затирается, полный словарь даёт тот же итог
        incoming = patch["fields"] or {}
        if not v.is_gm:
            # закрытые ключи игрок не видел — их значения остаются как есть
            incoming = {k: val for k, val in strip_gm_fields(incoming, v).items()
                        if k not in hidden}
            incoming = visible_refs(db, v, e.kind, incoming, e.fields or {})
        merged = dict(e.fields or {})
        for k, val in incoming.items():
            if val is None:
                merged.pop(k, None)
            else:
                merged[k] = val
        patch["fields"] = normalize_fields(e.kind, merged)
    before, after = journal.changes(e, patch)
    for k, val in patch.items():
        setattr(e, k, val)
    if after:
        journal.log(db, v, "entity", "update", target_id=e.id, title=e.name,
                    entity_id=e.id, detail=e.kind, visibility=e.visibility,
                    before=before, after=after, merge=True)
    db.commit()
    return public_entity(e, v, peer_names(db, v.campaign_id, [e]))


# --- отношения экипажа с организациями ----------------------------------------
# Дашборд отношений правит стол, а не только владелец карточки: уровень отношений и
# список дел — это журнал самого экипажа. Поэтому отдельная ручка на два ключа
# вместо общего PATCH: остальная карточка организации игроку по-прежнему закрыта.

DEEDS_MAX = 60
DEED_LEN = 160


class Deed(BaseModel):
    id: str | None = Field(default=None, description="Keep the id of an existing deed to preserve its author and time; omit for a new one.")
    text: str = Field(max_length=DEED_LEN)


class StandingIn(BaseModel):
    stance: str | None = Field(default=None, description="Crew's standing with the faction: `-3` … `+3`, or `\"\"` to clear.", examples=["+1"])
    deeds: list[Deed] | None = Field(default=None, description="The whole list of deeds (what the crew did for or against them); replaces the stored list, max 60.")


def normalize_deeds(raw, v: Viewer, before: list) -> list[dict]:
    """Дела приходят списком целиком; автор и время у старых записей сохраняются."""
    known = {str(d.get("id")): d for d in before or [] if isinstance(d, dict)}
    out: list[dict] = []
    for item in raw or []:
        if len(out) >= DEEDS_MAX:
            break
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            continue
        old = known.get(str(item.get("id") or "")) or {}
        out.append({
            "id": old.get("id") or uid(),
            "text": re.sub(r"\s+", " ", str(item.get("text") or "")).strip()[:DEED_LEN],
            "at": old.get("at") or now().isoformat(),
            "by": old.get("by") or v.member_id,
        })
    return out


@router.patch("/entities/{entity_id}/standing", summary="Set crew standing with a faction", tags=["entities"],
              response_model=EntityOut, responses=error_responses(400))
def patch_standing(
    entity_id: str, body: StandingIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Update `fields.stance` and `fields.deeds` of a `faction` — the crew's own ledger, so any
    player may write it even when the rest of the card is closed. Journal entry on change.
    400: not a faction, or a stance outside `-3`…`+3`."""
    e = get_visible_entity(db, v, entity_id)
    if e.kind != "faction":
        raise HTTPException(400, tr("entities.status_factions_only"))
    patch = body.model_dump(exclude_unset=True)
    fields = dict(e.fields or {})

    if patch.get("stance") is not None:
        stance = str(patch["stance"]).strip()
        if stance and stance not in STANCES:
            raise HTTPException(400, tr("entities.bad_status", stance=stance))
        fields["stance"] = stance

    if patch.get("deeds") is not None:
        fields["deeds"] = normalize_deeds(patch["deeds"], v, fields.get("deeds") or [])

    keys = ("stance", "deeds")
    before, after = journal.changes_map(
        {k: (e.fields or {}).get(k) for k in keys},
        {k: fields.get(k) for k in keys},
    )
    e.fields = fields
    if after:
        journal.log(db, v, "entity", "standing", target_id=e.id, title=e.name,
                    entity_id=e.id, detail=ctr("content.status"), visibility=e.visibility,
                    before=before, after=after)
    db.commit()
    return public_entity(e, v, peer_names(db, v.campaign_id, [e]))


@router.delete("/entities/{entity_id}", summary="Archive a record", tags=["entities"], response_model=OkDiscard,
               responses=error_responses(403))
def archive_entity(
    entity_id: str,
    discard: bool = Query(default=False, description="`true`: delete the card for good only if it is still empty (no name, summary, image, links, files); otherwise leave it and answer `discarded: false`."),
    v: Viewer = Depends(editor), db: Session = Depends(get_db),
):
    """Archive, not delete: the record disappears from lists (`GET /entities?archived=true` shows it)
    and `PATCH {"archived": false}` brings it back. Use `DELETE …/purge` to remove it for good.
    GM or the card's owner. Journal entry."""
    e = get_visible_entity(db, v, entity_id)
    if not v.is_gm and not entity_editable(e, v):
        raise HTTPException(403, tr("entities.archive_denied"))
    # брошенная пустая карточка — её завели кнопкой «добавить» и закрыли, ничего не вписав
    if discard and not (e.name or e.alias or e.summary or e.image_url) and not any(
        db.query(m).filter(*cond).first() for m, cond in (
            (Attachment, (Attachment.target_type == "entity", Attachment.target_id == e.id)),
            (EntityLink, (or_(EntityLink.from_id == e.id, EntityLink.to_id == e.id),)),
        )
    ):
        db.delete(e)
        db.commit()
        return {"ok": True, "discarded": True}
    if discard:
        return {"ok": True, "discarded": False}
    e.archived = True
    journal.log(db, v, "entity", "archive", target_id=e.id, title=e.name,
                entity_id=e.id, detail=e.kind, visibility=e.visibility)
    db.commit()
    return {"ok": True}


@router.delete("/entities/{entity_id}/purge", summary="Delete a record for good", tags=["entities"], response_model=Ok,
               responses=error_responses(403))
def purge_entity(entity_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Irreversible. Its links, blocks, notes and attachments go with it; references from other
    rows (clock owner, marker link, board card, message sender, affiliations, `ref` fields, news)
    are cleared. The journal keeps the history. GM only (403 otherwise)."""
    if not v.is_gm:
        raise HTTPException(403, tr("entities.purge_gm_only"))
    e = get_visible_entity(db, v, entity_id)
    cid, eid = e.campaign_id, e.id
    db.query(EntityLink).filter(EntityLink.campaign_id == cid,
                                or_(EntityLink.from_id == eid, EntityLink.to_id == eid)).delete()
    db.query(ContentBlock).filter(ContentBlock.campaign_id == cid, ContentBlock.entity_id == eid).delete()
    for a in db.query(Attachment).filter(Attachment.campaign_id == cid, Attachment.target_type == "entity",
                                         Attachment.target_id == eid):
        drop_files(a)
        db.delete(a)
    db.query(Clock).filter(Clock.campaign_id == cid, Clock.owner_id == eid).update({"owner_id": None})
    db.query(MapMarker).filter(MapMarker.campaign_id == cid, MapMarker.linked_id == eid).update(
        {"linked_id": None, "linked_type": None})
    db.query(BoardCard).filter(BoardCard.campaign_id == cid, BoardCard.entity_id == eid).update(
        {"entity_id": None})
    db.query(Message).filter(Message.campaign_id == cid, Message.sender_entity_id == eid).update(
        {"sender_entity_id": None, "sender_reveal": False})
    for other in db.query(Entity).filter(Entity.campaign_id == cid, Entity.id != eid).all():
        for key in AFFILIATION_KEYS:
            ids = getattr(other, key, None) or []
            if eid in ids:
                setattr(other, key, [x for x in ids if x != eid])
        refs = {k: "" for k in ref_keys(other) if (other.fields or {}).get(k) == eid}
        if refs:
            other.fields = {**(other.fields or {}), **refs}
    for n in db.query(News).filter(News.campaign_id == cid).all():
        if eid in (n.entity_ids or []):
            n.entity_ids = [x for x in n.entity_ids if x != eid]
    journal.log(db, v, "entity", "purge", target_id=eid, title=e.name or ctr("content.unnamed"),
                detail=e.kind, visibility="gm")
    db.delete(e)
    db.commit()
    return {"ok": True}


# --- links --------------------------------------------------------------------


class LinkIn(BaseModel):
    from_id: str = Field(description="Entity id the link starts from (must be visible to the caller).")
    to_id: str = Field(description="Entity id the link points to (must be visible to the caller).")
    label: str = Field(default="", max_length=LABEL_LEN, description="Relation as read from `from` to `to`: `works for`, `where to find`, `owes`…", examples=["works for"])
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)


class LinkPatch(BaseModel):
    label: str | None = Field(default=None, max_length=LABEL_LEN)
    visibility: Visibility | None = Field(default=None, description="Players may not set `gm`.")
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)


class PeerBrief(BaseModel):
    """The entity on the other end of a link, with the same per-field hiding as the card itself."""

    id: str
    kind: str = Field(description="One of `GET /meta` → `kinds`; archived legacy cards may carry an older kind.")
    name: str
    summary: str
    image_url: str
    status: str


class LinkOut(BaseModel):
    id: str
    direction: Literal["out", "in"] = Field(description="`out`: the queried entity is `from_id`; `in`: it is `to_id`.")
    label: str
    visibility: Visibility
    from_id: str
    to_id: str
    created_by: str | None = Field(description="Member id of the author.")
    can_edit: bool
    can_delete: bool
    peer: PeerBrief
    visible_to: list[str] | None = Field(default=None, description="Present for the GM, the author and anyone who may edit the link.")


class LinkPatched(LinkOut):
    ok: bool = True


class LinkSaved(Ok):
    """Saved, but the record the link points to is closed to the caller: only the id comes back."""

    id: str


def link_title(db: Session, link: EntityLink) -> str:
    """Заголовок для журнала: «А — Б», имена берём на момент события."""
    names = []
    for eid in (link.from_id, link.to_id):
        e = db.get(Entity, eid)
        names.append(e.name if e else eid)
    return " — ".join(names)


def link_visible(link: EntityLink, v: Viewer) -> bool:
    """Автор связи — её владелец для видимости `owner`."""
    return can_see(link, v, owner_member_id=link.created_by)


def link_mine(link: EntityLink, v: Viewer) -> bool:
    return bool(v.member_id) and link.created_by == v.member_id


def link_editable(db: Session, link: EntityLink, v: Viewer) -> bool:
    """Связь правит ГМ, её автор — и тот, кому открыта любая из двух карточек:
    сцепка принадлежит карточкам, а не тому, кто первым её завёл."""
    if not writable(v):
        return False
    if v.is_gm or link_mine(link, v):
        return True
    for entity_id in (link.from_id, link.to_id):
        e = db.get(Entity, entity_id)
        if e and e.campaign_id == v.campaign_id and entity_editable(e, v):
            return True
    return False


def get_visible_link(db: Session, v: Viewer, link_id: str) -> EntityLink:
    link = db.get(EntityLink, link_id)
    if not link or link.campaign_id != v.campaign_id or not link_visible(link, v):
        raise HTTPException(404, tr("entities.not_found"))
    return link


def peer_brief(e: Entity, v: Viewer) -> dict:
    """Витрина соседа по связи — та же поштучная видимость, что и в самой карточке."""
    hidden: set[str] = set() if v.is_gm else hidden_keys(e)
    return {
        "id": e.id,
        "kind": e.kind,
        "name": e.name,
        "summary": "" if "summary" in hidden else e.summary,
        "image_url": "" if "image_url" in hidden else e.image_url,
        "status": e.status,
    }


def link_item(link: EntityLink, direction: str, peer: dict, v: Viewer, can: bool) -> dict:
    mine = v.is_gm or link_mine(link, v)
    item = {
        "id": link.id,
        "direction": direction,
        "label": link.label,
        "visibility": link.visibility,
        "from_id": link.from_id,
        "to_id": link.to_id,
        "created_by": link.created_by,
        "can_edit": can,
        "can_delete": can,
        "peer": peer,
    }
    if mine or can:
        item["visible_to"] = link.visible_to or []
    return item


def link_side(db: Session, v: Viewer, link: EntityLink, entity_id: str) -> dict | None:
    direction = "out" if link.from_id == entity_id else "in"
    peer_id = link.to_id if direction == "out" else link.from_id
    peer = db.get(Entity, peer_id)
    if not peer or peer.campaign_id != v.campaign_id or not can_see(peer, v):
        return None
    return link_item(link, direction, peer_brief(peer, v), v, link_editable(db, link, v))


def check_link_scope(v: Viewer, scope: str | None) -> None:
    if scope is None:
        return
    if scope not in SCOPES:
        raise HTTPException(400, tr("entities.bad_visibility", scope=scope))
    if not v.is_gm and scope not in PLAYER_SCOPES:
        raise HTTPException(403, tr("entities.player_no_gm_vis"))


@router.get("/entities/{entity_id}/links", summary="List links of a record", tags=["links"],
            response_model=list[LinkOut])
def entity_links(entity_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Links in both directions whose other end is visible to the viewer, oldest first."""
    get_visible_entity(db, v, entity_id)
    rows = (
        db.query(EntityLink)
        .filter(EntityLink.campaign_id == v.campaign_id,
                or_(EntityLink.from_id == entity_id, EntityLink.to_id == entity_id))
        .order_by(EntityLink.created_at)
        .all()
    )
    out = []
    for link in rows:
        if not link_visible(link, v):
            continue
        item = link_side(db, v, link, entity_id)
        if item:
            out.append(item)
    return out


@router.post("/links", summary="Create a link between two records", tags=["links"],
             response_model=LinkOut, responses=error_responses(400, 403))
def create_link(body: LinkIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Directed `from_id → to_id` with a label. GM omitting `visibility` gets `gm`. Journal entry.
    Returned with `direction: "out"` relative to `from_id`. 400: same entity on both ends, or an
    identical link already exists. 403: player asked for `gm`. 404: an end is not visible."""
    scope = default_visibility(v, body.visibility)
    check_link_scope(v, scope)
    if body.from_id == body.to_id:
        raise HTTPException(400, tr("entities.self_link"))
    get_visible_entity(db, v, body.from_id)
    get_visible_entity(db, v, body.to_id)
    label = re.sub(r"\s+", " ", body.label or "").strip()[:LABEL_LEN]
    dupes = (
        db.query(EntityLink)
        .filter_by(campaign_id=v.campaign_id, from_id=body.from_id, to_id=body.to_id)
        .all()
    )
    for old in dupes:
        if (old.label or "").casefold() == label.casefold() and link_visible(old, v):
            raise HTTPException(400, tr("entities.link_exists"))
    link = EntityLink(
        campaign_id=v.campaign_id,
        from_id=body.from_id,
        to_id=body.to_id,
        label=label,
        visibility=scope,
        visible_to=body.visible_to,
        created_by=v.member_id,
    )
    db.add(link)
    db.flush()
    journal.log(db, v, "link", "create", target_id=link.id, title=link_title(db, link),
                entity_id=link.from_id, detail=label, visibility=link.visibility)
    db.commit()
    # оба конца только что проверены на видимость — сторона есть всегда
    return link_side(db, v, link, link.from_id)


@router.patch("/links/{link_id}", summary="Update a link", tags=["links"],
              response_model=LinkPatched | LinkSaved, responses=error_responses(400, 403))
def patch_link(
    link_id: str, body: LinkPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Change label or visibility. GM, the author, or anyone who may edit one of the two
    records. Journal entry on change. Returned relative to `from_id`; just `{ok, id}` when `to_id`
    is closed to the caller."""
    link = get_visible_link(db, v, link_id)
    if not link_editable(db, link, v):
        raise HTTPException(403, tr("entities.link_edit_denied"))
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    check_link_scope(v, patch.get("visibility"))
    if "label" in patch:
        patch["label"] = re.sub(r"\s+", " ", patch["label"]).strip()[:LABEL_LEN]
    before, after = journal.changes(link, patch)
    for k, val in patch.items():
        setattr(link, k, val)
    if after:
        journal.log(db, v, "link", "update", target_id=link.id, title=link_title(db, link),
                    entity_id=link.from_id, visibility=link.visibility,
                    before=before, after=after)
    db.commit()
    item = link_side(db, v, link, link.from_id)
    return {"ok": True, **(item or {"id": link.id})}


@router.delete("/links/{link_id}", summary="Delete a link", tags=["links"], response_model=Ok,
               responses=error_responses(403))
def delete_link(link_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Same rights as editing. Journal entry."""
    link = get_visible_link(db, v, link_id)
    if not link_editable(db, link, v):
        raise HTTPException(403, tr("entities.link_delete_denied"))
    journal.log(db, v, "link", "delete", target_id=link.id, title=link_title(db, link),
                entity_id=link.from_id, visibility=link.visibility,
                before={"label": link.label})
    db.delete(link)
    db.commit()
    return {"ok": True}


# --- content blocks -----------------------------------------------------------


class BlockIn(BaseModel):
    block_type: BlockType = Field(default="text", description="Flavour of the block: a plain text, a `rumor`, a GM `secret`, a `warning`, a `quote`…")
    title: str = Field(default="", max_length=200)
    content: str = Field(default="", description="Markdown-ish text; this is where the knowledge of the campaign lives.", examples=["Seen at the third dock the night the manifest vanished."])
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)
    order: int = Field(default=0, description="Sort key inside the parent; equal keys sort by creation time.")
    links: list[str] = Field(default=[], description="Ids of entities this block is about; shown as chips. Ids not in this campaign are dropped.")


class BlockPatch(BaseModel):
    block_type: BlockType | None = None
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    visibility: Visibility | None = Field(default=None, description="Players may not set `gm`, nor change visibility of a GM's block.")
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)
    order: int | None = None
    links: list[str] | None = None


class BlockOut(BaseModel):
    id: str
    entity_type: BlockParent = Field(description="What the block hangs on.")
    entity_id: str = Field(description="Id of that parent.")
    block_type: str
    title: str
    content: str
    order: int
    created_by: str | None = Field(description="Member id of the author.")
    edited_by: str | None = Field(description="Member id of the last editor.")
    author_name: str
    editor_name: str
    by_gm: bool = Field(description="Written by the GM as GM, not through a player's eyes. Like any block, only its author or the GM may edit or delete it.")
    links: list[str] = Field(description="Entity ids the block is about; players get only the ones they may see.")
    link_names: dict[str, str] = Field(description="Names for `links` the viewer may see.")
    visibility: Visibility
    visible_to: list[str]
    can_edit: bool
    can_delete: bool
    created_at: datetime
    updated_at: datetime


class BlockPatched(BlockOut):
    ok: bool = True


def block_by_gm(b: ContentBlock) -> bool:
    return bool(getattr(b, "created_by_gm", False))


def block_visible(b: ContentBlock, v: Viewer, parent_owner: str | None = None) -> bool:
    """Для видимости `owner` владельцем считается автор записи или владелец сущности."""
    if v.is_gm:
        return True
    if b.visibility == "owner":
        owners = {x for x in (b.created_by, parent_owner) if x}
        return bool(v.member_id) and v.member_id in owners
    return can_see(b, v)


def block_parent_owner(db: Session, v: Viewer, entity_type: str, entity_id: str) -> str | None:
    if entity_type != "entity":
        return None
    parent = db.get(Entity, entity_id)
    if parent is None:
        return None
    if parent.campaign_id != v.campaign_id or not can_see(parent, v):
        raise HTTPException(404, tr("entities.not_found"))
    return parent.owner_member_id


def get_visible_block(db: Session, v: Viewer, block_id: str) -> ContentBlock:
    b = db.get(ContentBlock, block_id)
    if not b or b.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("entities.not_found"))
    parent_owner = block_parent_owner(db, v, b.entity_type, b.entity_id)
    if not block_visible(b, v, parent_owner):
        raise HTTPException(404, tr("entities.not_found"))
    return b


def link_names(db: Session, v: Viewer, blocks) -> dict[str, str]:
    """Имена карточек, с которыми связаны записи, — только тех, что смотрящий видит."""
    ids = {x for b in blocks for x in (getattr(b, "links", None) or [])
           if isinstance(x, str) and UUID_RE.fullmatch(x)}
    if not ids:
        return {}
    found = db.query(Entity).filter(
        Entity.campaign_id == v.campaign_id, Entity.id.in_(ids), Entity.archived.is_(False)).all()
    return {e.id: e.name for e in found if can_see(e, v)}


def block_links(db: Session, v: Viewer, raw, kept=()) -> list[str]:
    """Только id карточек этой кампании: мусорный id роняет панель записей у всего стола.
    `kept` — прежние ссылки, которых автор не видит: его правка их не снимает."""
    ids = list(dict.fromkeys(x for x in raw or [] if isinstance(x, str) and UUID_RE.fullmatch(x)))
    found = {eid for (eid,) in db.query(Entity.id).filter(
        Entity.campaign_id == v.campaign_id, Entity.id.in_(ids))} if ids else set()
    return [x for x in ids if x in found] + [x for x in kept if x not in ids and UUID_RE.fullmatch(x)]


def block_item(b: ContentBlock, v: Viewer, names: dict[str, str],
               cards: dict[str, str] | None = None) -> dict:
    by_gm = block_by_gm(b)
    links = list(getattr(b, "links", None) or [])
    if not v.is_gm:
        links = [x for x in links if x in (cards or {})]
    edited_by = getattr(b, "edited_by", None)
    mine = bool(v.member_id) and b.created_by == v.member_id
    can_write = writable(v) and (v.is_gm or mine)
    return {
        "id": b.id,
        "entity_type": b.entity_type,
        "entity_id": b.entity_id,
        "block_type": b.block_type,
        "title": b.title,
        "content": b.content,
        "order": b.order,
        "created_by": b.created_by,
        "edited_by": edited_by,
        "author_name": names.get(b.created_by or "", ""),
        "editor_name": names.get(edited_by or "", ""),
        "by_gm": by_gm,
        "links": links,
        "link_names": {x: cards[x] for x in links if cards and x in cards},
        "visibility": b.visibility,
        "visible_to": b.visible_to or [],
        "can_edit": can_write,
        "can_delete": can_write,
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


def block_label(b: ContentBlock) -> str:
    """Заголовок записи для журнала: своего может не быть — берём начало текста."""
    return (b.title or "").strip() or re.sub(r"\s+", " ", b.content or "").strip()[:80]


def block_owner_entity(b: ContentBlock) -> str | None:
    return b.entity_id if b.entity_type == "entity" else None


def check_block_scope(v: Viewer, scope: str | None) -> None:
    if scope is None:
        return
    if scope not in SCOPES:
        raise HTTPException(400, tr("entities.bad_visibility", scope=scope))
    if not v.is_gm and scope not in PLAYER_SCOPES:
        raise HTTPException(403, tr("entities.player_scopes"))


@router.get("/blocks/{entity_type}/{entity_id}", summary="List blocks of a record, clock, marker or map",
            tags=["blocks"], response_model=list[BlockOut])
def list_blocks(
    entity_type: BlockParent, entity_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)
):
    """Blocks the viewer may see, by `order` then creation time. 404 when the parent is not visible."""
    if entity_type == "entity":
        parent = get_visible_entity(db, v, entity_id)
        owner = parent.owner_member_id
    else:
        if not parent_visible(db, v, entity_type, entity_id):
            raise HTTPException(404, tr("entities.not_found"))
        owner = None
    rows = (
        db.query(ContentBlock)
        .filter_by(campaign_id=v.campaign_id, entity_type=entity_type, entity_id=entity_id)
        .order_by(ContentBlock.order, ContentBlock.created_at)
        .all()
    )
    names = member_names(db, v.campaign_id)
    shown = [b for b in rows if block_visible(b, v, owner)]
    cards = link_names(db, v, shown)
    return [block_item(b, v, names, cards) for b in shown]


@router.post("/blocks/{entity_type}/{entity_id}", summary="Add a block", tags=["blocks"],
             response_model=BlockOut, responses=error_responses(400, 403))
def create_block(
    entity_type: BlockParent,
    entity_id: str,
    body: BlockIn,
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Attach a text block to a record (`entity`), a `clock`, a `marker` or a `map`. A GM's block
    is `gm`-only unless `visibility` is sent — rumors and descriptions meant for the table must say
    `crew`. Journal entry. 403: player asked for `gm`. 404: parent not visible."""
    scope = default_visibility(v, body.visibility)
    check_block_scope(v, scope)
    if entity_type == "entity":
        get_visible_entity(db, v, entity_id)
    elif not parent_visible(db, v, entity_type, entity_id):
        raise HTTPException(404, tr("entities.not_found"))
    data = body.model_dump()
    data["visibility"] = scope
    data["links"] = block_links(db, v, body.links)
    b = ContentBlock(
        campaign_id=v.campaign_id,
        entity_type=entity_type,
        entity_id=entity_id,
        created_by=v.member_id,
        created_by_gm=v.is_real_gm and not v.acting_as,
        **data,
    )
    db.add(b)
    db.flush()
    journal.log(db, v, "block", "create", target_id=b.id, title=block_label(b),
                entity_id=block_owner_entity(b), visibility=b.visibility,
                after={"title": b.title, "content": b.content})
    db.commit()
    return block_item(b, v, member_names(db, v.campaign_id), link_names(db, v, [b]))


@router.patch("/blocks/{block_id}", summary="Update a block", tags=["blocks"],
              response_model=BlockPatched, responses=error_responses(400, 403))
def patch_block(
    block_id: str, body: BlockPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Only the keys sent change. Only the block's author or the GM may edit it, visibility
    included (403 otherwise). Records the editor; journal entry on change."""
    b = get_visible_block(db, v, block_id)
    if not v.is_gm and (not v.member_id or b.created_by != v.member_id):
        raise HTTPException(403, tr("entities.block_not_yours"))
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    check_block_scope(v, patch.get("visibility"))
    if "links" in patch:
        seen = link_names(db, v, [b])
        unseen = [x for x in b.links or [] if not v.is_gm and x not in seen]
        patch["links"] = block_links(db, v, patch["links"], unseen)
    before, after = journal.changes(b, patch)
    for k, val in patch.items():
        setattr(b, k, val)
    b.edited_by = v.member_id
    if after:
        journal.log(db, v, "block", "update", target_id=b.id, title=block_label(b),
                    entity_id=block_owner_entity(b), visibility=b.visibility,
                    before=before, after=after)
    db.commit()
    return {"ok": True, **block_item(b, v, member_names(db, v.campaign_id), link_names(db, v, [b]))}


@router.delete("/blocks/{block_id}", summary="Delete a block", tags=["blocks"], response_model=Ok,
               responses=error_responses(403))
def delete_block(block_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM deletes any block; a player only their own, never a GM's. Journal entry."""
    b = get_visible_block(db, v, block_id)
    if not v.is_gm:
        if block_by_gm(b):
            raise HTTPException(403, tr("entities.gm_note_delete"))
        if not v.member_id or b.created_by != v.member_id:
            raise HTTPException(403, tr("entities.note_delete_denied"))
    journal.log(db, v, "block", "delete", target_id=b.id, title=block_label(b),
                entity_id=block_owner_entity(b), visibility=b.visibility,
                before={"title": b.title, "content": b.content})
    db.delete(b)
    db.commit()
    return {"ok": True}
