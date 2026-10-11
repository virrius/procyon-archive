from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from ..api_schema import AUTH_ERRORS
from ..db import get_db
from ..deps import gm_only
from ..models import AuditLog, CampaignMember, Entity, Event, User
from ..visibility import Viewer
from .entities import UUID_RE

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["history"], responses=AUTH_ERRORS)

# источники ленты: журнал правок (events) + учётные действия (audit_log)
SOURCES = ("entity", "block", "note", "clock", "message", "news", "marker", "map", "link",
           "file", "rules", "board", "account")
PAGE = 60
PAGE_MAX = 200


def _cursor(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _wanted(raw: str | None) -> set[str]:
    picked = {s.strip() for s in (raw or "").split(",") if s.strip()}
    return {s for s in picked if s in SOURCES} or set(SOURCES)


def _audit_scope(campaign_id: str, members: list[CampaignMember]):
    """Учётные события кампании. Вход и смена пароля пишутся без кампании — их берём
    только у её участников; входы ГМа-админа в каждую кампанию — шум, их не берём."""
    users = [str(m.user_id) for m in members]
    admins = [str(m.user_id) for m in members if m.user is not None and m.user.is_admin]
    loose = and_(AuditLog.campaign_id.is_(None), AuditLog.user_id.in_(users))
    if admins:
        loose = and_(loose, not_(and_(AuditLog.action == "login", AuditLog.user_id.in_(admins))))
    return or_(AuditLog.campaign_id == campaign_id, loose)


def _event_row(e: Event, entity_names: dict[str, str]) -> dict:
    return {
        "id": e.id,
        "at": e.created_at,
        "source": e.source,
        "action": e.action,
        "actor_id": e.actor_member_id,
        "actor": e.actor_name,
        "by_gm": e.by_gm,
        "title": e.target_title,
        "target_id": e.target_id,
        "entity_id": e.entity_id,
        "entity_name": entity_names.get(e.entity_id or "", ""),
        "detail": e.detail,
        "visibility": e.visibility,
        "before": e.before or {},
        "after": e.after or {},
    }


def _audit_row(a: AuditLog, users: dict[str, str]) -> dict:
    return {
        "id": a.id,
        "at": a.created_at,
        "source": "account",
        "action": a.action,
        "actor_id": None,
        "actor": users.get(a.user_id or "", ""),
        "by_gm": False,
        "title": a.detail,
        "target_id": "",
        "entity_id": None,
        "entity_name": "",
        "detail": "",
        "visibility": "",
        "before": {},
        "after": {},
    }


class HistoryEvent(BaseModel):
    id: str
    at: datetime
    source: str = Field(description="`entity` | `block` | `note` | `clock` | `message` | `news` | `marker` | `map` | `link` | `file` | `rules` | `board` | `account`.")
    action: str = Field(description="`create` | `update` | `delete` | `archive` | `purge` | `tick` | `deliver` | ... (per source); for `account`: `login`, `password_reset`, `account_blocked`, ....")
    actor_id: str | None = Field(description="Member id of who did it; null for account events.")
    actor: str = Field(description="Display name at the time.")
    by_gm: bool
    title: str = Field(description="Name of the changed row at the time.")
    target_id: str
    entity_id: str | None = Field(description="Card the event belongs to (for blocks, links, notes); the entity itself for entity events.")
    entity_name: str
    detail: str
    visibility: str = Field(description="Visibility of the row when the event was written - what the table could see.")
    before: dict = Field(description="Changed keys with their old values.")
    after: dict = Field(description="Changed keys with their new values.")


class HistoryMember(BaseModel):
    id: str
    name: str


class HistoryPage(BaseModel):
    events: list[HistoryEvent] = Field(description="Newest first.")
    next: datetime | None = Field(description="Pass as `before` to get the next page; null - nothing older.")
    members: list[HistoryMember] = Field(description="Members of the campaign, for filtering by `member`.")


@router.get("/history", summary="Campaign journal (GM)", response_model=HistoryPage)
def list_history(
    v: Viewer = Depends(gm_only),
    db: Session = Depends(get_db),
    source: str | None = Query(default=None, description="Comma-separated sources to include (see `events[].source`); default all."),
    member: str | None = Query(default=None, description="Member id of the actor."),
    action: str | None = Query(default=None, description="Exact action name."),
    q: str | None = Query(default=None, description="Substring in title or detail."),
    before: str | None = Query(default=None, description="Cursor: ISO timestamp from the previous page's `next`."),
    limit: int = Query(PAGE, ge=1, le=PAGE_MAX),
):
    """Who changed what, newest first. GM only: it includes rows the table cannot see, and
    `X-View-As` does not filter it — players have no journal (403). Each event records the
    row's visibility at the time. Pages go by time cursor: repeat the call with
    `before=<next>` until `next` is null."""
    cur = _cursor(before)
    want = _wanted(source)
    members = db.query(CampaignMember).filter_by(campaign_id=v.campaign_id).all()
    author = next((m for m in members if m.id == member), None) if member else None

    rows: list[dict] = []
    if want - {"account"}:
        eq = db.query(Event).filter(Event.campaign_id == v.campaign_id)
        eq = eq.filter(Event.source.in_(sorted(want - {"account"})))
        if member:
            eq = eq.filter(Event.actor_member_id == member)
        if action:
            eq = eq.filter(Event.action == action)
        if q:
            like = f"%{q.strip()}%"
            eq = eq.filter(or_(Event.target_title.ilike(like), Event.detail.ilike(like)))
        if cur:
            eq = eq.filter(Event.created_at < cur)
        events = eq.order_by(Event.created_at.desc()).limit(limit).all()
        ids = {e.entity_id for e in events if e.entity_id and UUID_RE.fullmatch(e.entity_id)}
        names = {
            e.id: e.name
            for e in (
                db.query(Entity).filter(Entity.id.in_(ids)).all() if ids else []
            )
        }
        rows += [_event_row(e, names) for e in events]

    if "account" in want and (author or not member):
        aq = db.query(AuditLog).filter(_audit_scope(v.campaign_id, members))
        if author:
            aq = aq.filter(AuditLog.user_id == str(author.user_id))
        if action:
            aq = aq.filter(AuditLog.action == action)
        if q:
            aq = aq.filter(AuditLog.detail.ilike(f"%{q.strip()}%"))
        if cur:
            aq = aq.filter(AuditLog.created_at < cur)
        audits = aq.order_by(AuditLog.created_at.desc()).limit(limit).all()
        uids = {a.user_id for a in audits if a.user_id}
        users = {
            u.id: (u.display_name or u.login)
            for u in (db.query(User).filter(User.id.in_(uids)).all() if uids else [])
        }
        rows += [_audit_row(a, users) for a in audits]

    rows.sort(key=lambda r: r["at"], reverse=True)
    page = rows[:limit]
    return {
        "events": page,
        # курсор следующей страницы: пусто — лента дочитана до конца
        "next": page[-1]["at"] if len(page) == limit else None,
        "members": [
            {"id": m.id, "name": m.display_name or (m.user.display_name if m.user else "")}
            for m in members
        ],
    }
