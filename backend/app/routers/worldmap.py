from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, VISIBLE_TO_DOC, Ok, Visibility, default_visibility, error_responses, vis_field
from ..db import get_db
from ..deps import editor, viewer
from ..i18n import ctr, tr
from ..models import ContentBlock, Entity, MapMarker, MapNode, MapStroke
from ..visibility import Viewer, apply_scope, can_see
from .entities import block_visible, peer_brief

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["map"], responses=AUTH_ERRORS)

# что у отметки считаем событием: координаты меняются перетаскиванием, их не пишем
MARKER_LOGGED = ("label", "marker_type", "visibility", "visible_to", "linked_type", "linked_id")

MARKER_ICONS = ("dot", "ring", "cross", "target", "diamond", "star")

MapLevel = Literal["sector", "system", "local"]
MarkerType = Literal["location", "custom"]
MarkerIcon = Literal["dot", "ring", "cross", "target", "diamond", "star"]
Color = Literal["amber", "rust", "steel", "plum", "olive", "white"]

COORD_DOC = "Fraction of the map image, 0..1 (0,0 = top-left corner): the background can be swapped without moving anything."
LINK_DOC = "`entity` when the marker stands for a record of the campaign (then `linked_id` is that entity's id); `null` for a free marker."


def marker_title(m: MapMarker) -> str:
    return (m.label or "").strip() or ctr("content.marker", n=m.number)


def marker_editable(m: MapMarker, v: Viewer) -> bool:
    """Как у карточек: ГМ правит любую отметку, игрок — только свою."""
    return v.is_gm or bool(v.member_id) and m.created_by == v.member_id


def check_link(db: Session, v: Viewer, linked_type: str | None, linked_id: str | None) -> None:
    if linked_type != "entity":
        return
    e = db.get(Entity, linked_id) if linked_id else None
    if not e or e.campaign_id != v.campaign_id or not can_see(e, v):
        raise HTTPException(404, tr("map.entry_missing"))


# --- input --------------------------------------------------------------------


class MapIn(BaseModel):
    name: str = Field(max_length=200, description="Map title shown in the map switcher.", examples=["Procyon sector"])
    level: MapLevel = Field(default="system", description="`sector` — the whole sector; `system` — one star system; `local` — legacy name of `system` on older maps.")
    image_url: str = Field(default="", description="Background image: the `url` of an uploaded file (`POST /upload`), or empty for a blank map.")
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)


class MapPatch(BaseModel):
    """Only the keys sent are changed."""

    name: str | None = Field(default=None, max_length=200)
    level: MapLevel | None = None
    image_url: str | None = Field(default=None, description="New background; empty string clears it.")
    visibility: Visibility | None = Field(default=None, description="GM only.")
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)


class MarkerIn(BaseModel):
    map_id: str = Field(description="Map the marker goes on (`GET /maps`).")
    x: float = Field(default=0.5, description=COORD_DOC)
    y: float = Field(default=0.5, description=COORD_DOC)
    marker_type: MarkerType = Field(default="location", description="`location` — a place (usually linked to a location entity); `custom` — anything else.")
    icon: MarkerIcon = Field(default="dot", description="Glyph drawn at the point. Unknown values fall back to `dot`.")
    label: str = Field(default="", max_length=200, description="Caption; empty → the linked entity's name, or `marker #N`.", examples=["Dock 3"])
    size: int = Field(default=0, description="Colour index into the palette amber, rust, steel, plum, olive, white (0..5).")
    linked_type: Literal["entity"] | None = Field(default=None, description=LINK_DOC)
    linked_id: str | None = Field(default=None, description="Entity id when `linked_type` is `entity`. 404 if the entity is not visible to you.")
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)


