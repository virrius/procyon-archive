from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, VISIBLE_TO_DOC, Ok, Visibility, default_visibility, error_responses, vis_field
from ..db import get_db
from ..deps import editor, gm_only, viewer
from ..i18n import tr
from ..models import Clock, Entity, Event
from ..visibility import ANY_PLAYER, Viewer, apply_scope, can_see

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["clocks"], responses=AUTH_ERRORS)

ClockColor = Literal["amber", "rust", "steel", "plum", "olive", "white"]
ClockStatus = Literal["active", "completed", "abandoned"]

OWNER_MEMBER_DOC = (
    "Who may tick and edit the clock: `\"*\"` — any player, `\"\"` — the GM only, or a member id. "
    "Omitted by a GM → `\"\"`; a player's own clock is always `\"*\"`. Only the GM changes it."
)
OWNER_DOC = "Entity the clock belongs to (a faction's plan, an NPC's scheme): `owner_type` is `entity`, `owner_id` its id. Both optional."


class ClockIn(BaseModel):
    name: str = Field(description="Clock title.", examples=["Syndicate retaliation"])
    description: str = Field("", description="What the clock tracks.")
    outcome: str = Field("", description="What happens when it fills.")
    kind: str = Field("", max_length=60, description="Free-text category the table uses to group clocks (see `GET /clock-kinds`).", examples=["threat"])
    color: ClockColor = Field("amber", description="Display colour.")
    segments: int = Field(6, ge=2, le=24, description="Number of segments, 2..24.", examples=[6])
    filled: int = Field(0, ge=0, description="Segments already filled.")
    status: ClockStatus = Field("active", description="Lifecycle state; new clocks are `active`.")
    owner_type: Literal["entity"] | None = Field(None, description=OWNER_DOC)
    owner_id: str | None = Field(None, description="Id of the owning entity (with `owner_type: entity`).")
    owner_member_id: str | None = Field(None, description=OWNER_MEMBER_DOC + " Omitted: a GM's clock gets `\"\"` (GM only), a player's gets `\"*\"`.")
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field([], description=VISIBLE_TO_DOC)


class ClockPatch(BaseModel):
    """Only the keys sent are changed. A closed clock accepts only visibility, visible_to and owner_member_id."""

    name: str | None = None
    description: str | None = None
    outcome: str | None = None
    kind: str | None = Field(None, max_length=60)
    color: ClockColor | None = None
    segments: int | None = Field(None, ge=2, le=24)
    filled: int | None = Field(None, ge=0, description="Clamped to 0..segments.")
    owner_type: Literal["entity"] | None = Field(None, description=OWNER_DOC)
    owner_id: str | None = None
    owner_member_id: str | None = Field(None, description=OWNER_MEMBER_DOC + " GM only.")
    visibility: Visibility | None = Field(None, description="New audience; players cannot set `gm`.")
    visible_to: list[str] | None = Field(None, description=VISIBLE_TO_DOC)


class TickIn(BaseModel):
    delta: int = Field(1, description="Segments to add (negative to remove). Clamped to 0..segments.")
    comment: str = Field("", description="Why the clock moved; shown in its history and the journal.")


class CompleteIn(BaseModel):
    comment: str = Field("", description="Closing note for the journal.")


class ClockOut(BaseModel):
    id: str
    name: str
    description: str
    outcome: str
    kind: str
    color: str
    segments: int
    filled: int
    status: ClockStatus
    owner_type: str | None = Field(description="`entity` when the clock belongs to a card; null for players when that card is hidden from them.")
    owner_id: str | None = Field(description="Id of the owning card; null for players when that card is hidden from them.")
    owner_name: str = Field(description="Name of the owning entity if it exists and is visible to you; else empty.")
    owner_member_id: str = Field(description=OWNER_MEMBER_DOC)
    can_edit: bool = Field(description="Whether this viewer may tick and edit the clock.")
    created_at: datetime
    updated_at: datetime
    visibility: Visibility | None = Field(None, description="Present for the GM only.")
    visible_to: list[str] | None = Field(None, description="Present for the GM only.")


