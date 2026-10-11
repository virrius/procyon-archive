"""Канон книги в кампании — на языке экземпляра.

Фракции и места книги, их досье, системы, значения бланков (плейбук, наследие, порок,
травма, размер и класс корабля), подписи связей, название карты сектора и книжные разделы
вырезок лежат в базе текстом на том языке, на котором кампания завелась. Когда язык
меняется (админ в Admin space или импорт кампании с другого экземпляра), всё это переходит
на новый язык — но только то, что совпадает с книгой слово в слово: правки ГМа и всё,
что написали игроки, остаётся как есть.

Обе книги одной формы и в одном порядке, поэтому пары «старое → новое» берутся по позиции.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import langpack
from .book_defs import book
from .book_lore import org_dossier, place_dossier, places
from .i18n import tr
from .models import ContentBlock, Entity, EntityLink, MapNode

# подписи связей, которые ставит сам интерфейс (ShipSheet: знакомый экипажа)
UI_LINK_LABELS = {"ru": ["знакомый экипажа"], "en": ["crew contact"]}
# прежние названия карты сектора, которые ставил код до локализации
OLD_SECTOR_NAMES = {"ru": ("Сектор Procyon",), "en": ("Procyon sector",)}
CHARACTER_LISTS = {"playbook": "PLAYBOOKS", "heritage": "HERITAGES", "vice": "VICES",
                   "trauma": "TRAUMAS"}


def _pairs(old: list, new: list) -> dict:
    return {a: b for a, b in zip(old, new) if a != b}


def _swap(value, table: dict):
    if isinstance(value, list):
        return [table.get(v, v) if isinstance(v, str) else v for v in value]
    return table.get(value, value) if isinstance(value, str) else value


def _block(db: Session, campaign_id: str, entity_id: str, title: str) -> ContentBlock | None:
    return db.query(ContentBlock).filter_by(
        campaign_id=campaign_id, entity_type="entity", entity_id=entity_id, title=title,
    ).first()


def _dossier(db: Session, cid: str, e: Entity, key: str, old: str, new: str,
             text_old: str, text_new: str) -> None:
    b = _block(db, cid, e.id, tr(f"content.lore.{key}", lang=old))
    if b is None:
        return
    b.title = tr(f"content.lore.{key}", lang=new)
    if b.content == text_old:
        b.content = text_new


def retranslate(db: Session, campaign_id: str, old: str, new: str) -> None:
    if old == new:
        return
    bo, bn = book(old), book(new)
    so, sn = langpack.schema(old), langpack.schema(new)
    ents = db.query(Entity).filter_by(campaign_id=campaign_id).all()

    systems = _pairs(so.SYSTEMS, sn.SYSTEMS)
    orgs = {a["name"]: (a, b) for a, b in zip(bo.ORGS, bn.ORGS)}
    spots = {a["name"]: (a, b) for (_s, a), (_t, b) in zip(places(old), places(new))}
    lists = {field: _pairs(getattr(so, attr), getattr(sn, attr))
             for field, attr in CHARACTER_LISTS.items()}
    sizes = _pairs(bo.SHIP_SIZES, bn.SHIP_SIZES)
    classes = {key: (t.get("ship_class"), bn.SHIP_TYPES.get(key, {}).get("ship_class"))
               for key, t in bo.SHIP_TYPES.items()}

    for e in ents:
        fields = dict(e.fields or {})
        if e.kind == "faction" and e.name in orgs:
            a, b = orgs[e.name]
            e.name = b["name"]
            if e.summary == a.get("blurb", ""):
                e.summary = b.get("blurb", "")
            _dossier(db, campaign_id, e, "org_block", old, new,
                     org_dossier(a, old), org_dossier(b, new))
        elif e.kind == "location" and e.name in spots:
            a, b = spots[e.name]
            e.name = b["name"]
            if e.summary == a.get("text", ""):
                e.summary = b.get("text", "")
            _dossier(db, campaign_id, e, "place_block", old, new,
                     place_dossier(a, old), place_dossier(b, new))
        elif e.kind == "character":
            for field, table in lists.items():
                if field in fields:
                    fields[field] = _swap(fields[field], table)
        elif e.kind == "ship":
            if e.name == tr("content.ship_unnamed", lang=old):
                e.name = tr("content.ship_unnamed", lang=new)
            if "size" in fields:
                fields["size"] = _swap(fields["size"], sizes)
            was, now = classes.get(fields.get("ship_type", ""), (None, None))
            if was and now and fields.get("ship_class") == was:
                fields["ship_class"] = now
            if isinstance(fields.get("heat"), dict):
                fields["heat"] = {systems.get(k, k): v for k, v in fields["heat"].items()}
        if "system" in fields:
            fields["system"] = _swap(fields["system"], systems)
        if fields != (e.fields or {}):
            e.fields = fields

    links = {**_pairs(list(so.LINK_LABEL_KEYS), list(sn.LINK_LABEL_KEYS)),
             **_pairs(UI_LINK_LABELS[old], UI_LINK_LABELS[new])}
    for link in db.query(EntityLink).filter_by(campaign_id=campaign_id).all():
        if link.label in links:
            link.label = links[link.label]

    for node in db.query(MapNode).filter_by(campaign_id=campaign_id).all():
        if node.name in (tr("content.sector", lang=old), *OLD_SECTOR_NAMES[old]):
            node.name = tr("content.sector", lang=new)

    _rules(db, campaign_id, old, new)


def _rules(db: Session, campaign_id: str, old: str, new: str) -> None:
    """Книжные разделы вырезок, которые ГМ не переименовывал: подпись и заметка — с новой
    книги. Страницы меняются, только если в разделе ровно страницы книги в её порядке:
    раздел, где ГМ что-то добавил, убрал или переставил, — уже его, страницы остаются."""
    from .routers.rules import OWNER, SECTION, SHOT, book_index, page_ref

    try:
        ia, ib = book_index(old), book_index(new)
    except (OSError, ValueError):
        return
    pairs = {a.get("title", ""): (a, b) for a, b in zip(ia.get("sections", []), ib.get("sections", []))}
    q = db.query(ContentBlock).filter_by(campaign_id=campaign_id, entity_type=OWNER)
    for sec in q.filter_by(block_type=SECTION).all():
        if sec.title not in pairs:
            continue
        a, b = pairs[sec.title]
        sec.title = b.get("title", "")
        if sec.content == a.get("note", ""):
            sec.content = b.get("note", "")
        items = q.filter_by(entity_id=sec.id).order_by(ContentBlock.order).all()
        # вырезки до двух книг лежат без каталога — это страницы русской
        def norm(content: str) -> str:
            if old != "ru" or not content.startswith("media:"):
                return content
            return "media:" + content.removeprefix("media:").removeprefix("rules/")

        def caption(page: dict, lang: str) -> str:
            label = page.get("label", "")
            return tr("content.page", lang=lang, label=label) if label else ""

        have = [(norm(i.content), i.title) if i.block_type == SHOT else None for i in items]
        want = [(f"media:{p.get('file', '')}" if old == "ru" else page_ref(p.get("file", ""), old),
                 caption(p, old)) for p in a.get("pages", [])]
        if not items or have != want:
            continue
        start, author = items[0].order, items[0].created_by
        for i in items:
            db.delete(i)
        for j, p in enumerate(b.get("pages", [])):
            db.add(ContentBlock(
                campaign_id=campaign_id, entity_type=OWNER, entity_id=sec.id, block_type=SHOT,
                title=caption(p, new), content=page_ref(p.get("file", ""), new), order=start + j,
                created_by=author, created_by_gm=True, visibility="gm",
            ))
