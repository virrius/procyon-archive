from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, VISIBLE_TO_DOC, Ok, Visibility, default_visibility, vis_field
from ..db import get_db
from ..deps import editor, viewer
from ..i18n import ctr, tr
from ..models import Attachment, Campaign, Entity, Message, MessageState
from ..visibility import Viewer, apply_scope, can_see

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["messages"], responses=AUTH_ERRORS)

MessageType = Literal[
    "personal", "crew", "job offer", "bounty", "HNN news", "system alert",
    "intercepted", "faction", "anonymous", "ship warning", "document",
]
MessageStatus = Literal["draft", "delivered", "archived"]

STATUS_DOC = (
    "`draft` — only the GM sees it; `delivered` — in the crew's inbox (sets `delivered_at`, journal `deliver`); "
    "`archived` — kept but out of the inbox."
)
SENDER_DOC = "Entity behind the sender (NPC, faction). Hidden from players unless `sender_reveal` is true."


class MessageIn(BaseModel):
    sender_display: str = Field("UNKNOWN", description="Sender name as the crew sees it.", examples=["Harbour Authority"])
    sender_entity_id: str | None = Field(None, description=SENDER_DOC)
    sender_reveal: bool = Field(False, description="Show the sender's entity card to the crew.")
    msg_type: MessageType = Field("crew", description="Flavour of the message; drives the inbox styling.")
    subject: str = Field("", examples=["Docking fees overdue"])
    body: str = Field("", description="Message text (plain text, line breaks kept).")
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field([], description=VISIBLE_TO_DOC)
    is_lead: bool = Field(False, description="Mark as a lead (a hook the crew may follow).")
    expires_at: str = Field("", description="Free-text in-fiction deadline shown to the crew.")
    status: MessageStatus = Field("delivered", description=STATUS_DOC)
    world_day: int | None = Field(default=None, ge=0, description="Game day of the message; omitted → the campaign's current day.")


NULLABLE = ("sender_entity_id", "world_day")


class MessagePatch(BaseModel):
    """Only the keys sent are changed; `null` is ignored except on `sender_entity_id` and `world_day`.
    `status: delivered` behaves exactly like `POST …/deliver`."""

    sender_display: str | None = None
    sender_entity_id: str | None = Field(None, description=SENDER_DOC)
    sender_reveal: bool | None = None
    msg_type: MessageType | None = None
    subject: str | None = None
    body: str | None = None
    visibility: Visibility | None = Field(None, description="New audience.")
    visible_to: list[str] | None = Field(None, description=VISIBLE_TO_DOC)
    is_lead: bool | None = None
    expires_at: str | None = None
    status: MessageStatus | None = Field(None, description=STATUS_DOC)
    world_day: int | None = Field(default=None, ge=0)


class StateIn(BaseModel):
    read: bool | None = Field(None, description="Mark read (true) or unread (false) for the calling member.")
    pinned: bool | None = Field(None, description="Pin or unpin for the calling member.")


class SenderCard(BaseModel):
    id: str
    name: str
    kind: str
    image_url: str


class MessageOut(BaseModel):
    id: str
    sender_display: str
    msg_type: str
    subject: str
    body: str
    status: MessageStatus
    is_lead: bool
    expires_at: str
    delivered_at: datetime | None
    created_at: datetime
    world_day: int | None
    read: bool = Field(description="Read by the calling member (per-member state; false right after POST/PATCH).")
    pinned: bool = Field(description="Pinned by the calling member.")
    sender_reveal: bool
    sender_card: SenderCard | None = Field(description="The sender's entity, when revealed to the crew.")
    visibility: Visibility | None = Field(None, description="Present for the GM only.")
    visible_to: list[str] | None = Field(None, description="Present for the GM only.")
    sender_entity_id: str | None = Field(None, description="Present for the GM only.")


class MessageAttachmentOut(BaseModel):
    id: str
    filename: str
    url: str = Field(description="Stored file name; fetch the bytes via `GET …/files/{id}`.")
    mime: str
    caption: str