class ClockHistoryOut(BaseModel):
    delta: int = Field(description="Change in filled segments (0 for complete/reopen).")
    from_: int = Field(alias="from", description="Filled before the move.")
    to: int = Field(description="Filled after the move.")
    comment: str = Field(description="Tick comment, or a localised 'completed' / 'reopened' marker.")
    author_member_id: str | None
    at: datetime

    model_config = {"populate_by_name": True}


def clock_editable(c: Clock, v: Viewer) -> bool:
    """Правку счётчика раздаёт ГМ: любой игрок ('*'), один участник или никто ('')."""
    if v.is_gm:
        return True
    who = ANY_PLAYER if c.owner_member_id is None else c.owner_member_id
    if who == ANY_PLAYER:
        return True
    return bool(v.member_id) and who == v.member_id


def _editable_or_403(c: Clock, v: Viewer) -> None:
    if not clock_editable(c, v):
        raise HTTPException(403, tr("clocks.edit_denied"))


def clock_title(c: Clock, db: Session) -> str:
    """Имя счётчика в журнале: «привязанная запись: счётчик».

    Счётчиков с одинаковым именем в кампании много («Погоня», «Тревога»), и без
    записи, к которой он привязан, строка журнала не читается.
    """
    if c.owner_type == "entity" and c.owner_id:
        e = db.get(Entity, c.owner_id)
        if e:
            return f"{e.name}: {c.name}"
    return c.name


def _owner_visible(c: Clock, v: Viewer, db: Session) -> Entity | None:
    if c.owner_type != "entity" or not c.owner_id:
        return None
    e = db.get(Entity, c.owner_id)
    return e if e and can_see(e, v) else None


def _out(c: Clock, v: Viewer, db: Session) -> dict:
    owner = _owner_visible(c, v, db)
    owner_name = owner.name if owner else ""
    # закрытый от стола владелец не выдаётся даже идентификатором
    hidden_owner = bool(c.owner_id) and owner is None and not v.is_gm
    d = {
        "id": c.id, "name": c.name, "description": c.description, "outcome": c.outcome,
        "kind": c.kind or "", "color": c.color, "segments": c.segments, "filled": c.filled,
        "status": c.status, "owner_type": None if hidden_owner else c.owner_type,
        "owner_id": None if hidden_owner else c.owner_id,
        "owner_name": owner_name, "updated_at": c.updated_at, "created_at": c.created_at,
        "owner_member_id": ANY_PLAYER if c.owner_member_id is None else c.owner_member_id,
        "can_edit": clock_editable(c, v),
    }
    if v.is_gm:
        d["visibility"] = c.visibility
        d["visible_to"] = c.visible_to or []
    return d


@router.get("/clocks", summary="List clocks", response_model=list[ClockOut])
def list_clocks(
    v: Viewer = Depends(viewer),
    db: Session = Depends(get_db),
    status: str | None = Query("active", description="Filter by status (`active`, `completed`, `abandoned`); empty string = all."),
    owner_id: str | None = Query(None, description="Only clocks owned by this entity."),
    kind: str | None = Query(None, description="Only clocks of this free-text kind."),
    limit: int | None = Query(None, ge=1, description="Page size; omitted → all."),
    offset: int = Query(0, ge=0),
):
    """Clocks visible to the viewer, grouped by kind (kindless last), newest first within a kind.
    Default filter is `status=active`; pass `status=` (empty) to see closed ones too."""
    q = db.query(Clock).filter(Clock.campaign_id == v.campaign_id)
    if status:
        q = q.filter(Clock.status == status)
    if owner_id:
        q = q.filter(Clock.owner_id == owner_id)
    if kind:
        q = q.filter(Clock.kind == kind)
    # тип вперёд (без типа — в конец), внутри — по created_at: тик не переставляет карточки
    q = (
        apply_scope(q, Clock, v)
        .order_by(
            case((Clock.kind == "", 1), else_=0),
            Clock.kind,
            Clock.created_at.desc(),
            Clock.id,
        )
        .offset(offset)
    )
    rows = (q.limit(limit) if limit else q).all()
    return [_out(c, v, db) for c in rows]


