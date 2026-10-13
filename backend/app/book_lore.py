"""Book canon (the "Procyon Sector" chapter) as entries of a new campaign.

``book().ORGS`` and ``book().PROCYON`` hold the data; here they become entities:
the short description goes into ``summary``, the book details (goal, turf, NPCs,
assets, allies, enemies, situation; for locations a rule and a scene) into one dossier note
with GM visibility. No images: the GM gives locations their look.

The sector map is a background from ./assets plus markers for locations that have ``map`` in the book.

Fills in only what is missing: the description for empty entries, the dossier for those without
a note with that title yet; GM edits are left alone.
"""

from __future__ import annotations

import glob
import os

from sqlalchemy.orm import Session

from .book_defs import book
from .i18n import tr
from .models import ContentBlock, Entity, MapMarker, MapNode
from .schema_defs import initial_status

ASSET_DIR = "/data/assets"
SECTOR_STEMS = ("procyon-sector", "procyon_sector", "sector")


def sector_background() -> str:
    """Static path to the sector map: nginx serves ./assets as /media."""
    for stem in SECTOR_STEMS:
        for ext in ("webp", "png", "jpg", "jpeg"):  # webp first: the same image is nine times lighter
            hits = glob.glob(os.path.join(ASSET_DIR, f"{stem}.{ext}"))
            if hits:
                return f"/media/{os.path.basename(hits[0])}"
    return ""


def _lines(*parts: tuple[str, str]) -> str:
    return "\n\n".join(f"{label}: {value}" for label, value in parts if value)


def org_dossier(org: dict, lang: str) -> str:
    bullets = "\n".join(f"• {f}" for f in org.get("faces", []))
    lab = lambda key: tr(f"content.lore.{key}", lang=lang)  # noqa: E731
    return _lines(
        (lab("goal"), org.get("goal", "")),
        (lab("turf"), org.get("turf", "")),
        (lab("faces"), f"\n{bullets}" if bullets else ""),
        (lab("assets"), org.get("assets", "")),
        (lab("quirk"), org.get("quirk", "")),
        (lab("allies"), ", ".join(org.get("allies", []))),
        (lab("enemies"), ", ".join(org.get("enemies", []))),
        (lab("situation"), org.get("situation", "")),
    )


def place_dossier(place: dict, lang: str) -> str:
    bullets = "\n".join(f"• {f}" for f in place.get("faces", []))
    lab = lambda key: tr(f"content.lore.{key}", lang=lang)  # noqa: E731
    return _lines(
        (lab("rule"), place.get("rule", "")),
        (lab("scene"), place.get("scene", "")),
        (lab("place_faces"), f"\n{bullets}" if bullets else ""),
        (lab("tags"), ", ".join(place.get("tags", []))),
    )


def places(lang: str) -> list[tuple[str, dict]]:
    """Book locations in order, with their system: both books use the same order."""
    return [
        (sysdef["system"], p)
        for sysdef in book(lang).PROCYON
        for p in list(sysdef.get("worlds", [])) + list(sysdef.get("sites", []))
    ]


def _ensure_block(db: Session, campaign_id: str, entity: Entity, title: str, content: str) -> None:
    if not content:
        return
    have = (
        db.query(ContentBlock.id)
        .filter_by(campaign_id=campaign_id, entity_type="entity", entity_id=entity.id, title=title)
        .first()
    )
    if have:
        return
    db.add(ContentBlock(
        campaign_id=campaign_id, entity_type="entity", entity_id=entity.id,
        block_type="text", title=title, content=content, order=0,
        created_by_gm=True, visibility="gm",
    ))


def _entity(db: Session, campaign_id: str, kind: str, name: str, known: dict) -> Entity:
    if name in known:
        return known[name]
    e = Entity(campaign_id=campaign_id, kind=kind, name=name, status=initial_status(kind))
    db.add(e)
    db.flush()
    known[name] = e
    return e


def apply_orgs(db: Session, campaign_id: str, lang: str) -> dict[str, Entity]:
    known = {
        e.name: e
        for e in db.query(Entity).filter_by(campaign_id=campaign_id, kind="faction").all()
    }
    out: dict[str, Entity] = {}
    for org in book(lang).ORGS:
        e = _entity(db, campaign_id, "faction", org["name"], known)
        if not e.fields:
            e.fields = {"category": org["category"], "rank": str(org["tier"]), "stance": "0"}
            # the whole sector list stays with the GM: the table learns of a faction when the GM reveals it
            e.visibility = "gm"
        if not e.summary:
            e.summary = org["blurb"]
        _ensure_block(db, campaign_id, e, tr("content.lore.org_block", lang=lang),
                      org_dossier(org, lang))
        out[org["name"]] = e
    return out


def apply_places(db: Session, campaign_id: str, lang: str) -> dict[str, Entity]:
    known = {
        e.name: e
        for e in db.query(Entity).filter_by(campaign_id=campaign_id, kind="location").all()
    }
    out: dict[str, Entity] = {}
    for system, p in places(lang):
        e = _entity(db, campaign_id, "location", p["name"], known)
        if not e.fields:
            e.fields = {"loc_type": p.get("kind", "planet"), "system": system}
        if not e.summary:
            e.summary = p.get("text", "")
        _ensure_block(db, campaign_id, e, tr("content.lore.place_block", lang=lang),
                      place_dossier(p, lang))
        out[p["name"]] = e
    return out


def apply_map(db: Session, campaign_id: str, lang: str, located: dict[str, Entity]) -> MapNode:
    """Sector map with markers for book locations; if a map exists, nothing is touched."""
    node = db.query(MapNode).filter_by(campaign_id=campaign_id, level="sector").first()
    if node:
        return node
    node = MapNode(campaign_id=campaign_id, name=tr("content.sector", lang=lang), level="sector",
                   image_url=sector_background())
    db.add(node)
    db.flush()
    number = 1
    for _system, p in places(lang):
        e = located.get(p["name"])
        if not p.get("map") or e is None:
            continue
        x, y = p["map"]
        db.add(MapMarker(
            campaign_id=campaign_id, map_id=node.id, number=number, x=x, y=y,
            marker_type="location", icon="ring", size=5,
            linked_type="entity", linked_id=e.id,
        ))
        number += 1
    return node


def seed_campaign(db: Session, campaign_id: str, lang: str) -> None:
    """Everything a campaign starts with: book factions and locations, and the map with their markers."""
    apply_orgs(db, campaign_id, lang)
    apply_map(db, campaign_id, lang, apply_places(db, campaign_id, lang))
