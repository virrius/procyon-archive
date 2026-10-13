from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..api_schema import AUTH_ERRORS, error_responses
from ..db import get_db
from ..deps import gm_only
from ..i18n import tr
from ..models import Board, BoardCard, BoardEdge, Clock, Entity
from ..translit import slugify
from .boards import (
    CARD_KINDS,
    COL,
    DEF_W,
    EDGE_STYLES,
    ROW,
    ROWS_BY_KIND,
    card_name,
    fill_keys,
    get_board,
    sync_block,
    unique_key,
)
from .entities import UUID_RE

# The board for someone who cannot see it: a snapshot of the layout in words and batch edits.
# Cards are addressed by keys (`gregor-varg`), coordinates move in grid cells, and
# a whole scene — cards and the threads between them — is placed in one request.

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["boards-agent"], responses=AUTH_ERRORS)

CardKind = Literal["entity", "text", "image", "clock", "sketch", "name"]
EdgeStyle = Literal["thread", "dashed", "arrow"]
Color = Literal["amber", "rust", "steel", "plum", "olive", "white", "black"]
REF_DOC = "Name of the {what} (case-insensitive; a unique substring works too) or its id. Unknown → 404; several matches → 400 listing the candidates with ids."
CELL_DOC = "Grid cell (one cell = 40 canvas units); `col` grows to the right, `row` down."

GAP = 1          # a cell of air between cards in auto-placement
MAX_COL = 60     # width of the strip searched for free space, in cells


def resolve(db: Session, campaign_id: str, cards: list[BoardCard]) -> tuple[dict, dict, dict]:
    """Entries, clocks and clock owners in one pass."""
    ids = [c.entity_id for c in cards if c.entity_id]
    entities = {
        e.id: e
        for e in (db.query(Entity).filter(
            Entity.campaign_id == campaign_id, Entity.id.in_(ids)).all() if ids else [])
    }
    clock_ids = [c.clock_id for c in cards if c.clock_id]
    clocks = {
        cl.id: cl
        for cl in (db.query(Clock).filter(
            Clock.campaign_id == campaign_id, Clock.id.in_(clock_ids)).all() if clock_ids else [])
    }
    owner_ids = [cl.owner_id for cl in clocks.values()
                 if cl.owner_type == "entity" and cl.owner_id]
    owners = {
        e.id: e.name
        for e in (db.query(Entity).filter(
            Entity.campaign_id == campaign_id,
            Entity.id.in_(owner_ids)).all() if owner_ids else [])
    }
    return entities, clocks, owners


def cell(card: BoardCard) -> tuple[int, int, int, int]:
    """A card in cells: col, row, width, height (height is an estimate by kind)."""
    return (
        int(round(card.x / COL)),
        int(round(card.y / ROW)),
        max(1, int(round((card.w or 240.0) / COL))),
        max(1, int(round(card.h / ROW))) if card.h else ROWS_BY_KIND.get(card.kind, 3),
    )


def free_spot(boxes: list[tuple[int, int, int, int]], cols: int, rows: int) -> tuple[int, int]:
    """The first free spot, top to bottom: cards must not land on top of each other."""
    for row in range(0, 400):
        for col in range(0, MAX_COL):
            clash = any(
                col < bx + bw + GAP and col + cols + GAP > bx
                and row < by + bh + GAP and row + rows + GAP > by
                for bx, by, bw, bh in boxes
            )
            if not clash:
                return col, row
    return 0, 0


def norm_notes(notes: list[dict] | None) -> list[dict]:
    """A note needs its own id: the board edits and removes it by that id."""
    out = []
    for n in notes or []:
        if not isinstance(n, dict):
            continue
        out.append({
            "id": str(n.get("id") or uuid4().hex[:8]),
            "text": str(n.get("text") or ""),
            "tag": str(n.get("tag") or ""),
        })
    return out


