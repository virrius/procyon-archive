from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class PK:
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uid)


class Stamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


# --- accounts -----------------------------------------------------------------


class User(Base, PK, Stamps):
    __tablename__ = "users"
    login: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # password was set by default (first admin): until it is changed, the API only allows /auth/me and /auth/password
    password_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # bumped on password change: tokens with an older version are no longer accepted
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class Campaign(Base, PK, Stamps):
    __tablename__ = "campaigns"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    # language of the starter content: canon, map, ship, rules clippings; what was created stays as is
    lang: Mapped[str] = mapped_column(String(5), default="")
    members: Mapped[list[CampaignMember]] = relationship(back_populates="campaign")

    # campaign wardrobe: {"wardrobe": {key: outfit}} — outfits from the table's good frames
    img_prompt_kit: Mapped[str] = mapped_column(Text, default="")
    # in-game time — days since 1261.1.1; year, week and weekday are derived from it
    world_day: Mapped[int] = mapped_column(Integer, default=0)
    # crew sheet setup on top of the book: {"common": [...], "playbooks": {key: {...}}}
    sheet_setup: Mapped[dict] = mapped_column(JSONB, default=dict)


class ServerSettings(Base):
    """Server settings shared by all campaigns: hub, models and prompts. One row with id "main"."""

    __tablename__ = "server_settings"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="main")
    hub_base_url: Mapped[str] = mapped_column(String(300), default="")
    hub_api_key: Mapped[str] = mapped_column(String(200), default="")
    img_model: Mapped[str] = mapped_column(String(100), default="")
    news_model: Mapped[str] = mapped_column(String(100), default="")
    # who draws: worker | api; hub_draw detects the service protocol from its response.
    # Empty drawing URL and key fall back to the text ones
    draw_kind: Mapped[str] = mapped_column(String(20), default="")
    draw_model: Mapped[str] = mapped_column(String(100), default="")
    draw_base_url: Mapped[str] = mapped_column(String(300), default="")
    draw_api_key: Mapped[str] = mapped_column(String(200), default="")
    # hub instructions: inpainting and the three directions; empty means the text from code
    img_inpaint_prompt: Mapped[str] = mapped_column(Text, default="")
    img_prose_person: Mapped[str] = mapped_column(Text, default="")
    img_prose_frame: Mapped[str] = mapped_column(Text, default="")
    img_prose_action: Mapped[str] = mapped_column(Text, default="")
    # kit overrides without the wardrobe: the wardrobe stays with the campaign
    img_prompt_kit: Mapped[str] = mapped_column(Text, default="")
    # instance language: UI and generation; empty means English
    lang: Mapped[str] = mapped_column(String(5), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CampaignMember(Base, PK, Stamps):
    __tablename__ = "campaign_members"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="player")  # gm|player|observer
    display_name: Mapped[str] = mapped_column(String(120), default="")
    campaign: Mapped[Campaign] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


# --- content ------------------------------------------------------------------


class VisMixin:
    """crew | selected | owner | gm"""

    visibility: Mapped[str] = mapped_column(String(20), default="crew")
    visible_to: Mapped[list] = mapped_column(JSONB, default=list)


class Entity(Base, PK, Stamps, VisMixin):
    """Generic record: person, npc, faction, ship, crew, location, item."""

    __tablename__ = "entities"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    alias: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    faction_ids: Mapped[list] = mapped_column(JSONB, default=list)
    location_ids: Mapped[list] = mapped_column(JSONB, default=list)
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    owner_member_id: Mapped[str | None] = mapped_column(String(64))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # what the GM has not revealed to players yet: entity column names and fields keys
    hidden_fields: Mapped[list] = mapped_column(JSONB, default=list)
    # generation form snapshot: direction, register, manner, slots, prompt. Lives on the
    # entity, not on the job: cancelling deletes the job, and the next frame is almost always
    # edited from the previous one. Not sent to the table: GM-only
    gen_form: Mapped[dict] = mapped_column(JSONB, default=dict)


class EntityLink(Base, PK, Stamps, VisMixin):
    """Directed link between two entities; every link carries its own visibility."""

    __tablename__ = "entity_links"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    from_id: Mapped[str] = mapped_column(String(64), index=True)
    to_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    created_by: Mapped[str | None] = mapped_column(String(64))


class ContentBlock(Base, PK, Stamps, VisMixin):
    __tablename__ = "content_blocks"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    block_type: Mapped[str] = mapped_column(String(30), default="text")
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_by_gm: Mapped[bool] = mapped_column(Boolean, default=False)
    edited_by: Mapped[str | None] = mapped_column(String(64))
    links: Mapped[list] = mapped_column(JSONB, default=list)  # ids of the entities the note is about


