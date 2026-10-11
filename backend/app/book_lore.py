"""Канон книги (глава «Сектор Процион») в карточках новой кампании.

``book().ORGS`` и ``book().PROCYON`` держат данные, здесь они становятся сущностями:
короткое описание уходит в ``summary``, подробности книги (цель, территория, лица,
ресурсы, союзники, враги, положение; для мест — правило и сцена) — в одну запись-досье
с видимостью ГМ. Картинок нет: облик местам ГМ даёт сам.

Карта сектора — фон из ./assets и отметки мест, у которых в книге стоит ``map``.

Заполняет только отсутствующее: описание — пустым карточкам, досье — тем, у кого записи
с этим заголовком ещё нет; правки ГМа не трогаются.
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
    """Статический путь к карте сектора: nginx отдаёт ./assets как /media."""
    for stem in SECTOR_STEMS:
        for ext in ("webp", "png", "jpg", "jpeg"):  # webp первым: тот же кадр вдевятеро легче
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
    """Места книги по порядку, с системой: тот же порядок у обеих книг."""
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
            # весь список сектора у ГМа: организацию стол узнаёт, когда ГМ её откроет
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
    """Карта сектора с отметками мест книги; есть карта — ничего не трогаем."""
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
    """Всё, с чем кампания стартует: фракции и места книги, карта с их отметками."""
    apply_orgs(db, campaign_id, lang)
    apply_map(db, campaign_id, lang, apply_places(db, campaign_id, lang))