def _card(db: Session, m: Message) -> dict | None:
    """Карточка отправителя для стола — только когда ГМ раскрыл привязку."""
    if not (m.sender_reveal and m.sender_entity_id):
        return None
    e = db.get(Entity, m.sender_entity_id)
    if not e or e.campaign_id != m.campaign_id:
        return None
    return {"id": e.id, "name": e.name, "kind": e.kind, "image_url": e.image_url}


def _out(m: Message, v: Viewer, state: MessageState | None, card: dict | None = None) -> dict:
    d = {
        "id": m.id, "sender_display": m.sender_display, "msg_type": m.msg_type,
        "subject": m.subject, "body": m.body,
        "status": m.status, "is_lead": m.is_lead, "expires_at": m.expires_at,
        "delivered_at": m.delivered_at, "created_at": m.created_at, "world_day": m.world_day,
        "read": bool(state and state.read_at), "pinned": bool(state and state.pinned),
        "sender_reveal": m.sender_reveal, "sender_card": card,
    }
    if v.is_gm:
        d["visibility"] = m.visibility
        d["visible_to"] = m.visible_to or []
        d["sender_entity_id"] = m.sender_entity_id
    return d


def _deliver(db: Session, v: Viewer, m: Message) -> None:
    """Одна дорога в «доставлено» — и для PATCH status, и для /deliver."""
    m.status = "delivered"
    m.delivered_at = datetime.now(timezone.utc)
    journal.log(db, v, "message", "deliver", target_id=m.id,
                title=m.subject or ctr("content.no_subject"), detail=ctr("content.from", who=m.sender_display),
                visibility=m.visibility)


@router.get("/messages", summary="List messages", response_model=list[MessageOut])
def list_messages(
    v: Viewer = Depends(viewer), db: Session = Depends(get_db),
    include_drafts: bool = Query(True, description="GM only: include `draft` messages. Players never see drafts."),
    limit: int | None = Query(None, ge=1, description="Page size; omitted → all."),
    offset: int = Query(0, ge=0),
):
    """Messages visible to the viewer, newest first, with the caller's own read/pinned state."""
    q = db.query(Message).filter(Message.campaign_id == v.campaign_id)
    if not v.is_gm or not include_drafts:
        q = q.filter(Message.status.in_(["delivered", "archived"]))
    q = apply_scope(q, Message, v).order_by(Message.created_at.desc()).offset(offset)
    rows = (q.limit(limit) if limit else q).all()
    states = {
        s.message_id: s
        for s in db.query(MessageState).filter(MessageState.member_id == v.member_id).all()
    }
    ids = {m.sender_entity_id for m in rows if m.sender_reveal and m.sender_entity_id}
    cards = {
        e.id: {"id": e.id, "name": e.name, "kind": e.kind, "image_url": e.image_url}
        for e in (
            db.query(Entity)
            .filter(Entity.campaign_id == v.campaign_id, Entity.id.in_(ids)).all()
            if ids else []
        )
    }
    return [
        _out(m, v, states.get(m.id),
             cards.get(m.sender_entity_id) if m.sender_reveal else None)
        for m in rows
    ]