def find_entity(db: Session, campaign_id: str, ref: str) -> Entity:
    """An entry is referred to by name: the agent has nowhere to get the id from, and the GM says the name aloud."""
    e = db.get(Entity, ref) if UUID_RE.fullmatch(ref) else None
    if e is not None and e.campaign_id == campaign_id:
        return e
    rows = (
        db.query(Entity)
        .filter(Entity.campaign_id == campaign_id, func.lower(Entity.name) == ref.strip().lower())
        .all()
    )
    if not rows:
        rows = (
            db.query(Entity)
            .filter(Entity.campaign_id == campaign_id, Entity.name.ilike(f"%{ref.strip()}%"))
            .limit(5).all()
        )
    if not rows:
        raise HTTPException(404, tr("boards.agent.entry_missing", ref=ref))
    if len(rows) > 1:
        names = ", ".join(tr("boards.agent.entry_option", name=r.name, id=r.id) for r in rows)
        raise HTTPException(400, tr("boards.agent.entry_ambiguous", ref=ref, names=names))
    return rows[0]


def find_clock(db: Session, campaign_id: str, ref: str) -> Clock:
    cl = db.get(Clock, ref) if UUID_RE.fullmatch(ref) else None
    if cl is not None and cl.campaign_id == campaign_id:
        return cl
    rows = (
        db.query(Clock)
        .filter(Clock.campaign_id == campaign_id, func.lower(Clock.name) == ref.strip().lower())
        .all()
    )
    if not rows:
        raise HTTPException(404, tr("boards.agent.clock_missing", ref=ref))
    if len(rows) > 1:
        raise HTTPException(400, tr("boards.agent.clock_ambiguous", ref=ref))
    return rows[0]




# --- output -------------------------------------------------------------------


class BoardBriefOut(BaseModel):
    id: str
    name: str
    summary: str


class GridOut(BaseModel):
    col_px: float = Field(description="Canvas units per column.")
    row_px: float = Field(description="Canvas units per row.")
    note: str


class DumpEntityOut(BaseModel):
    id: str
    kind: str
    summary: str
    status: str


class DumpClockOut(BaseModel):
    id: str
    filled: int
    segments: int
    status: str
    owner: str = Field(description="Name of the entity the clock belongs to; empty when none.")
    outcome: str


class DumpNoteOut(BaseModel):
    tag: str
    text: str


class DumpCardOut(BaseModel):
    key: str = Field(description="Address of the card for `batch`.")
    id: str = Field(description="Card id (for the canvas endpoints `/board-cards/{card_id}`).")
    kind: CardKind
    name: str = Field(description="How the card is called out loud: record or clock name, first line of text, or a kind label.")
    col: int
    row: int
    cols: int = Field(description="Width in cells.")
    color: str
    entity: DumpEntityOut | None = Field(default=None, description="`entity` cards.")
    notes: list[DumpNoteOut] | None = Field(default=None, description="Present when the card has notes.")
    clock: DumpClockOut | None = Field(default=None, description="`clock` cards.")
    text: str | None = Field(default=None, description="`text` and `name` cards.")
    font_size: int | None = Field(default=None, description="`text` cards.")
    image_url: str | None = Field(default=None, description="`image` cards.")
    title: str | None = Field(default=None, description="`image` cards.")
    strokes: int | None = Field(default=None, description="`sketch` cards: number of freehand strokes (their shape is not exported).")
    labels: list[str] | None = Field(default=None, description="`sketch` cards: text labels written on the sketch, if any.")


class DumpEdgeOut(BaseModel):
    src: str = Field(alias="from", serialization_alias="from", description="Key of the card the thread starts from.")
    dst: str = Field(alias="to", serialization_alias="to")
    label: str
    style: str
    color: str

    model_config = ConfigDict(populate_by_name=True)


class BoardDumpOut(BaseModel):
    board: BoardBriefOut
    grid: GridOut
    cards: list[DumpCardOut]
    edges: list[DumpEdgeOut]


class BoardListItemOut(BaseModel):
    id: str
    name: str
    summary: str
    cards: int = Field(description="Number of cards on the board.")
    archived: bool = False


class BatchResultOut(BaseModel):
    board_id: str
    cards: dict[str, Literal["created", "updated", "deleted", "missing"]] = Field(
        description="Outcome per card key. `missing` — a `delete` for a key that was not on the board.")
    edges: int = Field(description="Thread operations actually applied (created, edited or deleted); self-loops and deletes of absent threads are not counted.")
    ids: dict[str, str] = Field(default_factory=dict, description="Card key → card id for every card created or updated by this request.")


@router.get("/boards/{board_id}/dump", summary="Snapshot of a board", response_model=BoardDumpOut,
            response_model_exclude_none=True)
