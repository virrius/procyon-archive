from __future__ import annotations

from itertools import islice

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import cast, or_, String as SAString
from sqlalchemy.orm import Session

from ..api_schema import AUTH_ERRORS
from ..db import get_db
from ..deps import viewer
from ..i18n import tr
from ..models import (
    Clock,
    ContentBlock,
    Entity,
    Message,
    News,
)
from ..visibility import Viewer, apply_scope, can_see
from .entities import block_visible, parent_visible, peer_brief

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["search"], responses=AUTH_ERRORS)


class SearchHit(BaseModel):
    type: Literal["entity", "block", "message", "news"] = Field(description="What matched.")
    kind: str = Field(description="Entity kind, block type, message type or news byline - depends on `type`.")
    id: str = Field(description="Id of the matched row (for a block: the id of the entity/clock it sits on).")
    title: str
    snippet: str = Field(description="Up to 180 characters around the match.")
    status: str
    target_type: str = Field(description="Where it leads: `entity` | `clock` | `rule` | `message` | `news` | `marker` | `map`.")
    target_id: str


def block_shown(db: Session, v: Viewer, b: ContentBlock) -> bool:
    """Та же проверка, что у записей на странице карточки: сперва карточка, потом запись."""
    if not parent_visible(db, v, b.entity_type, b.entity_id):
        return False
    parent = db.get(Entity, b.entity_id) if b.entity_type == "entity" else None
    return block_visible(b, v, parent.owner_member_id if parent else None)


def block_target(db: Session, v: Viewer, b: ContentBlock) -> tuple[str, dict] | None:
    """Чьё имя стоит у записи в выдаче и куда она ведёт. None — вести некуда."""
    if b.entity_type in ("entity", "clock"):
        parent = db.get(Entity if b.entity_type == "entity" else Clock, b.entity_id)
        if parent is None or parent.campaign_id != v.campaign_id or not can_see(parent, v):
            return None
        return parent.name, {"target_type": b.entity_type, "target_id": parent.id}
    if b.entity_type == "rules" and b.block_type != "seed":
        # вырезка ведёт к себе самой, раздел — к себе; имя раздела — у вырезки
        section = db.get(ContentBlock, b.entity_id) if b.entity_id else None
        return (section.title if section else ""), {"target_type": "rule", "target_id": b.id}
    return None


@router.get("/search", summary="Find anything by text", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=2, description="Substring, case-insensitive; 2+ characters.", examples=["Varg"]),
    v: Viewer = Depends(viewer),
    db: Session = Depends(get_db),
    limit: int = Query(40, ge=1, le=200, description="Per result type; the answer holds at most 2 x limit rows."),
):
    """Substring search over entities (name, alias, summary; GM also over `fields`), content
    blocks, messages and news - filtered by what the viewer may see. The usual way to
    turn a name into an id; for entities alone `GET /entities?q=` returns full cards."""
    like = f"%{q}%"
    results: list[dict] = []

    eq = db.query(Entity).filter(Entity.campaign_id == v.campaign_id, ~Entity.archived)
    conds = [Entity.name.ilike(like), Entity.alias.ilike(like)]
    if v.is_gm:
        conds += [Entity.summary.ilike(like), cast(Entity.fields, SAString).ilike(like)]
    else:
        conds.append(Entity.summary.ilike(like) & ~Entity.hidden_fields.contains(["summary"]))
    for e in apply_scope(eq.filter(or_(*conds)), Entity, v).limit(limit).all():
        shown = peer_brief(e, v)
        results.append({
            "type": "entity", "kind": e.kind, "id": e.id, "title": e.name,
            "snippet": (shown["summary"] or "")[:180], "status": shown["status"],
            "target_type": "entity", "target_id": e.id,
        })

    bq = db.query(ContentBlock).filter(
        ContentBlock.campaign_id == v.campaign_id,
        or_(ContentBlock.title.ilike(like), ContentBlock.content.ilike(like)),
    )
    if not v.is_gm:
        bq = bq.filter(ContentBlock.visibility != "gm")
    for b in islice((b for b in bq if v.is_gm or block_shown(db, v, b)), limit):
        hit = block_target(db, v, b)
        if hit is None:
            continue
        owner, target = hit
        title = b.title or tr("misc.search.note")
        results.append({
            "type": "block", "kind": b.block_type, "id": b.entity_id,
            "title": f"{owner}: {title}" if owner else title,
            "snippet": "" if b.block_type == "shot" else b.content[:180],
            "status": "", **target,
        })

    mq = db.query(Message).filter(
        Message.campaign_id == v.campaign_id,
        or_(Message.subject.ilike(like), Message.body.ilike(like),
            Message.sender_display.ilike(like)),
    )
    if not v.is_gm:
        mq = mq.filter(Message.status.in_(["delivered", "archived"]))
    for m in apply_scope(mq, Message, v).limit(limit).all():
        results.append({
            "type": "message", "kind": m.msg_type, "id": m.id,
            "title": m.subject or tr("misc.search.from", name=m.sender_display),
            "snippet": m.body[:180], "status": m.status,
            "target_type": "message", "target_id": m.id,
        })

    wq = db.query(News).filter(
        News.campaign_id == v.campaign_id,
        or_(News.headline.ilike(like), News.body.ilike(like)),
    )
    for n in apply_scope(wq, News, v).limit(limit).all():
        results.append({
            "type": "news", "kind": n.byline, "id": n.id,
            "title": n.headline or tr("misc.search.from", name=n.byline), "snippet": n.body[:180], "status": "",
            "target_type": "news", "target_id": n.id,
        })

    return results[: limit * 2]
