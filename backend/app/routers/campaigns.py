from __future__ import annotations


from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import langpack
from ..api_schema import AUTH_ERRORS, Ok, Role, error_responses
from ..book_defs import book
from ..book_lore import seed_campaign
from ..db import get_db
from ..deps import current_user, gm_only, viewer
from ..i18n import LANGS, instance_lang, tr
from ..models import AuditLog, Campaign, CampaignMember, Entity, User
from ..security import hash_password
from ..visibility import Viewer
from .rules import seed_rules

router = APIRouter(prefix="/api", tags=["campaigns"], responses=AUTH_ERRORS)


class CampaignIn(BaseModel):
    name: str = Field(max_length=200, examples=["The Procyon Run"])
    description: str = ""
    lang: Literal["ru", "en"] | None = Field(
        default=None, description="Language of the starting materials: rulebook canon, sector map, ship. Empty = the instance language.")


# --- vocabulary ---------------------------------------------------------------------------


class FieldDef(BaseModel):
    key: str = Field(description="Key inside `entity.fields`.")
    label: str = Field(description="Human label in the request language.")
    type: str = Field(description="`text` | `textarea` | `select` | `multi` (list of strings) | `ref` (id of another entity).")
    options: list[str] | None = Field(default=None, description="Allowed values for `select` / `multi`.")
    max: int | None = Field(default=None, description="For `multi`: how many values may be picked.")
    kinds: str | None = Field(default=None, description="For `ref`: comma-separated entity kinds the id may point to.")
    secret: bool | None = Field(default=None, description="Hidden from players on a new card by default (listed in `hidden_fields`).")
    badge: bool | None = Field(default=None, description="UI hint: shown as a badge on the card.")
    note: bool | None = Field(default=None, description="UI hint: shown as a short line under the name.")


class KindDef(BaseModel):
    label: str
    plural: str
    statuses: list[str] = Field(description="Allowed `status` values; empty — the kind has no status.")
    fields: list[FieldDef] = Field(description="Kind-specific keys of `entity.fields`. Any key may also be hidden per card via `hidden_fields`; keys starting with `gm_` are GM-only.")


class MetaOut(BaseModel):
    """The vocabulary of the instance. Read it once before writing anything."""

    kinds: dict[str, KindDef] = Field(description="Entity kinds (`character`, `npc`, `faction`, `ship`, `location`, `job`, `item`) with their fields and statuses.")
    message_types: list[str] = Field(description="Allowed `msg_type` of a message.")
    visibility_scopes: list[str] = Field(description="`crew` | `selected` | `owner` | `gm` — see the API description.")
    block_types: list[str] = Field(description="Allowed `block_type` of a content block.")
    labels: dict[str, str] = Field(description="Human labels for internal keys (statuses, link labels, ship types) in the request language.")
    systems: list[str] = Field(description="Star systems of the sector — values of the `system` field.")
    ship_sizes: list[str]
    ship_types: dict[str, dict] = Field(description="Ship type key → {label, blurb, …} from the rulebook.")
    ship_modules: dict[str, list[dict]] = Field(description="Ship modules by slot (hull, …) from the rulebook.")
    playbooks: dict[str, dict] = Field(description="Character playbook key → {label, aliases, blurb, unique, talents, items, xp_trigger, start, builds} from the rulebook. `fields.playbook` stores the label; `fields.talents` stores `playbook:talent` keys.")
    char_sheet: dict = Field(description="Character sheet reference: standard items, heritages, backgrounds (`past`), vices, traumas with texts, xp, harm, load, stash, teamwork notes.")


@router.get("/meta", tags=["system"], summary="Vocabulary: kinds, fields, statuses, scopes", response_model=MetaOut,
            response_model_exclude_none=True)
def get_meta():
    """Everything the schema cannot express as enums: which `fields` keys and `status`
    values each entity kind has, message and block types, visibility scopes, star systems,
    ship types. Labels follow `Accept-Language`. No login: the web app reads it before sign-in."""
    S, B = langpack.schema(), book()
    return {
        "kinds": S.kinds(),
        "message_types": S.MESSAGE_TYPES,
        "visibility_scopes": S.VISIBILITY_SCOPES,
        "block_types": S.BLOCK_TYPES,
        "labels": S.labels(),
        "systems": S.SYSTEMS,
        "ship_sizes": B.SHIP_SIZES,
        "ship_types": B.SHIP_TYPES,
        "ship_modules": B.SHIP_MODULES,
        "playbooks": {key: {**pb, "aliases": [book(lang).PLAYBOOK_SHEETS[key]["label"] for lang in LANGS]}
                      for key, pb in S.PLAYBOOK_SHEETS.items()},
        "char_sheet": S.CHAR_SHEET,
    }


