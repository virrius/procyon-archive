"""Промпт-кит: дефолты из кода плюс правки админа.

Сервер хранит только отличия от дефолта, поэтому обновления кода доезжают сами.
Гардероб — находки конкретного стола, он живёт у кампании.
"""
from __future__ import annotations

from .dispatch import (
    COMMENT_LENGTHS,
    COMMENT_MANNERS,
    COMMENT_WRITING,
    DISPATCH_JOURNALISTS,
    DISPATCH_LENSES,
    NEWS_TEMPLATES,
)
from .prose import CORNERS, LOOKS
from .lore import (
    REGISTER_HINTS,
    FRAME_ANCHORS,
    REGISTERS,
    VIEW_LAWS,
    VIEW_TITLES,
    VIEWS,
)

KIT_SECTIONS = ("views", "registers", "anchors", "wardrobe", "news_templates", "dispatch_journalists",
                "dispatch_lenses", "comment_manners", "comment_lengths", "comment_writing")
# секции депеш журналиста к рисующей модели отношения не имеют
NEWS_SECTIONS = ("news_templates", "dispatch_journalists", "dispatch_lenses",
                 "comment_manners", "comment_lengths", "comment_writing")

# Части, которые наряд подменяет целиком. Всё остальное в кадре остаётся от
# описания: наряд отвечает за то, во что одет субъект, и ни за что больше
WARDROBE_SLOTS = ("wear",)


def default_kit() -> dict:
    return {
        "views": {k: {"title": VIEW_TITLES[k], "law": VIEW_LAWS[k]} for k in VIEWS},
        "registers": {k: {"title": v["title"], "hint": REGISTER_HINTS.get(k, ""),
                          "look": LOOKS.get(k, ""), "corner": CORNERS.get(k, ""), "vocab": v["vocab"],
                          "vocab_person": v.get("vocab_person", ""),
                          "vocab_ship": v.get("vocab_ship", "")}
                      for k, v in REGISTERS.items()},
        "anchors": {f"frame:{k}": dict(v) for k, v in FRAME_ANCHORS.items()},
        # гардероб пуст в коде: наряды — не свойство мира вообще, а находки
        # конкретного стола, и заводятся из удачной генерации
        "wardrobe": {},
        "news_templates": dict(NEWS_TEMPLATES),
        "dispatch_journalists": {k: dict(v) for k, v in DISPATCH_JOURNALISTS.items()},
        "dispatch_lenses": dict(DISPATCH_LENSES),
        "comment_manners": dict(COMMENT_MANNERS),
        "comment_lengths": dict(COMMENT_LENGTHS),
        "comment_writing": dict(COMMENT_WRITING),
    }


def outfit_slots(kit: dict, key: str) -> dict:
    """Одежда наряда: удачная одежда повторяется дословно, а хаб на каждом прогоне
    переписывает её заново — так десять колец и превращались в «несколько колец»."""
    item = (kit.get("wardrobe") or {}).get(key)
    if not isinstance(item, dict):
        return {}
    out = {}
    for slot in WARDROBE_SLOTS:
        value = [str(x).strip() for x in (item.get(slot) or []) if str(x).strip()]
        if value:
            out[slot] = value
    return out


def merge_kit(base: dict, over: dict | None, keep_nulls: bool = False) -> dict:
    """Наложить правки на дефолт. Словари сливаются по ключам, всё остальное
    заменяется целиком. null в правке — запись удалена, в том числе пришедшая из кода."""
    if not over:
        return base
    out = dict(base)
    for key, value in over.items():
        if value is None and not keep_nulls:
            out.pop(key, None)
        elif key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge_kit(out[key], value, keep_nulls)
        else:
            out[key] = value
    return out


def strip_defaults(over: dict, base: dict | None) -> dict:
    """Хранить только отличия от кода: запись, совпавшая с дефолтом, иначе застынет на старом тексте."""
    out = {}
    for key, value in over.items():
        known = isinstance(base, dict) and key in base
        if known and value == base[key]:
            continue
        if known and isinstance(value, dict) and isinstance(base[key], dict):
            value = strip_defaults(value, base[key])
            if not value:
                continue
        out[key] = value
    return out


def prune_nulls(over: dict, base: dict | None) -> dict:
    """null храним только там, где он гасит запись кода; удалённое добавленное просто исчезает."""
    out = {}
    for key, value in over.items():
        known = isinstance(base, dict) and key in base
        if value is None:
            if known:
                out[key] = None
        elif isinstance(value, dict):
            out[key] = prune_nulls(value, base.get(key) if known else None)
        else:
            out[key] = value
    return out
