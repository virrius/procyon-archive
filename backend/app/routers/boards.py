from __future__ import annotations

import re

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, Ok, error_responses
from ..db import get_db
from ..deps import gm_only
from ..i18n import ctr, tr
from ..models import Board, BoardCard, BoardEdge, Clock, ContentBlock, Entity
from ..langpack import names as N
from ..translit import slugify

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["boards"], responses=AUTH_ERRORS)

CARD_KINDS = ("entity", "text", "image", "clock", "sketch", "name")
EDGE_STYLES = ("thread", "dashed", "arrow")

CardKind = Literal["entity", "text", "image", "clock", "sketch", "name"]
EdgeStyle = Literal["thread", "dashed", "arrow"]
Color = Literal["amber", "rust", "steel", "plum", "olive", "white", "black"]

KIND_DOC = (
    "`entity` — a record of the campaign (needs `entity_id`); `clock` — a live clock (needs `clock_id`); "
    "`text` — a sticky note; `image` — a frame or picture; `sketch` — freehand field (`ink`); "
    "`name` — a walk-on NPC: name and description that never enter the campaign records."
)
NOTES_DOC = (
    "Sticky notes pinned to the card: `[{id?, text, tag}]`. On entity and clock cards they are also "
    "written into the record itself as one GM-only block titled after the board (`Board: <name>`), grouped by tag."
)
INK_DOC = (
    "Sketch content: strokes `{color, width, pts: [x, y, x, y, …]}` in card coordinates and labels "
    "`{kind: 'text', text, x, y, color, size}`. At most 400 items, 2000 points per stroke."
)

# Сетка холста. Внутри всё живёт в единицах холста, но наружу (снимок доски,
# пакетная правка) координаты ходят клетками: так раскладку можно описать словами,
# не считая пиксели.
COL = 40.0
ROW = 40.0
# высота карточки складывается из текста и известна только браузеру; для
# авторазмещения хватает грубой оценки в клетках
ROWS_BY_KIND = {"entity": 5, "clock": 4, "image": 6, "text": 3, "sketch": 8,
                "name": 3}
DEF_W = {"entity": 520.0, "text": 230.0, "image": 260.0, "clock": 230.0,
         "sketch": 420.0, "name": 260.0}



# росчерк — ломаная в координатах карточки, подпись — точка с текстом. Ограничения
# не про вкус: одно поле не должно разрастись в мегабайты — доска ходит целиком
MAX_STROKES = 400
MAX_POINTS = 2000