@router.post("/messages", summary="Compose a message", response_model=MessageOut)
def create_message(body: MessageIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM only (403 otherwise): in-fiction mail is written by the GM. Omitted `visibility` → `gm`;
    omitted `world_day` → the campaign's current day. `status: delivered` (the default) sets `delivered_at`.
    Journal: `create`."""
    if not v.is_gm:
        raise HTTPException(403, tr("comms.gm_composes"))
    data = body.model_dump()
    data["visibility"] = default_visibility(v, body.visibility)
    m = Message(campaign_id=v.campaign_id, **data)
    if m.world_day is None:
        m.world_day = db.get(Campaign, v.campaign_id).world_day
    if m.status == "delivered":
        m.delivered_at = datetime.now(timezone.utc)
    db.add(m)
    db.flush()
    journal.log(db, v, "message", "create", target_id=m.id, title=m.subject or ctr("content.no_subject"),
                detail=ctr("content.from", who=m.sender_display), visibility=m.visibility,
                after={"subject": m.subject, "body": m.body, "status": m.status})
    db.commit()
    return _out(m, v, None, _card(db, m))


def _get(db: Session, v: Viewer, mid: str) -> Message:
    m = db.get(Message, mid)
    if not m or m.campaign_id != v.campaign_id or not can_see(m, v):
        raise HTTPException(404, tr("comms.not_found"))
    if not v.is_gm and m.status == "draft":
        raise HTTPException(404, tr("comms.not_found"))
    return m


@router.patch("/messages/{message_id}", summary="Edit a message", response_model=MessageOut)
def patch_message(
    message_id: str, body: MessagePatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """GM only. Only the keys sent are changed. Changing `status` to `delivered` is the same as
    `POST …/deliver` (sets `delivered_at`, journal `deliver`); other changes write an `update` entry."""
    if not v.is_gm:
        raise HTTPException(403, tr("comms.gm_only"))
    m = _get(db, v, message_id)
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items()
             if val is not None or k in NULLABLE}
    deliver = patch.get("status") == "delivered" and m.status != "delivered"
    if deliver:
        patch.pop("status")
    before, after = journal.changes(m, patch)
    for k, val in patch.items():
        setattr(m, k, val)
    if after:
        journal.log(db, v, "message", "update", target_id=m.id,
                    title=m.subject or ctr("content.no_subject"), detail=ctr("content.from", who=m.sender_display),
                    visibility=m.visibility, before=before, after=after)
    if deliver:
        _deliver(db, v, m)
    db.commit()
    return _out(m, v, None, _card(db, m))


@router.post("/messages/{message_id}/deliver", summary="Deliver a message to the crew", response_model=MessageOut)
def deliver_message(message_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM only. Status → `delivered`, `delivered_at` = now, journal `deliver`.
    Identical to `PATCH` with `{"status": "delivered"}`. The crew sees it only if `visibility` allows."""
    if not v.is_gm:
        raise HTTPException(403, tr("comms.gm_only"))
    m = _get(db, v, message_id)
    _deliver(db, v, m)
    db.commit()
    return _out(m, v, None, _card(db, m))


@router.delete("/messages/{message_id}", summary="Delete a message", response_model=Ok)
def delete_message(message_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM only. Deletes the message, its per-member states and its attachments. Journal: `delete`."""
    if not v.is_gm:
        raise HTTPException(403, tr("comms.gm_only"))
    m = _get(db, v, message_id)
    db.query(MessageState).filter_by(message_id=m.id).delete()
    db.query(Attachment).filter_by(
        campaign_id=v.campaign_id, target_type="message", target_id=m.id
    ).delete()
    journal.log(db, v, "message", "delete", target_id=m.id,
                title=m.subject or ctr("content.no_subject"), detail=ctr("content.from", who=m.sender_display),
                visibility=m.visibility, before={"subject": m.subject, "body": m.body})
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/messages/{message_id}/state", summary="Set read/pinned for yourself", response_model=Ok)
def set_message_state(
    message_id: str, body: StateIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Per-member flags on a message the caller can see; omitted keys are left as they are. Not journaled."""
    m = _get(db, v, message_id)
    st = (
        db.query(MessageState)
        .filter_by(message_id=m.id, member_id=v.member_id)
        .one_or_none()
    )
    if not st:
        st = MessageState(message_id=m.id, member_id=v.member_id)
        db.add(st)
    if body.read is not None:
        st.read_at = datetime.now(timezone.utc) if body.read else None
    if body.pinned is not None:
        st.pinned = body.pinned
    db.commit()
    return {"ok": True}


@router.get("/messages/{message_id}/attachments", summary="List a message's attachments",
            response_model=list[MessageAttachmentOut])
def message_attachments(
    message_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)
):
    """Attachments of a message the viewer can see, filtered by each attachment's own visibility.
    Upload one with `POST …/upload` using `target_type=message`."""
    _get(db, v, message_id)
    q = db.query(Attachment).filter_by(
        campaign_id=v.campaign_id, target_type="message", target_id=message_id
    )
    return [
        {"id": a.id, "filename": a.filename, "url": a.url, "mime": a.mime, "caption": a.caption}
        for a in apply_scope(q, Attachment, v).all()
    ]