class MarkerPatch(BaseModel):
    """Only the keys sent are changed. Dragging (x/y only) is not written to the journal."""

    x: float | None = Field(default=None, description=COORD_DOC)
    y: float | None = Field(default=None, description=COORD_DOC)
    marker_type: MarkerType | None = None
    icon: MarkerIcon | None = None
    label: str | None = Field(default=None, max_length=200)
    size: int | None = Field(default=None, description="Colour index 0..5.")
    linked_type: Literal["entity", ""] | None = Field(default=None, description="`entity` to link, empty string to unlink; omit to keep.")
    linked_id: str | None = Field(default=None, description="Entity id; empty string unlinks.")
    visibility: Visibility | None = Field(default=None, description="Players cannot set `gm`.")
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)


class StrokeIn(BaseModel):
    map_id: str = Field(description="Map the stroke is drawn on.")
    points: list[list[float]] = Field(
        description="Polyline as `[[x, y], …]` in map fractions 0..1; 2..4000 points, clamped and rounded to 4 decimals.",
        examples=[[[0.12, 0.3], [0.15, 0.32], [0.2, 0.31]]],
    )
    color: Color = Field(default="amber")
    width: int = Field(default=3, description="Pen width 1..12 (clamped).")
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field(default=[], description=VISIBLE_TO_DOC)


# --- output -------------------------------------------------------------------


class MapOut(BaseModel):
    id: str
    name: str
    level: str = Field(description="`sector` or `system`.")
    image_url: str = Field(description="Background file url; empty for a blank map.")
    visibility: Visibility | None = Field(default=None, description="Present for the GM only.")


class MapDeletedOut(BaseModel):
    ok: bool = True
    markers: int = Field(description="How many markers (with their blocks and strokes) went with the map.")


class LinkedEntityOut(BaseModel):
    """The entity a marker stands for, trimmed to what the viewer may see."""

    id: str
    kind: str
    name: str
    status: str
    alias: str
    summary: str = Field(description="Empty when the GM hid it from players.")
    image_url: str = Field(description="Empty when the GM hid it from players.")


class MarkerOut(BaseModel):
    id: str
    number: int = Field(description="Sequential number on its map; used as the caption when `label` is empty.")
    x: float
    y: float
    marker_type: str = Field(description="`location` or `custom`.")
    icon: str
    label: str
    size: int = Field(description="Colour index 0..5.")
    linked_type: str | None
    linked_id: str | None
    linked: LinkedEntityOut | None = Field(description="The linked entity, or `null` when there is none or it is hidden from you.")
    note_count: int = Field(description="Blocks attached to the marker that you may see.")
    created_by: str | None = Field(description="Member id of the author.")
    can_edit: bool = Field(description="Whether you may patch or delete it (GM, or the author).")
    visibility: Visibility | None = Field(description="Present only when `can_edit`.")
    visible_to: list[str] | None = Field(description="Present only when `can_edit`.")


class StrokeOut(BaseModel):
    id: str
    points: list[list[float]]
    color: str
    width: int
    created_by: str | None
    visibility: Visibility | None = Field(description="Present for the GM only.")


class StrokesClearedOut(BaseModel):
    deleted: int


# --- maps ---------------------------------------------------------------------


def map_item(m: MapNode, v: Viewer) -> dict:
    return {"id": m.id, "name": m.name, "level": m.level, "image_url": m.image_url,
            "visibility": m.visibility if v.is_gm else None}


def stroke_item(s: MapStroke, v: Viewer) -> dict:
    return {"id": s.id, "points": s.points, "color": s.color, "width": s.width,
            "created_by": s.created_by, "visibility": s.visibility if v.is_gm else None}