def norm_ink(ink: list | None) -> list[dict]:
    """Содержимое наброска: росчерк {color, width, pts} (точки — плоский список
    x, y) или подпись {kind: text, x, y, text, color, size}."""
    out: list[dict] = []
    for item in (ink or [])[:MAX_STROKES]:
        if not isinstance(item, dict):
            continue
        color = str(item.get("color") or "amber")[:20]
        if item.get("kind") == "text":
            text = str(item.get("text") or "").strip()[:200]
            if not text:
                continue
            out.append({
                "kind": "text", "text": text, "color": color,
                "x": round(float(item.get("x") or 0.0), 1),
                "y": round(float(item.get("y") or 0.0), 1),
                "size": max(8, min(160, int(item.get("size") or 16))),
            })
            continue
        pts = [
            round(float(v), 1)
            for v in (item.get("pts") or [])[:MAX_POINTS * 2]
            if isinstance(v, (int, float))
        ]
        if len(pts) < 2:
            continue
        out.append({
            "color": color,
            "width": max(1, min(40, int(item.get("width") or 2))),
            "pts": pts[: len(pts) // 2 * 2],
        })
    return out


def card_name(card: BoardCard, entity: Entity | None, clock: Clock | None) -> str:
    """Как карточка зовётся вслух: имя записи, имя счётчика или начало текста."""
    if entity is not None:
        return entity.name
    if clock is not None:
        return clock.name
    if card.title or card.body:
        return (card.title or card.body).strip().splitlines()[0][:60]
    if card.kind == "sketch":
        return ctr("content.sketch")
    return ctr("content.extra") if card.kind == "name" else ""


def unique_key(base: str, taken: set[str]) -> str:
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def fill_keys(cards: list[BoardCard], entities: dict, clocks: dict) -> None:
    """Ключ карточке, у которой его нет: по имени записи, счётчика или началу текста."""
    taken = {c.key for c in cards if c.key}
    for card in cards:
        if card.key:
            continue
        card.key = unique_key(slugify(card_name(card, entities.get(card.entity_id or ""),
                                                clocks.get(card.clock_id or "")), card.kind), taken)
        taken.add(card.key)


def block_title(board: Board) -> str:
    return ctr("content.board", name=board.name)


MARKUP = [
    re.compile(r"\*\*(?!\s)(.+?)(?<!\s)\*\*(?!\*)"),
    re.compile(r"__(?!\s)(.+?)(?<!\s)__(?!_)"),
    re.compile(r"(?<!\*)\*(?![\s*])([^*\n]*?[^\s*]|[^\s*])\*(?!\*)"),
]


def plain(text: str) -> str:
    """Выделение с доски (**жирный**, *курсив*, __подчёркнутый__) записи не нужно."""
    for rx in MARKUP:
        text = rx.sub(r"\1", text)
    return text


def compose_notes(notes: list | None) -> str:
    """Записки доски одним текстом: сперва без тега, дальше — группами по тегу."""
    groups: dict[str, list[str]] = {}
    for note in notes or []:
        if not isinstance(note, dict):
            continue
        body = plain(str(note.get("text") or "")).strip()
        if not body:
            continue
        groups.setdefault(str(note.get("tag") or "").strip(), []).append(body)
    parts: list[str] = []
    for tag in sorted(groups, key=lambda t: (t != "", t.lower())):
        lines = [f"• {body}" for body in groups[tag]]
        parts.append("\n".join([f"[{tag}]", *lines] if tag else lines))
    return "\n\n".join(parts)


def note_target(card: BoardCard) -> tuple[str, str] | None:
    """К чему записки карточки прирастают в кампании: запись или счётчик."""
    if card.kind == "entity" and card.entity_id:
        return "entity", card.entity_id
    if card.kind == "clock" and card.clock_id:
        return "clock", card.clock_id
    return None


def sync_block(db: Session, v, card: BoardCard, board: Board) -> None:
    """Записки, привязанные к карточке на доске, живут и в самой записи (или в
    счётчике) — одним блоком под именем доски. Пусто — блок убирается."""
    target = note_target(card)
    if target is None:
        return
    kind, target_id = target
    block = db.get(ContentBlock, card.block_id) if card.block_id else None
    if block is not None and block.campaign_id != v.campaign_id:
        block = None
    text = compose_notes(card.notes)
    if not text:
        if block is not None:
            db.delete(block)
        card.block_id = None
        return
    if block is None:
        block = ContentBlock(
            campaign_id=v.campaign_id, entity_type=kind, entity_id=target_id,
            block_type="text", created_by=v.member_id, created_by_gm=True,
            visibility="gm", visible_to=[],
        )
        db.add(block)
        db.flush()
        card.block_id = block.id
    block.entity_type = kind
    block.entity_id = target_id
    block.title = block_title(board)
    block.content = text
    block.edited_by = v.member_id


class BoardIn(BaseModel):
    name: str = Field(description="Board title.", examples=["The cargo case"])
    summary: str = Field(default="", description="One line about what the board is for.")
    order: int = Field(default=0, description="Position in the board list; lower first.")


class BoardPatch(BaseModel):
    """Only the keys sent are changed. Renaming also retitles the `Board: <name>` blocks written from its cards."""

    name: str | None = None
    summary: str | None = None
    order: int | None = None
    archived: bool | None = Field(default=None, description="Archived boards drop out of the list but keep their cards.")


class CardIn(BaseModel):
    board_id: str = Field(description="Board the card goes on (`GET /boards`).")
    kind: CardKind = Field(default="text", description=KIND_DOC)
    entity_id: str | None = Field(default=None, description="Required for `entity`; ignored otherwise.")
    clock_id: str | None = Field(default=None, description="Required for `clock`; ignored otherwise.")
    title: str = Field(default="", description="Caption (image cards, headings).")
    body: str = Field(default="", description="Text of a `text` or `name` card. `**bold**`, `*italic*`, `__underline__` allowed.")
    notes: list[dict] = Field(default=[], description=NOTES_DOC)
    image_url: str = Field(default="", description="Picture url for `image` cards (an uploaded file's `url`).")
    color: Color = Field(default="amber")
    font_size: int = Field(default=14, description="Text size 10..240 for `text` cards.")
    x: float = Field(default=0.0, description="Canvas units; the canvas is unbounded, one grid cell = 40 units.")
    y: float = Field(default=0.0, description="Canvas units.")
    w: float = Field(default=240.0, description="Width in canvas units.")
    h: float = Field(default=0.0, description="Height in canvas units; 0 = fit to content (only sketches set it).")
    ink: list[dict] = Field(default=[], description=INK_DOC)


class CardPatch(BaseModel):
    """Only the keys sent are changed. Changing `notes`, `entity_id` or `clock_id` re-syncs the card's record block."""

    kind: CardKind | None = None
    entity_id: str | None = None
    clock_id: str | None = None
    title: str | None = None
    body: str | None = None
    notes: list[dict] | None = Field(default=None, description=NOTES_DOC + " Replaces the whole list.")
    image_url: str | None = None
    color: Color | None = None
    font_size: int | None = Field(default=None, description="Clamped to 10..240.")
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = Field(default=None, description="Clamped to 0..4000.")
    ink: list[dict] | None = Field(default=None, description=INK_DOC)
    collapsed: bool | None = Field(default=None, description="Folded to its title.")
    z: int | None = Field(default=None, description="Stacking order; higher is on top.")


class EdgeIn(BaseModel):
    board_id: str
    from_card_id: str = Field(description="Card id (not key) on the same board.")
    to_card_id: str = Field(description="Card id on the same board; must differ from `from_card_id`.")
    label: str = Field(default="", description="Caption on the thread.", examples=["seen together"])
    color: Color = Field(default="rust")
    style: EdgeStyle = Field(default="thread", description="`thread` plain, `dashed`, `arrow` with a head at `to`.")


class EdgePatch(BaseModel):
    label: str | None = None
    color: Color | None = None
    style: EdgeStyle | None = None


# --- output -------------------------------------------------------------------


class BoardOut(BaseModel):
    id: str
    name: str
    summary: str
    order: int
    card_count: int
    archived: bool = False
    updated_at: datetime


class CreatedOut(BaseModel):
    id: str


class EdgeCreatedOut(BaseModel):
    id: str
    existing: bool = Field(default=False, description="`true` when the pair was already linked: that thread's id is returned, nothing is created.")


class CardEntityOut(BaseModel):
    id: str
    kind: str
    name: str
    alias: str
    summary: str
    image_url: str
    status: str
    rank: str = Field(description="`fields.rank` of the record as a string; empty when unset.")


class CardClockOut(BaseModel):
    id: str
    name: str
    segments: int
    filled: int
    color: str
    status: str
    kind: str
    description: str
    outcome: str
    owner_type: str | None = Field(default=None, description="`entity` when the clock belongs to a card.")
    owner_id: str | None = Field(default=None, description="Id of the owning card.")
    owner_name: str = Field(description="Name of the entity the clock belongs to; empty when none.")
    visibility: str


class BoardCardOut(BaseModel):
    id: str
    board_id: str
    kind: CardKind
    key: str = Field(description="Human key within the board (`gregor-varg`) used by the boards-agent layer.")
    entity_id: str | None
    clock_id: str | None
    title: str
    body: str
    notes: list[dict]
    image_url: str
    color: str
    font_size: int
    x: float
    y: float
    w: float
    h: float
    ink: list[dict]
    collapsed: bool
    z: int
    entity: CardEntityOut | None = Field(description="Resolved record for `entity` cards.")
    clock: CardClockOut | None = Field(description="Resolved clock for `clock` cards.")


class BoardEdgeOut(BaseModel):
    id: str
    board_id: str
    from_card_id: str
    to_card_id: str
    label: str
    color: str
    style: str


class RolledNameOut(BaseModel):
    name: str = Field(description="Ready to use: first name, family name and alias joined.")
    shape: str
    first: str
    family: str
    alias: str
    country: str = Field(description="Country key for the world pool; empty for the setting pool.")
    gender: str | None = Field(default=None, description="`f`/`m`; absent for xenos.")


class NameRollOut(BaseModel):
    shape: str
    pool: str
    region: str
    gender: str
    regions: list[list[str]] = Field(description="`[key, label]` shelves of the world pool for the region picker.")
    names: list[RolledNameOut]


def get_board(db: Session, campaign_id: str, board_id: str) -> Board:
    b = db.get(Board, board_id)
    if not b or b.campaign_id != campaign_id:
        raise HTTPException(404, tr("boards.board_missing"))
    return b


def get_card(db: Session, campaign_id: str, card_id: str) -> BoardCard:
    card = db.get(BoardCard, card_id)
    if not card or card.campaign_id != campaign_id:
        raise HTTPException(404, tr("boards.card_missing"))
    return card


def card_item(
    card: BoardCard,
    entities: dict[str, Entity],
    clocks: dict[str, Clock] | None = None,
    owners: dict[str, str] | None = None,
) -> dict:
    e = entities.get(card.entity_id or "")
    cl = (clocks or {}).get(card.clock_id or "")
    return {
        "id": card.id, "board_id": card.board_id, "kind": card.kind, "key": card.key or "",
        "entity_id": card.entity_id, "clock_id": card.clock_id,
        "title": card.title, "body": card.body, "notes": card.notes or [],
        "image_url": card.image_url, "color": card.color, "font_size": card.font_size or 14,
        "x": card.x, "y": card.y, "w": card.w, "h": card.h or 0.0,
        "ink": card.ink or [],
        "collapsed": card.collapsed, "z": card.z,
        "entity": None if e is None else {
            "id": e.id, "kind": e.kind, "name": e.name, "alias": e.alias,
            "summary": e.summary, "image_url": e.image_url, "status": e.status,
            "rank": str((e.fields or {}).get("rank", "")),
        },
        "clock": None if cl is None else {
            "id": cl.id, "name": cl.name, "segments": cl.segments, "filled": cl.filled,
            "color": cl.color, "status": cl.status, "kind": cl.kind,
            "description": cl.description, "outcome": cl.outcome,
            # доска только у ГМа: владельца не прячем
            "owner_type": cl.owner_type, "owner_id": cl.owner_id,
            # подпись счётчика на доске та же, что в базе: «владелец: имя»
            "owner_name": (owners or {}).get(cl.owner_id or "", ""),
            "visibility": cl.visibility,
        },
    }


def edge_item(e: BoardEdge) -> dict:
    return {
        "id": e.id, "board_id": e.board_id,
        "from_card_id": e.from_card_id, "to_card_id": e.to_card_id,
        "label": e.label, "color": e.color, "style": e.style,
    }


@router.get("/name-roll", summary="Roll walk-on names", response_model=NameRollOut)
def roll_names(
    n: int = Query(8, ge=1, le=40, description="How many names."),
    shape: str = Query("mix", description="`mono` first name only, `full` with family name, `alias` with a nickname, `aliasfull`, `xeno` (setting pool only); `mix` draws from all."),
    pool: str = Query("setting", description="`setting` — rulebook and frontier names; `world` — real-world names by country."),
    region: str = Query("any", description="World pool only: a shelf key or country key from `regions`; `any` takes all."),
    gender: str = Query("any", description="`f`, `m` or `any`. Xenos have no gender and come with any choice."),
    v=Depends(gm_only),
):
    """GM only. A batch of names for walk-on NPCs; nothing is stored — put the one you like on a board as a `name` card."""
    if shape != "mix" and shape not in N().SHAPES:
        shape = "mix"
    if pool != "world":
        pool = "setting"
    if gender not in N().GENDERS:
        gender = "any"
    return {
        "shape": shape, "pool": pool, "region": region, "gender": gender,
        "regions": N().group_list(),
        "names": N().roll(n, shape, pool, region, gender),
    }


@router.get("/boards", summary="List boards", response_model=list[BoardOut])
def list_boards(
    v=Depends(gm_only), db: Session = Depends(get_db),
    archived: bool = Query(False, description="`true` lists archived boards instead of active ones."),
):
    """GM only. Boards in `order`. For a readable snapshot of a board use `GET /boards/{board_id}/dump`."""
    rows = (
        db.query(Board)
        .filter(Board.campaign_id == v.campaign_id, Board.archived.is_(archived))
        .order_by(Board.order, Board.created_at)
        .all()
    )
    counts = dict(
        db.query(BoardCard.board_id, func.count(BoardCard.id))
        .filter(BoardCard.campaign_id == v.campaign_id)
        .group_by(BoardCard.board_id)
        .all()
    )
    return [
        {"id": b.id, "name": b.name, "summary": b.summary, "order": b.order,
         "card_count": counts.get(b.id, 0), "archived": b.archived, "updated_at": b.updated_at}
        for b in rows
    ]


@router.post("/boards", summary="Create a board", response_model=BoardOut)
def create_board(body: BoardIn, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Boards are GM-only by nature: nothing on them is ever shown to players. Logged in the journal."""
    b = Board(campaign_id=v.campaign_id, created_by=v.member_id, **body.model_dump())
    db.add(b)
    db.flush()
    journal.log(db, v, "board", "create", target_id=b.id, title=b.name, visibility="gm")
    db.commit()
    return {"id": b.id, "name": b.name, "summary": b.summary, "order": b.order,
            "card_count": 0, "archived": b.archived, "updated_at": b.updated_at}


@router.patch("/boards/{board_id}", summary="Rename or archive a board", response_model=Ok)
def patch_board(
    board_id: str, body: BoardPatch, v=Depends(gm_only), db: Session = Depends(get_db)
):
    """GM only. Send only the keys to change. Renaming retitles the record blocks written from this board. Logged in the journal."""
    b = get_board(db, v.campaign_id, board_id)
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    before, after = journal.changes(b, patch)
    for k, val in patch.items():
        setattr(b, k, val)
    if "name" in after:
        # доску переименовали — заголовки её записей в карточках идут следом
        block_ids = [
            r.block_id
            for r in db.query(BoardCard.block_id)
            .filter(BoardCard.campaign_id == v.campaign_id, BoardCard.board_id == b.id)
            .all()
            if r.block_id
        ]
        if block_ids:
            db.query(ContentBlock).filter(ContentBlock.id.in_(block_ids)).update(
                {"title": block_title(b)}, synchronize_session=False)
    if after:
        journal.log(db, v, "board", "update", target_id=b.id, title=b.name,
                    visibility="gm", before=before, after=after)
    db.commit()
    return {"ok": True}


@router.delete("/boards/{board_id}", summary="Delete a board", response_model=Ok)
def delete_board(board_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Deletes the board with its cards and threads. Record blocks already written from its notes stay on the records. Logged in the journal."""
    b = get_board(db, v.campaign_id, board_id)
    db.query(BoardEdge).filter_by(campaign_id=v.campaign_id, board_id=board_id).delete(
        synchronize_session=False)
    db.query(BoardCard).filter_by(campaign_id=v.campaign_id, board_id=board_id).delete(
        synchronize_session=False)
    journal.log(db, v, "board", "delete", target_id=b.id, title=b.name, visibility="gm")
    db.delete(b)
    db.commit()
    return {"ok": True}


@router.get("/boards/{board_id}/cards", summary="List cards of a board", response_model=list[BoardCardOut])
def list_cards(board_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Cards in stacking order with the record (`entity`) or clock (`clock`) they stand for resolved. Canvas coordinates; for grid cells and keys see `GET /boards/{board_id}/dump`."""
    get_board(db, v.campaign_id, board_id)
    rows = (
        db.query(BoardCard)
        .filter_by(campaign_id=v.campaign_id, board_id=board_id)
        .order_by(BoardCard.z, BoardCard.created_at)
        .all()
    )
    ids = [r.entity_id for r in rows if r.entity_id]
    entities = {
        e.id: e
        for e in (
            db.query(Entity).filter(
                Entity.campaign_id == v.campaign_id, Entity.id.in_(ids)
            ).all()
            if ids else []
        )
    }
    clock_ids = [r.clock_id for r in rows if r.clock_id]
    clocks = {
        cl.id: cl
        for cl in (
            db.query(Clock).filter(
                Clock.campaign_id == v.campaign_id, Clock.id.in_(clock_ids)
            ).all()
            if clock_ids else []
        )
    }
    owner_ids = [cl.owner_id for cl in clocks.values()
                 if cl.owner_type == "entity" and cl.owner_id]
    owners = {
        e.id: e.name
        for e in (
            db.query(Entity).filter(
                Entity.campaign_id == v.campaign_id, Entity.id.in_(owner_ids)
            ).all()
            if owner_ids else []
        )
    }
    return [card_item(r, entities, clocks, owners) for r in rows]


@router.post("/board-cards", summary="Put a card on a board", response_model=CreatedOut, responses=error_responses(400))
def create_card(body: CardIn, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. `entity` cards need `entity_id`, `clock` cards need `clock_id` (400 otherwise; 404 if the target is not in this campaign).
    The card lands on top of the stack. Notes on entity/clock cards are mirrored into the record as a GM-only block."""
    board = get_board(db, v.campaign_id, body.board_id)
    data = body.model_dump()
    if data["kind"] not in CARD_KINDS:
        data["kind"] = "text"
    data["ink"] = norm_ink(data.get("ink"))
    if data["kind"] != "entity":
        data["entity_id"] = None
    elif not data["entity_id"]:
        raise HTTPException(400, tr("boards.entry_card_needs_entry"))
    if data["kind"] != "clock":
        data["clock_id"] = None
    elif not data["clock_id"]:
        raise HTTPException(400, tr("boards.clock_card_needs_clock"))
    if data["entity_id"]:
        e = db.get(Entity, data["entity_id"])
        if not e or e.campaign_id != v.campaign_id:
            raise HTTPException(404, tr("boards.entry_missing"))
    if data["clock_id"]:
        cl = db.get(Clock, data["clock_id"])
        if not cl or cl.campaign_id != v.campaign_id:
            raise HTTPException(404, tr("boards.clock_missing"))
    top = (
        db.query(func.coalesce(func.max(BoardCard.z), 0))
        .filter_by(campaign_id=v.campaign_id, board_id=body.board_id)
        .scalar()
    )
    card = BoardCard(campaign_id=v.campaign_id, created_by=v.member_id, z=top + 1, **data)
    keys = {k for (k,) in db.query(BoardCard.key).filter_by(campaign_id=v.campaign_id, board_id=body.board_id)}
    fill_keys([card], {card.entity_id: db.get(Entity, card.entity_id)} if card.entity_id else {},
              {card.clock_id: db.get(Clock, card.clock_id)} if card.clock_id else {})
    card.key = unique_key(card.key, keys)
    db.add(card)
    db.flush()
    sync_block(db, v, card, board)
    db.commit()
    return {"id": card.id}


@router.patch("/board-cards/{card_id}", summary="Change a card", response_model=Ok)
def patch_card(
    card_id: str, body: CardPatch, v=Depends(gm_only), db: Session = Depends(get_db)
):
    """GM only. Send only the keys to change. `notes` replace the list and re-sync the record block; an unknown `kind` is ignored."""
    card = get_card(db, v.campaign_id, card_id)
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    if patch.get("kind") and patch["kind"] not in CARD_KINDS:
        patch.pop("kind")
    if "ink" in patch:
        patch["ink"] = norm_ink(patch["ink"])
    if "h" in patch:
        patch["h"] = max(0.0, min(4000.0, float(patch["h"])))
    if "font_size" in patch:
        patch["font_size"] = max(10, min(240, int(patch["font_size"])))
    for k, val in patch.items():
        setattr(card, k, val)
    if {"notes", "entity_id", "clock_id"} & set(patch):
        sync_block(db, v, card, get_board(db, v.campaign_id, card.board_id))
    db.commit()
    return {"ok": True}


@router.delete("/board-cards/{card_id}", summary="Remove a card", response_model=Ok)
def delete_card(card_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Threads attached to the card go with it; the record block written from its notes stays."""
    card = get_card(db, v.campaign_id, card_id)
    db.query(BoardEdge).filter(
        BoardEdge.campaign_id == v.campaign_id,
        (BoardEdge.from_card_id == card_id) | (BoardEdge.to_card_id == card_id),
    ).delete(synchronize_session=False)
    db.delete(card)
    db.commit()
    return {"ok": True}


@router.get("/boards/{board_id}/edges", summary="List threads of a board", response_model=list[BoardEdgeOut])
def list_edges(board_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Threads between cards, oldest first."""
    get_board(db, v.campaign_id, board_id)
    rows = (
        db.query(BoardEdge)
        .filter_by(campaign_id=v.campaign_id, board_id=board_id)
        .order_by(BoardEdge.created_at)
        .all()
    )
    return [edge_item(e) for e in rows]


@router.post("/board-edges", summary="Tie a thread between two cards", response_model=EdgeCreatedOut, responses=error_responses(400))
def create_edge(body: EdgeIn, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. One thread per ordered pair: if the pair is already tied, the existing thread's id comes back with `existing: true`.
    400 when both ends are the same card or a card is on another board."""
    get_board(db, v.campaign_id, body.board_id)
    if body.from_card_id == body.to_card_id:
        raise HTTPException(400, tr("boards.thread_nowhere"))
    for cid in (body.from_card_id, body.to_card_id):
        card = get_card(db, v.campaign_id, cid)
        if card.board_id != body.board_id:
            raise HTTPException(400, tr("boards.card_other_board"))
    data = body.model_dump()
    if data["style"] not in EDGE_STYLES:
        data["style"] = "thread"
    # та же пара уже связана — новую нить не плодим
    twin = (
        db.query(BoardEdge)
        .filter_by(campaign_id=v.campaign_id, board_id=body.board_id,
                   from_card_id=body.from_card_id, to_card_id=body.to_card_id)
        .first()
    )
    if twin:
        return {"id": twin.id, "existing": True}
    e = BoardEdge(campaign_id=v.campaign_id, created_by=v.member_id, **data)
    db.add(e)
    db.flush()
    db.commit()
    return {"id": e.id}


@router.patch("/board-edges/{edge_id}", summary="Change a thread", response_model=Ok)
def patch_edge(
    edge_id: str, body: EdgePatch, v=Depends(gm_only), db: Session = Depends(get_db)
):
    """GM only. Label, colour or style; send only the keys to change."""
    e = db.get(BoardEdge, edge_id)
    if not e or e.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("boards.thread_missing"))
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    if patch.get("style") and patch["style"] not in EDGE_STYLES:
        patch.pop("style")
    for k, val in patch.items():
        setattr(e, k, val)
    db.commit()
    return {"ok": True}


@router.delete("/board-edges/{edge_id}", summary="Cut a thread", response_model=Ok)
def delete_edge(edge_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only."""
    e = db.get(BoardEdge, edge_id)
    if not e or e.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("boards.thread_missing"))
    db.delete(e)
    db.commit()
    return {"ok": True}