def dump_board(board_id: str, v=Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. The board as words: every card with its `key`, grid position and what it stands for
    (record, clock, text, image, sketch, walk-on name), and the threads between keys. No card ids
    needed afterwards — `POST /boards/{board_id}/batch` addresses everything by `key`.
    Cards created before keys existed get one on this call."""
    board = get_board(db, v.campaign_id, board_id)
    cards = (
        db.query(BoardCard)
        .filter_by(campaign_id=v.campaign_id, board_id=board_id)
        .order_by(BoardCard.y, BoardCard.x)
        .all()
    )
    entities, clocks, owners = resolve(db, v.campaign_id, cards)
    edges = (
        db.query(BoardEdge)
        .filter_by(campaign_id=v.campaign_id, board_id=board_id)
        .order_by(BoardEdge.created_at)
        .all()
    )
    by_id = {c.id: c for c in cards}

    out_cards = []
    for card in cards:
        e = entities.get(card.entity_id or "")
        cl = clocks.get(card.clock_id or "")
        col, row, cols, _ = cell(card)
        item: dict = {
            "key": card.key, "id": card.id, "kind": card.kind, "name": card_name(card, e, cl),
            "col": col, "row": row, "cols": cols, "color": card.color,
        }
        if card.kind == "entity" and e is not None:
            item["entity"] = {"id": e.id, "kind": e.kind, "summary": e.summary,
                              "status": e.status}
        if card.notes:
            item["notes"] = [
                {"tag": str(n.get("tag") or ""), "text": str(n.get("text") or "")}
                for n in card.notes if isinstance(n, dict)
            ]
        if card.kind == "clock" and cl is not None:
            item["clock"] = {
                "id": cl.id, "filled": cl.filled, "segments": cl.segments,
                "status": cl.status, "owner": owners.get(cl.owner_id or "", ""),
                "outcome": cl.outcome,
            }
        if card.kind == "text":
            item["text"] = card.body
            item["font_size"] = card.font_size or 14
        if card.kind == "name":
            item["text"] = card.body
        if card.kind == "image":
            item["image_url"] = card.image_url
            item["title"] = card.title
        if card.kind == "sketch":
            # strokes tell the agent nothing — only their count goes out; text labels
            # are readable, so they go out as text
            marks = [m for m in (card.ink or []) if isinstance(m, dict)]
            item["strokes"] = len([m for m in marks if m.get("kind") != "text"])
            labels = [str(m.get("text") or "") for m in marks if m.get("kind") == "text"]
            if labels:
                item["labels"] = labels
        out_cards.append(item)

    out_edges = [
        {
            "from": by_id[e.from_card_id].key if e.from_card_id in by_id else "",
            "to": by_id[e.to_card_id].key if e.to_card_id in by_id else "",
            "label": e.label, "style": e.style, "color": e.color,
        }
        for e in edges
        if e.from_card_id in by_id and e.to_card_id in by_id
    ]
    return {
        "board": {"id": board.id, "name": board.name, "summary": board.summary},
        "grid": {"col_px": COL, "row_px": ROW,
                 "note": tr("boards.agent.grid_note")},
        "cards": out_cards,
        "edges": out_edges,
    }


class NoteOp(BaseModel):
    id: str | None = Field(default=None, description="Keep the id to edit an existing note; omitted → a new id is issued.")
    text: str = Field(default="", examples=["Lies about the manifest"])
    tag: str = Field(default="", description="Group label; notes are grouped by tag in the record block.", examples=["clues"])


class CardOp(BaseModel):
    """One card operation. Without `col`/`row` the card takes the first free spot (top to bottom, one cell of air around)."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["create", "update", "delete"] = Field(
        default="create",
        description="`create` — new card, or edit when `key` is already on the board; `update` — edit only (404 if the key is missing); `delete` — remove the card and its threads (`missing` in the result if there was none).",
    )
    key: str = Field(default="", description="Human key within the board, e.g. `gregor-varg`. Omitted on create → derived from the record/clock name or the text (transliterated, unique).", examples=["gregor-varg"])
    kind: CardKind = Field(default="text", description="Ignored when `entity` or `clock` is given (the kind follows). `entity`/`clock` without a target → 400.")
    entity: str | None = Field(default=None, description=REF_DOC.format(what="campaign record") + " Makes the card an `entity` card.", examples=["Gregor Varg"])
    clock: str | None = Field(default=None, description=REF_DOC.format(what="clock") + " Makes the card a `clock` card.")
    text: str | None = Field(default=None, description="Body of a `text` or `name` card.")
    title: str | None = Field(default=None, description="Caption (image cards).")
    notes: list[NoteOp] | None = Field(default=None, description="Replaces the card's notes as a whole. On entity/clock cards they are also written into the record as one GM-only block `Board: <board name>`, grouped by tag; an empty list removes that block.")
    image_url: str | None = Field(default=None, description="Picture for an `image` card (an uploaded file's `url`).")
    color: Color | None = None
    font_size: int | None = Field(default=None, description="10..240, text cards.")
    col: int | None = Field(default=None, description=CELL_DOC)
    row: int | None = Field(default=None, description=CELL_DOC)
    cols: int | None = Field(default=None, description="Width in cells; omitted → default width of the kind.")