class Clock(Base, PK, Stamps, VisMixin):
    __tablename__ = "clocks"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(60), default="", index=True)  # type, set by the table
    color: Mapped[str] = mapped_column(String(20), default="amber")
    segments: Mapped[int] = mapped_column(Integer, default=6)
    filled: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    owner_type: Mapped[str | None] = mapped_column(String(30))
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # who may edit: '*' — any player, '' — GM only, otherwise a member id
    owner_member_id: Mapped[str] = mapped_column(String(64), default="*")


class Message(Base, PK, Stamps, VisMixin):
    __tablename__ = "messages"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    sender_display: Mapped[str] = mapped_column(String(200), default="UNKNOWN")
    sender_entity_id: Mapped[str | None] = mapped_column(String(64))
    # the link is usually backstage; the flag reveals the sender's entry to the table
    sender_reveal: Mapped[bool] = mapped_column(Boolean, default=False)
    msg_type: Mapped[str] = mapped_column(String(40), default="crew")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|delivered|archived
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[str] = mapped_column(String(80), default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # in-game day of the message (like Campaign.world_day)
    world_day: Mapped[int | None] = mapped_column(Integer, nullable=True)


class News(Base, PK, Stamps, VisMixin):
    """Sector news: a journalist's dispatch that the GM has put on air."""

    __tablename__ = "news"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    headline: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    byline: Mapped[str] = mapped_column(String(120), default="")
    journalist: Mapped[str] = mapped_column(String(60), default="")
    # the gist of the news as a summary; the GM can hide it from the table — then players work it out from the text
    lead: Mapped[str] = mapped_column(Text, default="")
    lead_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    # comments from net users: [{handle, who, text}]
    comments: Mapped[list] = mapped_column(JSONB, default=list)
    # in-game release day (like Campaign.world_day); empty means the news predates in-game time
    world_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # who and what the news is about: campaign entries and clocks
    entity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    clock_ids: Mapped[list] = mapped_column(JSONB, default=list)


class NewsJob(Base, PK, Stamps):
    """A dispatch order for a journalist: written in the background; drafts wait for the GM here
    until the GM puts them on air or discards them."""

    __tablename__ = "news_jobs"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ready|failed
    journalist: Mapped[str] = mapped_column(String(60), default="")
    gm_text: Mapped[str] = mapped_column(Text, default="")
    entity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    clock_ids: Mapped[list] = mapped_column(JSONB, default=list)
    lenses: Mapped[list] = mapped_column(JSONB, default=list)
    # [{lens, angle, headline, text, manual, aired, news_id, dropped}]
    drafts: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str] = mapped_column(Text, default="")


class MessageState(Base, PK):
    __tablename__ = "message_states"
    __table_args__ = (UniqueConstraint("message_id", "member_id"),)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(64), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class MapNode(Base, PK, Stamps, VisMixin):
    __tablename__ = "map_nodes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20), default="sector")
    image_url: Mapped[str] = mapped_column(String(500), default="")


class MapMarker(Base, PK, Stamps, VisMixin):
    __tablename__ = "map_markers"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    map_id: Mapped[str] = mapped_column(ForeignKey("map_nodes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    x: Mapped[float] = mapped_column(Float, default=0.5)
    y: Mapped[float] = mapped_column(Float, default=0.5)
    marker_type: Mapped[str] = mapped_column(String(30), default="location")
    icon: Mapped[str] = mapped_column(String(20), default="dot")
    label: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    linked_type: Mapped[str | None] = mapped_column(String(30))
    linked_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str | None] = mapped_column(String(64))


class MapStroke(Base, PK, Stamps, VisMixin):
    """Freehand marker stroke: normalised points, so the background can change."""

    __tablename__ = "map_strokes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    map_id: Mapped[str] = mapped_column(ForeignKey("map_nodes.id"), index=True)
    points: Mapped[list] = mapped_column(JSONB, default=list)
    color: Mapped[str] = mapped_column(String(20), default="amber")
    width: Mapped[int] = mapped_column(Integer, default=3)
    created_by: Mapped[str | None] = mapped_column(String(64))


class Board(Base, PK, Stamps):
    """Story board: the GM's canvas that collects cards, note clippings and
    free notes tied with threads. GM-only — never sent to the table, so
    neither the board nor its cards have visibility."""

    __tablename__ = "boards"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))