@router.get("/clock-kinds", summary="List clock kinds in use", response_model=list[str])
def clock_kinds(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Kinds are not predefined: this is the distinct set of `kind` values on clocks the viewer can see."""
    q = db.query(Clock).filter(Clock.campaign_id == v.campaign_id, Clock.kind != "")
    rows = apply_scope(q, Clock, v).all()
    return sorted({c.kind for c in rows}, key=str.casefold)


@router.post("/clocks", summary="Create a clock", response_model=ClockOut, responses=error_responses(400))
def create_clock(body: ClockIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM or player. A GM's clock defaults to `visibility: gm` and `owner_member_id: ""` (GM-only editing)
    until opened on purpose; a player's clock is `crew` and editable by any player. Writes a `create` journal entry.
    400 — segments outside 2..24 or unknown colour; 403 — a player asking for `gm` visibility."""
    if not v.is_gm and body.visibility == "gm":
        raise HTTPException(403, tr("clocks.gm_only"))
    data = body.model_dump()
    data["kind"] = (data.get("kind") or "").strip()[:60]
    # счётчик ГМа заводится закрытым, и правит его только ГМ: стол получает
    # и счётчик, и право на него, когда ГМ сам их отдаст
    data["visibility"] = default_visibility(v, body.visibility)
    if v.is_gm and data.get("owner_member_id") is None:
        data["owner_member_id"] = ""
    if not v.is_gm:
        # игрок не раздаёт права: свой счётчик он завёл открытым для стола
        data["owner_member_id"] = ANY_PLAYER
    c = Clock(campaign_id=v.campaign_id, **data)
    db.add(c)
    db.flush()
    journal.log(db, v, "clock", "create", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=f"0/{c.segments}", visibility=c.visibility)
    db.commit()
    return _out(c, v, db)


def _get(db: Session, v: Viewer, clock_id: str) -> Clock:
    c = db.get(Clock, clock_id)
    if not c or c.campaign_id != v.campaign_id or not can_see(c, v):
        raise HTTPException(404, tr("clocks.not_found"))
    return c


@router.patch("/clocks/{clock_id}", summary="Edit a clock", response_model=ClockOut, responses=error_responses(400))
def patch_clock(
    clock_id: str, body: ClockPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Only the keys sent are changed; `filled` is clamped to 0..segments. A closed clock (completed or
    abandoned) accepts only `visibility`, `visible_to` and `owner_member_id` — 400 otherwise.
    403 — not the clock's editor, or a player touching `owner_member_id` / setting `gm`. Writes an `update` journal entry."""
    c = _get(db, v, clock_id)
    _editable_or_403(c, v)
    data = body.model_dump(exclude_unset=True)
    if "owner_member_id" in data and not v.is_gm:
        raise HTTPException(403, tr("clocks.owner_gm_only"))
    if c.status != "active":
        # закрытый счётчик — только видимость; содержимое заморожено
        extra = set(data) - {"visibility", "visible_to", "owner_member_id"}
        if extra:
            raise HTTPException(400, tr("clocks.closed_frozen"))
    if "visibility" in data and data["visibility"] == "gm" and not v.is_gm:
        raise HTTPException(403, tr("clocks.gm_only"))
    if "kind" in data:
        data["kind"] = (data["kind"] or "").strip()[:60]
    if not v.is_gm and c.owner_id and _owner_visible(c, v, db) is None:
        # игрок не видит владельца — и не может его снять или подменить
        data.pop("owner_type", None)
        data.pop("owner_id", None)
    before, after = journal.changes(c, data)
    for k, val in data.items():
        setattr(c, k, val)
    c.filled = max(0, min(c.segments, c.filled))
    if after:
        journal.log(db, v, "clock", "update", target_id=c.id, title=clock_title(c, db),
                    entity_id=c.owner_id if c.owner_type == "entity" else None,
                    visibility=c.visibility, before=before, after=after)
    db.commit()
    return _out(c, v, db)


@router.post("/clocks/{clock_id}/tick", summary="Tick a clock", response_model=ClockOut, responses=error_responses(400))
def tick_clock(
    clock_id: str, body: TickIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Move the clock by `delta` segments and record why. Only on an `active` clock (400 otherwise);
    400 also when adding to a full clock. 403 — not the clock's editor. Writes a `tick` journal entry
    that `GET …/history` reads back."""
    c = _get(db, v, clock_id)
    _editable_or_403(c, v)
    if c.status != "active":
        raise HTTPException(400, tr("clocks.closed_reopen_first"))
    if body.delta > 0 and c.filled >= c.segments:
        raise HTTPException(400, tr("clocks.already_full"))
    before = c.filled
    c.filled = max(0, min(c.segments, c.filled + body.delta))
    journal.log(db, v, "clock", "tick", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=body.comment, visibility=c.visibility,
                before={"filled": before}, after={"filled": c.filled,
                                                  "segments": c.segments})
    db.commit()
    return _out(c, v, db)


@router.post("/clocks/{clock_id}/complete", summary="Complete a filled clock", response_model=ClockOut, responses=error_responses(400))
def complete_clock(
    clock_id: str,
    body: CompleteIn = CompleteIn(),
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """A full clock is closed by a person, never automatically: status becomes `completed`.
    400 — not active, or not yet filled. 403 — not the clock's editor. Journal: `complete`."""
    c = _get(db, v, clock_id)
    _editable_or_403(c, v)
    if c.status != "active":
        raise HTTPException(400, tr("clocks.already_closed"))
    if c.filled < c.segments:
        raise HTTPException(400, tr("clocks.not_full"))
    c.status = "completed"
    journal.log(db, v, "clock", "complete", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=body.comment, visibility=c.visibility)
    db.commit()
    return _out(c, v, db)


@router.post("/clocks/{clock_id}/reopen", summary="Reopen a closed clock", response_model=ClockOut, responses=error_responses(400))
def reopen_clock(clock_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """A completed or abandoned clock returns to `active` with its fill unchanged.
    An abandoned clock can be reopened by the GM only (403). 400 — already active. Journal: `reopen`."""
    c = _get(db, v, clock_id)
    _editable_or_403(c, v)
    if c.status == "active":
        raise HTTPException(400, tr("clocks.already_open"))
    if c.status == "abandoned" and not v.is_gm:
        raise HTTPException(403, tr("clocks.abandoned_gm"))
    c.status = "active"
    journal.log(db, v, "clock", "reopen", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=f"{c.filled}/{c.segments}", visibility=c.visibility)
    db.commit()
    return _out(c, v, db)


@router.get("/clocks/{clock_id}/history", summary="Clock move history", response_model=list[ClockHistoryOut])
def clock_history(clock_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Ticks, completions and reopenings of this clock, newest first — read from the campaign journal."""
    c = _get(db, v, clock_id)
    rows = (
        db.query(Event)
        .filter(Event.campaign_id == v.campaign_id, Event.source == "clock",
                Event.target_id == c.id,
                Event.action.in_(("tick", "complete", "reopen")))
        .order_by(Event.created_at.desc())
        .all()
    )
    out = []
    for e in rows:
        # у завершения шкала не двигается: заполненный счётчик дальше заморожен
        was = (e.before or {}).get("filled", c.filled)
        became = (e.after or {}).get("filled", was)
        out.append({
            "delta": became - was, "from": was, "to": became,
            "comment": tr("clocks.history.reopened") if e.action == "reopen"
            else e.detail or (tr("clocks.history.completed") if e.action == "complete" else ""),
            "author_member_id": e.actor_member_id, "at": e.created_at,
        })
    return out


@router.delete("/clocks/{clock_id}/purge", summary="Delete a clock for good", response_model=Ok)
def purge_clock(clock_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Removes the clock; the journal keeps its history and adds a `purge` entry.
    For the normal way out use `DELETE /clocks/{clock_id}` (abandon)."""
    c = _get(db, v, clock_id)
    journal.log(db, v, "clock", "purge", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=f"{c.filled}/{c.segments}", visibility=c.visibility)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.delete("/clocks/{clock_id}", summary="Abandon a clock", response_model=Ok, responses=error_responses(400))
def abandon_clock(clock_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Not a deletion: status becomes `abandoned`, the row stays (list it with `status=abandoned`).
    400 — already closed. 403 — not the clock's editor. Journal: `delete`. Only the GM can reopen it."""
    c = _get(db, v, clock_id)
    _editable_or_403(c, v)
    if c.status != "active":
        raise HTTPException(400, tr("clocks.already_closed"))
    c.status = "abandoned"
    journal.log(db, v, "clock", "delete", target_id=c.id, title=clock_title(c, db),
                entity_id=c.owner_id if c.owner_type == "entity" else None,
                detail=f"{c.filled}/{c.segments}", visibility=c.visibility)
    db.commit()
    return {"ok": True}