class EdgeOp(BaseModel):
    """A thread between two cards addressed by key. One thread per ordered pair: repeating it edits label, colour and style."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["create", "delete"] = Field(default="create")
    src: str = Field(alias="from", description="Key of the card the thread starts from (`from`). Unknown key → 400.")
    dst: str = Field(alias="to", description="Key of the card the thread goes to (`to`).")
    label: str = Field(default="", examples=["supplier"])
    color: Color = Field(default="rust")
    style: EdgeStyle = Field(default="thread", description="`thread` plain, `dashed`, `arrow` with a head at `to`.")


class BatchIn(BaseModel):
    cards: list[CardOp] = Field(default=[], description="Applied in order; later ops may reference keys created earlier in the same batch.")
    edges: list[EdgeOp] = Field(default=[], description="Applied after all card ops.")


BATCH_EXAMPLE = {
    "cards": [
        {"key": "devi", "entity": "Devi Yasmin"},
        {"key": "chase", "clock": "The chase", "col": 20, "row": 2,
         "notes": [{"tag": "why", "text": "The syndicate raised the price"}]},
        {"key": "note", "kind": "text", "text": "the cargo left through dock three", "font_size": 20},
        {"op": "update", "key": "gregor-varg", "notes": [{"tag": "clues", "text": "Key card"}]},
        {"op": "delete", "key": "old-note"},
    ],
    "edges": [
        {"from": "devi", "to": "gregor-varg", "label": "supplier"},
        {"from": "note", "to": "devi", "label": "according to Kes", "style": "dashed"},
        {"op": "delete", "from": "rumor", "to": "chase"},
    ],
}


@router.post("/boards/{board_id}/batch", summary="Place a scene on a board", response_model=BatchResultOut,
             responses=error_responses(400))
def batch_board(board_id: str, body: BatchIn = Body(examples=[BATCH_EXAMPLE]), v=Depends(gm_only),
                db: Session = Depends(get_db)):
    """GM only. Cards and threads in one atomic request (any error rolls everything back).
    Cards are addressed by `key`; records and clocks by **name** (or id). Without `col`/`row` a card
    takes the first free spot. Notes on entity/clock cards are mirrored into the record as a GM-only
    block titled after the board. 400: ambiguous name, `entity`/`clock` card without a target,
    thread to an unknown key; 404: `update` of a missing key, unknown record or clock name."""
    board = get_board(db, v.campaign_id, board_id)
    cards = (
        db.query(BoardCard).filter_by(campaign_id=v.campaign_id, board_id=board_id).all()
    )
    entities, clocks, _ = resolve(db, v.campaign_id, cards)
    fill_keys(cards, entities, clocks)
    by_key = {c.key: c for c in cards if c.key}
    boxes = [cell(c) for c in cards]
    top = max([c.z or 0 for c in cards], default=0)
    done: dict[str, str] = {}

    for op in body.cards:
        if op.op == "delete":
            card = by_key.get(op.key)
            if card is None:
                done[op.key] = "missing"
                continue
            db.query(BoardEdge).filter(
                BoardEdge.campaign_id == v.campaign_id,
                (BoardEdge.from_card_id == card.id) | (BoardEdge.to_card_id == card.id),
            ).delete(synchronize_session=False)
            db.delete(card)
            by_key.pop(op.key, None)
            done[op.key] = "deleted"
            continue

        card = by_key.get(op.key) if op.key else None
        kind = op.kind if op.kind in CARD_KINDS else "text"
        if card is None:
            if op.op == "update":
                raise HTTPException(404, tr("boards.agent.card_missing", key=op.key))
            e = find_entity(db, v.campaign_id, op.entity) if op.entity else None
            cl = find_clock(db, v.campaign_id, op.clock) if op.clock else None
            if e is not None:
                kind = "entity"
            elif cl is not None:
                kind = "clock"
            elif kind in ("entity", "clock"):
                raise HTTPException(400, tr("boards.agent.card_needs_target"))
            cols = op.cols or max(1, int(round(DEF_W.get(kind, 240.0) / COL)))
            rows = ROWS_BY_KIND.get(kind, 3)
            col, row = (op.col, op.row) if op.col is not None and op.row is not None \
                else free_spot(boxes, cols, rows)
            base = slugify(op.key or (e.name if e else cl.name if cl else op.text or kind), kind)
            key = op.key if op.key and op.key not in by_key else unique_key(base, set(by_key))
            top += 1
            card = BoardCard(
                campaign_id=v.campaign_id, board_id=board_id, created_by=v.member_id,
                key=key, kind=kind, entity_id=e.id if e else None,
                clock_id=cl.id if cl else None,
                x=col * COL, y=row * ROW, w=cols * COL, z=top,
                body=op.text or "", title=op.title or "", image_url=op.image_url or "",
                color=op.color or "amber", font_size=op.font_size or 14,
                notes=norm_notes([n.model_dump() for n in op.notes] if op.notes is not None else None),
            )
            db.add(card)
            db.flush()
            by_key[key] = card
            boxes.append((col, row, cols, rows))
            done[key] = "created"
            sync_block(db, v, card, board)
        else:
            if op.entity:
                card.entity_id = find_entity(db, v.campaign_id, op.entity).id
                card.kind = "entity"
            if op.clock:
                card.clock_id = find_clock(db, v.campaign_id, op.clock).id
                card.kind = "clock"
            if op.text is not None:
                card.body = op.text
            if op.title is not None:
                card.title = op.title
            if op.notes is not None:
                card.notes = norm_notes([n.model_dump() for n in op.notes])
            if op.image_url is not None:
                card.image_url = op.image_url
            if op.color is not None:
                card.color = op.color
            if op.font_size is not None:
                card.font_size = max(10, min(240, op.font_size))
            if op.cols is not None:
                card.w = max(1, op.cols) * COL
            if op.col is not None:
                card.x = op.col * COL
            if op.row is not None:
                card.y = op.row * ROW
            done[card.key] = "updated"
            # the entry block is rebuilt only when the notes change or what they are attached to changes
            if op.notes is not None or op.entity or op.clock:
                sync_block(db, v, card, board)

    db.flush()
    applied = 0
    for op in body.edges:
        a, b = by_key.get(op.src), by_key.get(op.dst)
        if a is None or b is None:
            raise HTTPException(400, tr("boards.agent.thread_no_card", src=op.src, dst=op.dst))
        if a.id == b.id:
            continue
        twin = (
            db.query(BoardEdge)
            .filter_by(campaign_id=v.campaign_id, board_id=board_id,
                       from_card_id=a.id, to_card_id=b.id)
            .first()
        )
        if op.op == "delete":
            if twin is not None:
                db.delete(twin)
                applied += 1
            continue
        if twin is not None:
            twin.label, twin.color = op.label, op.color
            twin.style = op.style if op.style in EDGE_STYLES else "thread"
            applied += 1
            continue
        db.add(BoardEdge(
            campaign_id=v.campaign_id, board_id=board_id, created_by=v.member_id,
            from_card_id=a.id, to_card_id=b.id, label=op.label, color=op.color,
            style=op.style if op.style in EDGE_STYLES else "thread",
        ))
        applied += 1

    db.commit()
    ids = {k: by_key[k].id for k, state in done.items() if state in ("created", "updated") and k in by_key}
    return {"board_id": board.id, "cards": done, "edges": applied, "ids": ids}


@router.get("/boards-dump", summary="List boards with card counts", response_model=list[BoardListItemOut])
def list_boards_dump(
    v=Depends(gm_only), db: Session = Depends(get_db),
    archived: bool = Query(False, description="`true` lists archived boards instead of active ones."),
):
    """GM only. Where to start when a board is named: find its id here, then `GET /boards/{board_id}/dump`."""
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
        {"id": b.id, "name": b.name, "summary": b.summary, "cards": counts.get(b.id, 0),
         "archived": b.archived}
        for b in rows
    ]