def marker_item(db: Session, v: Viewer, m: MapMarker, note_count: int) -> dict:
    linked = None
    if m.linked_type == "entity" and m.linked_id:
        e = db.get(Entity, m.linked_id)
        if e and can_see(e, v):
            shown = peer_brief(e, v)
            linked = {"id": e.id, "kind": e.kind, "name": e.name, "status": shown["status"],
                      "alias": e.alias, "summary": shown["summary"],
                      "image_url": shown["image_url"]}
    can = marker_editable(m, v)
    return {
        "id": m.id, "number": m.number, "x": m.x, "y": m.y,
        "marker_type": m.marker_type, "icon": m.icon or "dot",
        "label": m.label, "size": m.size,
        "linked_type": m.linked_type, "linked_id": m.linked_id,
        "linked": linked, "note_count": note_count,
        "created_by": m.created_by,
        "can_edit": can,
        # аудиторию отдаём тому, кто вправе её менять: иначе пикер покажет
        # дефолт «всем» и затрёт настоящий скоуп при первой же правке
        "visibility": m.visibility if can else None,
        "visible_to": (m.visible_to or []) if can else None,
    }


@router.get("/maps", summary="List maps", response_model=list[MapOut])
def list_maps(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Maps of the campaign visible to you, sector maps first. Markers and strokes are fetched per map."""
    q = db.query(MapNode).filter(MapNode.campaign_id == v.campaign_id)
    rows = apply_scope(q, MapNode, v).order_by(MapNode.level, MapNode.name).all()
    return [map_item(m, v) for m in rows]


@router.post("/maps", summary="Create a map", response_model=MapOut, responses=error_responses(403))
def create_map(body: MapIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM only. A map omitted `visibility` is `gm` — open it when the table should see it. Logged in the journal."""
    if not v.is_gm:
        raise HTTPException(403, tr("map.gm_manages_maps"))
    data = body.model_dump()
    data["visibility"] = default_visibility(v, body.visibility)
    m = MapNode(campaign_id=v.campaign_id, **data)
    db.add(m)
    db.flush()
    journal.log(db, v, "map", "create", target_id=m.id, title=m.name,
                detail=m.level, visibility=m.visibility)
    db.commit()
    return map_item(m, v)


@router.patch("/maps/{map_id}", summary="Change a map", response_model=MapOut, responses=error_responses(403))
def patch_map(
    map_id: str, body: MapPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """GM only. Send only the keys to change; returns the map. Changes are logged in the journal."""
    if not v.is_gm:
        raise HTTPException(403, tr("map.gm_only"))
    m = db.get(MapNode, map_id)
    if not m or m.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("map.not_found"))
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items() if val is not None}
    before, after = journal.changes(m, patch)
    for k, val in patch.items():
        setattr(m, k, val)
    if after:
        journal.log(db, v, "map", "update", target_id=m.id, title=m.name,
                    detail=m.level, visibility=m.visibility, before=before, after=after)
    db.commit()
    return map_item(m, v)