class BoardCard(Base, PK, Stamps):
    """A card on the board: entity — an entry thumbnail with key notes, text —
    a free sticky note, image — a frame used as evidence, clock — a live campaign clock,
    sketch — a field the GM draws on by hand, name — an extra (one-scene NPC): name
    and description, not stored in the campaign database. Coordinates are in canvas units
    (not fractions: the canvas is infinite, with no background under it)."""

    __tablename__ = "board_cards"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id"), index=True)
    # human-readable key within the board: used to address the card in the snapshot and in
    # batch edits instead of a uuid ("gregor-varg", "ulika-manifest")
    key: Mapped[str] = mapped_column(String(64), default="", index=True)
    kind: Mapped[str] = mapped_column(String(20), default="text")
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # a clock lives its own life in the campaign: the board holds only a link to it
    clock_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # notes attached to a card on the board: [{id, text, tag}]. They go into the campaign
    # entry itself as one block, grouped by tag
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    # id of that block: edits go into it instead of spawning new notes
    block_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str] = mapped_column(String(20), default="amber")
    # text field font size: a board caption can be a small mark or a heading
    font_size: Mapped[int] = mapped_column(Integer, default=14)
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    w: Mapped[float] = mapped_column(Float, default=240.0)
    # height is set manually only for fields where it can't be derived from the content
    # (sketch); for other cards the browser computes the height from the text
    h: Mapped[float] = mapped_column(Float, default=0.0)
    # sketch strokes: [{color, width, pts: [x, y, ...]}] in card coordinates
    ink: Mapped[list] = mapped_column(JSONB, default=list)
    collapsed: Mapped[bool] = mapped_column(Boolean, default=False)
    z: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64))


class BoardEdge(Base, PK, Stamps):
    """A thread between cards: like the red string on a detective's board."""

    __tablename__ = "board_edges"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id"), index=True)
    from_card_id: Mapped[str] = mapped_column(String(64), index=True)
    to_card_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    color: Mapped[str] = mapped_column(String(20), default="rust")
    style: Mapped[str] = mapped_column(String(20), default="thread")
    created_by: Mapped[str | None] = mapped_column(String(64))


class Attachment(Base, PK, Stamps, VisMixin):
    __tablename__ = "attachments"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    target_type: Mapped[str | None] = mapped_column(String(30), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    caption: Mapped[str] = mapped_column(String(300), default="")
    uploaded_by: Mapped[str | None] = mapped_column(String(64))
    # preview box in original-image pixels, "x,y,w,h"; empty means a preview of the whole frame.
    # The file is not cut when cropping: thumbnails use the box, full size uses the original
    crop_box: Mapped[str] = mapped_column(String(60), default="")


class ImageGenJob(Base, PK, Stamps):
    """Portrait generation job: the GM sets a prompt, the local worker polls,
    brings 4 candidates, the GM picks one and the rest are deleted. Lives until picked/cancelled,
    so it can be minimized (window closed) and resumed later — the status survives
    closing the modal on the frontend."""

    __tablename__ = "image_gen_jobs"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    # empty means the job is not tied to an entity (a campaign frame, the Campaign frames screen)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # txt2img — draw from scratch; inpaint — redraw an area of an existing image by a
    # mask. The latter brings along a source, a mask and a different graph in the worker
    kind: Mapped[str] = mapped_column(String(20), default="txt2img", index=True)
    # inpaint: what we edit and with which mask (the mask is its own attachment, target_id = job id)
    source_attachment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # the part of the source actually sent to the model: "x,y,w,h" in coordinates of the
    # prepared copy. Empty means the whole frame is edited (the mask covers almost all of it)
    crop_box: Mapped[str] = mapped_column(String(60), default="")
    # when the worker claimed the job and which attempt this is: a lost worker shows only
    # through these two fields — otherwise the job hangs in claimed forever (see reap_stale_jobs)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # 1.0 — repaint the area from scratch, lower — touch it up, keeping the original shape
    denoise: Mapped[float] = mapped_column(Float, default=1.0)
    prompt: Mapped[str] = mapped_column(Text, default="")
    width: Mapped[int] = mapped_column(Integer, default=768)
    height: Mapped[int] = mapped_column(Integer, default=960)
    n_images: Mapped[int] = mapped_column(Integer, default=4)
    # per-job seed: two prompt builds are comparable only if the noise under them is the same
    seed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(64))
    # the attempt's branches and slots: the Studio feed shows what it was built from
    params: Mapped[dict] = mapped_column(JSONB, default=dict)


class Event(Base, PK):
    """Campaign log: who changed what and when. Written on every edit
    (see history.log), so it survives deletion of the record itself — unlike
    row created_at/updated_at. `before`/`after` hold only the changed keys."""

    __tablename__ = "events"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    actor_member_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_name: Mapped[str] = mapped_column(String(120), default="")
    by_gm: Mapped[bool] = mapped_column(Boolean, default=False)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    target_title: Mapped[str] = mapped_column(String(200), default="")
    # the entry the feed links to (an entry, note or clock links to its own)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(String(400), default="")
    visibility: Mapped[str] = mapped_column(String(20), default="")
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class AuditLog(Base, PK):
    __tablename__ = "audit_log"
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