class LangOut(BaseModel):
    lang: str = Field(description="`ru` | `en` — the instance language: UI, rulebook canon, generated texts.")


@router.get("/lang", tags=["system"], summary="Instance language", response_model=LangOut)
def get_lang():
    """No login: the login screen needs it first. Error texts of other calls follow
    `Accept-Language` and fall back to this language."""
    return {"lang": instance_lang()}


# --- campaigns ----------------------------------------------------------------------------


class CampaignBrief(BaseModel):
    id: str
    name: str
    status: str
    role: Role = Field(description="Your role in this campaign.")
    member_id: str = Field(description="Your member id here — what `visible_to`, `owner_member_id` and `X-View-As` take.")


@router.get("/campaigns", summary="Campaigns I belong to", response_model=list[CampaignBrief])
def list_campaigns(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """One row per membership, with your role and member id. The `id` goes into every
    `/api/campaigns/{campaign_id}/…` path."""
    ms = db.query(CampaignMember).filter_by(user_id=user.id).all()
    return [
        {
            "id": m.campaign.id,
            "name": m.campaign.name,
            "status": m.campaign.status,
            "role": m.role,
            "member_id": m.id,
        }
        for m in ms
    ]


class CampaignCreated(BaseModel):
    id: str


@router.post("/campaigns", summary="Create a campaign (admin)", response_model=CampaignCreated,
             responses=error_responses(403))
def create_campaign(
    body: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Server admin only. The creator becomes its GM. The campaign starts with the
    rulebook canon: factions, locations, the sector map with their markers, and an unnamed ship — in `lang`.
    Once created, the materials stay in that language."""
    if not user.is_admin:
        raise HTTPException(403, tr("campaigns.admin_creates"))
    lang = body.lang or instance_lang()
    c = Campaign(name=body.name, description=body.description, owner_id=user.id, lang=lang)
    db.add(c)
    db.flush()
    gm = CampaignMember(campaign_id=c.id, user_id=user.id, role="gm", display_name=user.display_name)
    db.add(gm)
    db.flush()
    db.add(Entity(campaign_id=c.id, kind="ship", name=tr("content.ship_unnamed", lang=lang)))
    seed_campaign(db, c.id, lang)
    seed_rules(db, c.id, gm.id, lang)
    db.commit()
    return {"id": c.id}


class CampaignPatch(BaseModel):
    name: str = Field(max_length=200)


class CampaignRenamed(BaseModel):
    id: str
    name: str


@router.patch("/campaigns/{campaign_id}", summary="Rename the campaign (GM)", response_model=CampaignRenamed,
              responses=error_responses(422))
def rename_campaign(body: CampaignPatch, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Only the name can change. 422 — empty name."""
    name = body.name.strip()
    if not name:
        raise HTTPException(422, tr("campaigns.name_empty"))
    c = db.get(Campaign, v.campaign_id)
    c.name = name
    db.commit()
    return {"id": c.id, "name": c.name}


class MemberOut(BaseModel):
    id: str = Field(description="Member id — the value for `visible_to`, `owner_member_id`, `X-View-As`.")
    role: Role
    display_name: str
    login: str | None = Field(default=None, description="Only for the GM.")
    is_active: bool | None = Field(default=None, description="Only for the GM.")


class CampaignOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    world_day: int = Field(description="Game day counter (0 = campaign start); year/week/day are derived by the UI.")
    my_role: Role = Field(description="Effective role — `player` when a GM uses `X-View-As`.")
    my_member_id: str | None = Field(description="Effective member id; empty under `X-View-As: crew`.")
    is_real_gm: bool
    acting_as: str | None = Field(description="`crew` or a member id when `X-View-As` is in effect, else null.")
    members: list[MemberOut]
    sheet_setup: dict = Field(description="GM's crew sheet setup over the rulebook — see `PUT /sheet-setup`.")


@router.get("/campaigns/{campaign_id}", summary="Campaign with its members", response_model=CampaignOut)
def get_campaign(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """The place to get member ids (for `visible_to`, `owner_member_id`, `X-View-As`)
    and the current game day."""
    c = db.get(Campaign, v.campaign_id)
    members = db.query(CampaignMember).filter_by(campaign_id=c.id).all()
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "status": c.status,
        "world_day": c.world_day,
        "my_role": v.role,
        "my_member_id": v.member_id,
        "is_real_gm": v.is_real_gm,
        "acting_as": v.acting_as,
        "members": [
            {
                "id": m.id,
                "role": m.role,
                "display_name": m.display_name or m.user.display_name,
                "login": m.user.login if v.is_real_gm else None,
                "is_active": m.user.is_active if v.is_real_gm else None,
            }
            for m in members
        ],
        "sheet_setup": c.sheet_setup or {},
    }


class SheetRow(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(max_length=160)
    text: str = Field(default="", max_length=2000)
    more: str = Field(default="", max_length=4000)
    load: int | list[int] | None = Field(default=None, description="Items only: load or a choice of loads.")
    armor: bool = Field(default=False, description="Abilities only: uses special armor.")
    fine: bool = False


class PlaybookSetup(BaseModel):
    talents: list[SheetRow] | None = Field(default=None, description="Replaces the book's special abilities.")
    items: list[SheetRow] | None = Field(default=None, description="Replaces the book's playbook items.")
    stress_max: int | None = Field(default=None, ge=1, le=12)
    xp_trigger: str | None = Field(default=None, max_length=400)


class SheetSetup(BaseModel):
    common: list[SheetRow] | None = Field(default=None, description="Replaces the standard items of every sheet.")
    playbooks: dict[str, PlaybookSetup] = Field(default={}, description="Playbook key → its setup.")


@router.put("/campaigns/{campaign_id}/sheet-setup", summary="Set the crew sheet setup (GM)",
            response_model=dict, responses=error_responses(422))
def put_sheet_setup(body: SheetSetup, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Whole setup at once; a section left out falls back to the rulebook for every character.
    422 — unknown playbook key."""
    unknown = set(body.playbooks) - set(book().PLAYBOOK_SHEETS)
    if unknown:
        raise HTTPException(422, tr("campaigns.bad_playbook", keys=", ".join(sorted(unknown))))
    setup = body.model_dump(exclude_none=True, exclude_defaults=True)
    setup["playbooks"] = {k: p for k, p in setup.get("playbooks", {}).items() if p}
    if not setup["playbooks"]:
        setup.pop("playbooks")
    c = db.get(Campaign, v.campaign_id)
    c.sheet_setup = setup
    db.commit()
    return setup


# --- game time ----------------------------------------------------------------------------


class TimeOut(BaseModel):
    day: int = Field(description="Game day counter; 0 = campaign start.")


class TimeShift(BaseModel):
    days: int = Field(ge=-3650, le=3650, description="Days to add (negative to go back); clamped at 0.")


class TimeSet(BaseModel):
    day: int = Field(ge=0)


@router.get("/campaigns/{campaign_id}/time", summary="Game day", response_model=TimeOut)
def get_time(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """The campaign's game day counter (0 = start). Messages and news carry `world_day` in the same units."""
    return {"day": db.get(Campaign, v.campaign_id).world_day}


@router.post("/campaigns/{campaign_id}/time", summary="Shift the game day (GM)", response_model=TimeOut)
def shift_time(body: TimeShift, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Adds `days` to the counter (never below 0) and returns the new value."""
    c = db.get(Campaign, v.campaign_id)
    c.world_day = max(0, c.world_day + body.days)
    db.commit()
    return {"day": c.world_day}


@router.put("/campaigns/{campaign_id}/time", summary="Set the game day (GM)", response_model=TimeOut)
def set_time(body: TimeSet, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Sets the counter to an absolute day."""
    c = db.get(Campaign, v.campaign_id)
    c.world_day = body.day
    db.commit()
    return {"day": c.world_day}


# --- player accounts ----------------------------------------------------------------------


class PlayerIn(BaseModel):
    login: str = Field(description="Lower-cased, unique across the server.", examples=["kes"])
    password: str = Field(min_length=4)
    display_name: str = Field(default="", description="Shown at the table; defaults to the login.")
    role: Role = Field(default="player", description="`observer` reads only.")


class PlayerPatch(BaseModel):
    password: str | None = Field(default=None, min_length=4, description="New password.")
    display_name: str | None = None
    is_active: bool | None = Field(default=None, description="`false` blocks the account; the campaign owner cannot be blocked.")


class PlayerCreated(BaseModel):
    member_id: str
    user_id: str
    login: str
    role: Role


@router.post("/campaigns/{campaign_id}/players", summary="Create a player account (GM)",
             response_model=PlayerCreated, responses=error_responses(400, 409))
def create_player(
    body: PlayerIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    """Creates the user and adds them to this campaign; the GM hands the login and password
    to the player. 409 — the login is taken."""
    login = body.login.strip().lower()
    if not login or len(body.password) < 4:
        raise HTTPException(400, tr("campaigns.login_password"))
    if body.role not in ("player", "gm", "observer"):
        raise HTTPException(400, tr("campaigns.bad_role"))
    user = db.query(User).filter(User.login == login).first()
    if user:
        raise HTTPException(409, tr("campaigns.login_taken"))
    user = User(
        login=login,
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip() or login,
    )
    db.add(user)
    db.flush()
    m = CampaignMember(
        campaign_id=v.campaign_id, user_id=user.id, role=body.role,
        display_name=user.display_name,
    )
    db.add(m)
    db.add(AuditLog(campaign_id=v.campaign_id, user_id=v.user_id,
                    action="player_created", detail=login))
    db.commit()
    return {"member_id": m.id, "user_id": user.id, "login": user.login, "role": m.role}


def _account_locked(db: Session, v: Viewer, user: User) -> bool:
    """The account spans more than this campaign: the GM can only remove it from here; the instance admin edits it."""
    if db.get(User, v.user_id).is_admin:
        return False
    if user.is_admin or user.id == db.get(Campaign, v.campaign_id).owner_id:
        return True
    return db.query(CampaignMember).filter(
        CampaignMember.user_id == user.id, CampaignMember.campaign_id != v.campaign_id
    ).count() > 0


@router.patch("/campaigns/{campaign_id}/players/{member_id}", summary="Reset password, rename or block a player (GM)",
              response_model=Ok, responses=error_responses(400, 403))
def patch_player(
    member_id: str, body: PlayerPatch, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    """Only the keys sent are applied. Password resets and blocks are written to the account audit (`/history`, source `account`).
    403 — the account is a server admin, the campaign owner or a member of other campaigns: only a server admin
    may change it; a GM may only remove it from the campaign."""
    m = db.get(CampaignMember, member_id)
    if not m or m.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("campaigns.member_missing"))
    user = db.get(User, m.user_id)
    if _account_locked(db, v, user):
        raise HTTPException(403, tr("campaigns.account_locked"))
    if body.password:
        if len(body.password) < 4:
            raise HTTPException(400, tr("campaigns.password_short"))
        user.password_hash = hash_password(body.password)
        user.token_version = (user.token_version or 0) + 1
        db.add(AuditLog(campaign_id=v.campaign_id, user_id=v.user_id,
                        action="password_reset", detail=user.login))
    if body.display_name is not None:
        user.display_name = body.display_name
        m.display_name = body.display_name
    if body.is_active is not None:
        if not body.is_active and user.id == db.get(Campaign, v.campaign_id).owner_id:
            raise HTTPException(400, tr("campaigns.owner_disable"))
        user.is_active = body.is_active
        db.add(AuditLog(campaign_id=v.campaign_id, user_id=v.user_id,
                        action="account_active" if body.is_active else "account_blocked",
                        detail=user.login))
    db.commit()
    return {"ok": True}


@router.delete("/campaigns/{campaign_id}/members/{member_id}", summary="Remove a member (GM)",
               response_model=Ok, responses=error_responses(400))
def revoke_member(
    member_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    """Removes the membership. An account that belonged to no other campaign (and is not
    a server admin) is disabled so its token stops working. The owner cannot be removed (400)."""
    m = db.get(CampaignMember, member_id)
    if not m or m.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("campaigns.member_missing"))
    if m.user_id == db.get(Campaign, v.campaign_id).owner_id:
        raise HTTPException(400, tr("campaigns.owner_revoke"))
    user = db.get(User, m.user_id)
    other = (
        db.query(CampaignMember)
        .filter(CampaignMember.user_id == m.user_id, CampaignMember.id != m.id)
        .count()
    )
    db.delete(m)
    if user and other == 0 and not user.is_admin:
        # account exists only for this campaign: disable it so its token dies too
        user.is_active = False
    db.add(AuditLog(campaign_id=v.campaign_id, user_id=v.user_id,
                    action="access_revoked", detail=user.login if user else member_id))
    db.commit()
    return {"ok": True}