@router.delete("/maps/{map_id}", summary="Delete a map", response_model=MapDeletedOut, responses=error_responses(403))
def delete_map(map_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM only. Deletes the map with all its markers, their blocks and all strokes. Logged in the journal."""
    if not v.is_gm:
        raise HTTPException(403, tr("map.gm_only"))
    m = db.get(MapNode, map_id)
    if not m or m.campaign_id != v.campaign_id:
        raise HTTPException(404, tr("map.not_found"))
    marker_ids = [
        r.id for r in db.query(MapMarker.id).filter_by(campaign_id=v.campaign_id, map_id=map_id)
    ]
    if marker_ids:
        db.query(ContentBlock).filter(
            ContentBlock.entity_type == "marker", ContentBlock.entity_id.in_(marker_ids)
        ).delete(synchronize_session=False)
    db.query(MapStroke).filter_by(campaign_id=v.campaign_id, map_id=map_id).delete(
        synchronize_session=False)
    db.query(MapMarker).filter_by(campaign_id=v.campaign_id, map_id=map_id).delete(
        synchronize_session=False)
    journal.log(db, v, "map", "delete", target_id=m.id, title=m.name,
                detail=m.level, visibility=m.visibility)
    db.delete(m)
    db.commit()
    return {"ok": True, "markers": len(marker_ids)}


# --- markers ------------------------------------------------------------------


@router.get("/maps/{map_id}/markers", summary="List markers of a map", response_model=list[MarkerOut])
def list_markers(map_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Markers you may see, by number. A hidden map answers 404. `linked` is the entity the marker
    stands for, trimmed to the fields open to you; `note_count` counts blocks on the marker
    (`GET /blocks/marker/{marker_id}`)."""
    node = db.get(MapNode, map_id)
    if not node or node.campaign_id != v.campaign_id or not can_see(node, v):
        raise HTTPException(404, tr("map.map_missing"))
    q = db.query(MapMarker).filter_by(campaign_id=v.campaign_id, map_id=map_id)
    rows = apply_scope(q, MapMarker, v).order_by(MapMarker.number).all()

    note_counts: dict[str, int] = {}
    for b in db.query(ContentBlock).filter(
        ContentBlock.campaign_id == v.campaign_id, ContentBlock.entity_type == "marker",
        ContentBlock.entity_id.in_([m.id for m in rows]),
    ):
        if block_visible(b, v):
            note_counts[b.entity_id] = note_counts.get(b.entity_id, 0) + 1
    return [marker_item(db, v, m, note_counts.get(m.id, 0)) for m in rows]


@router.post("/markers", summary="Place a marker", response_model=MarkerOut, responses=error_responses(403))
def create_marker(body: MarkerIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Any editor. The marker gets the next `number` on its map. A GM's marker without `visibility`
    is `gm`; players cannot set `gm`. 404 when the map or the linked entity is not visible to you.
    Logged in the journal."""
    node = db.get(MapNode, body.map_id)
    if not node or node.campaign_id != v.campaign_id or not can_see(node, v):
        raise HTTPException(404, tr("map.map_missing"))
    if not v.is_gm and body.visibility == "gm":
        raise HTTPException(403, tr("map.gm_only"))
    check_link(db, v, body.linked_type, body.linked_id)
    nxt = (
        db.query(func.coalesce(func.max(MapMarker.number), 0))
        .filter_by(campaign_id=v.campaign_id, map_id=body.map_id)
        .scalar()
    ) + 1
    data = body.model_dump()
    data["visibility"] = default_visibility(v, body.visibility)
    m = MapMarker(campaign_id=v.campaign_id, number=nxt, created_by=v.member_id, **data)
    db.add(m)
    db.flush()
    journal.log(db, v, "marker", "create", target_id=m.id, title=marker_title(m),
                detail=node.name, visibility=m.visibility)
    db.commit()
    return marker_item(db, v, m, 0)


@router.patch("/markers/{marker_id}", summary="Change a marker", response_model=Ok, responses=error_responses(403))
def patch_marker(
    marker_id: str, body: MarkerPatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """GM or the marker's author. Send only the keys to change. Empty `linked_type`/`linked_id`
    unlink the entity. Moving (x/y) is not journaled; label, type, link and visibility changes are."""
    m = db.get(MapMarker, marker_id)
    if not m or m.campaign_id != v.campaign_id or not can_see(m, v):
        raise HTTPException(404, tr("map.not_found"))
    if not marker_editable(m, v):
        raise HTTPException(403, tr("map.not_your_marker"))
    if not v.is_gm and body.visibility == "gm":
        raise HTTPException(403, tr("map.gm_only"))
    patch = {k: val for k, val in body.model_dump(exclude_unset=True).items()
             if val is not None}
    if patch.get("icon") not in MARKER_ICONS:
        patch.pop("icon", None)
    # пустая строка в связке — снять привязку: None в PATCH означает «не трогать»
    for k in ("linked_type", "linked_id"):
        if patch.get(k) == "":
            patch[k] = None
    if "linked_type" in patch or "linked_id" in patch:
        check_link(db, v,
                   patch.get("linked_type", m.linked_type),
                   patch.get("linked_id", m.linked_id))
    # перетаскивание отметки — не событие журнала, иначе лента забита координатами
    before, after = journal.changes(m, patch, MARKER_LOGGED)
    for k, val in patch.items():
        setattr(m, k, val)
    if after:
        journal.log(db, v, "marker", "update", target_id=m.id, title=marker_title(m),
                    visibility=m.visibility, before=before, after=after)
    db.commit()
    return {"ok": True}


@router.delete("/markers/{marker_id}", summary="Delete a marker", response_model=Ok, responses=error_responses(403))
def delete_marker(marker_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM or the marker's author. Blocks attached to the marker go with it. Logged in the journal."""
    m = db.get(MapMarker, marker_id)
    if not m or m.campaign_id != v.campaign_id or not can_see(m, v):
        raise HTTPException(404, tr("map.not_found"))
    if not marker_editable(m, v):
        raise HTTPException(403, tr("map.not_your_marker"))
    db.query(ContentBlock).filter_by(entity_type="marker", entity_id=m.id).delete()
    journal.log(db, v, "marker", "delete", target_id=m.id, title=marker_title(m),
                visibility=m.visibility, before={"label": m.label})
    db.delete(m)
    db.commit()
    return {"ok": True}


# --- freehand marker ----------------------------------------------------------


@router.get("/maps/{map_id}/strokes", summary="List strokes of a map", response_model=list[StrokeOut])
def list_strokes(map_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Freehand strokes you may see, oldest first. A hidden map answers 404."""
    node = db.get(MapNode, map_id)
    if not node or node.campaign_id != v.campaign_id or not can_see(node, v):
        raise HTTPException(404, tr("map.map_missing"))
    q = db.query(MapStroke).filter_by(campaign_id=v.campaign_id, map_id=map_id)
    return [stroke_item(s, v) for s in apply_scope(q, MapStroke, v).order_by(MapStroke.created_at).all()]


@router.post("/strokes", summary="Draw a stroke", response_model=StrokeOut, responses=error_responses(400, 403))
def create_stroke(body: StrokeIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Any editor. Points are clamped to 0..1; 400 outside 2..4000 points. A GM's stroke without
    `visibility` is `gm`; players cannot set `gm`. Not journaled."""
    node = db.get(MapNode, body.map_id)
    if not node or node.campaign_id != v.campaign_id or not can_see(node, v):
        raise HTTPException(404, tr("map.map_missing"))
    if len(body.points) < 2 or len(body.points) > 4000:
        raise HTTPException(400, tr("map.stroke_points"))
    if not v.is_gm and body.visibility == "gm":
        raise HTTPException(403, tr("map.gm_only"))
    pts = [[round(min(1.0, max(0.0, float(x))), 4), round(min(1.0, max(0.0, float(y))), 4)]
           for x, y in body.points]
    st = MapStroke(
        campaign_id=v.campaign_id, created_by=v.member_id,
        **{**body.model_dump(), "points": pts, "width": max(1, min(12, body.width)),
           "visibility": default_visibility(v, body.visibility)},
    )
    db.add(st)
    db.flush()
    db.commit()
    return stroke_item(st, v)


@router.delete("/strokes/{stroke_id}", summary="Erase a stroke", response_model=Ok, responses=error_responses(403))
def delete_stroke(stroke_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """GM or the stroke's author."""
    st = db.get(MapStroke, stroke_id)
    if not st or st.campaign_id != v.campaign_id or not can_see(st, v):
        raise HTTPException(404, tr("map.not_found"))
    if not v.is_gm and st.created_by != v.member_id:
        raise HTTPException(403, tr("map.not_your_stroke"))
    db.delete(st)
    db.commit()
    return {"ok": True}


@router.delete("/maps/{map_id}/strokes", summary="Erase my strokes on a map", response_model=StrokesClearedOut)
def clear_strokes(map_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Erases only the strokes you drew (the GM's too); someone else's go one by one via `DELETE /strokes/{id}`."""
    q = (
        db.query(MapStroke)
        .filter_by(campaign_id=v.campaign_id, map_id=map_id)
        .filter(MapStroke.created_by == v.member_id)
    )
    n = 0
    for st in q.all():
        db.delete(st)
        n += 1
    db.commit()
    return {"deleted": n}
