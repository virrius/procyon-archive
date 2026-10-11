"""Промпт-кит: дефолты из кода плюс правки ГМа, и сборка инструкции для хаба.

Кит — единственная форма, в которой ГМ видит и правит промптинг: кампания хранит
только отличия от дефолта, поэтому обновления кода доезжают до неё сами.
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
    AGE_BANDS,
    REGISTER_HINTS,
    COMMON_LAW,
    FRAME_ANCHORS,
    HEADS,
    KINDS,
    REGISTERS,
    SLOT_RULES,
    VIEW_LAWS,
    VIEW_TITLES,
    VIEWS,
    register_text,
    tune_world,
)

# ── промпт-кит: всё, что ГМ может посмотреть и поправить ───────────────────
# Кампания хранит только изменённые ключи, остальное берётся отсюда. Разделение
# на блоки повторяет инструкцию хабу: голова направления, закон сеттинга, законы
# подтипов, словари регистров, разметка слотов, якоря и возраст.
KIT_SECTIONS = ("heads", "common_law", "views", "registers", "slot_rules", "anchors",
                "ages", "wardrobe", "news_templates", "dispatch_journalists", "dispatch_lenses",
                "comment_manners", "comment_lengths", "comment_writing")
# секции депеш журналиста к рисующей модели отношения не имеют
NEWS_SECTIONS = ("news_templates", "dispatch_journalists", "dispatch_lenses",
                 "comment_manners", "comment_lengths", "comment_writing")

# Слоты, которые наряд подменяет целиком. Всё остальное в кадре остаётся от
# описания: наряд отвечает за то, во что одет субъект, и ни за что больше
WARDROBE_SLOTS = ("wear",)


def default_kit() -> dict:
    return {
        "heads": {k: HEADS[k] for k in KINDS},
        "common_law": COMMON_LAW,
        "slot_rules": dict(SLOT_RULES),
        "views": {k: {"title": VIEW_TITLES[k], "law": VIEW_LAWS[k]} for k in VIEWS},
        "registers": {k: {"title": v["title"], "hint": REGISTER_HINTS.get(k, ""),
                          "look": LOOKS.get(k, ""), "corner": CORNERS.get(k, ""), "vocab": v["vocab"],
                          "vocab_person": v.get("vocab_person", ""),
                          "vocab_ship": v.get("vocab_ship", "")}
                      for k, v in REGISTERS.items()},
        # якорь персонажа строку не ведёт — от ролей в схеме остался только перечень
        "anchors": {f"frame:{k}": dict(v) for k, v in FRAME_ANCHORS.items()},
        "ages": dict(AGE_BANDS),
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
    """Слоты наряда: что подставить вместо одежды и снаряжения.

    Наряд ложится поверх слотов уже после хаба, а не подсказкой ему: удачная
    одежда должна повторяться дословно, а модель на каждом прогоне переписывает
    её заново — так десять колец и превращались в «несколько колец».
    """
    item = (kit.get("wardrobe") or {}).get(key)
    if not isinstance(item, dict):
        return {}
    out = {}
    for slot in WARDROBE_SLOTS:
        value = [str(x).strip() for x in (item.get(slot) or []) if str(x).strip()]
        if value:
            out[slot] = value
    return out


def apply_outfit(kit: dict, slots: dict, key: str) -> dict:
    """Подставить наряд в слоты. Пустой ключ и незнакомый наряд ничего не меняют."""
    if not key:
        return slots
    slots.update(outfit_slots(kit, key))
    return slots


def merge_kit(base: dict, over: dict | None, keep_nulls: bool = False) -> dict:
    """Наложить правки ГМа на дефолт. Словари сливаются по ключам, всё остальное
    заменяется целиком: список тегов правят целиком, а не по элементу.
    null в правке — запись удалена, в том числе пришедшая из кода."""
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


def kit_head_block(kit: dict, kind: str, view: str = "interior") -> str:
    """Та часть кита, которую редактор правит как связный текст."""
    head = kit["heads"][kind] + "\n" + kit["common_law"]
    return put_view(kit, head, view) if kind == "frame" else head


def put_view(kit: dict, text: str, view: str) -> str:
    """Подставить закон подтипа кадра на место {view}."""
    law = ((kit.get("views") or {}).get(view) or {}).get("law") or VIEW_LAWS.get(view, "")
    return text.replace("{view}", law)


def kit_system_prompt(kit: dict, kind: str, register: str, view: str = "interior") -> str:
    """Регистр необязателен: пустой — словаря нет, слоты пишутся общим языком мира.

    Словарь регистра сужает речь Квена под один угол сеттинга. Это полезно, когда
    ГМ такой угол выбрал, и мешает, когда не выбрал: тогда обжитая техника
    навязывается хай-теку и наоборот.
    """
    reg = kit["registers"].get(register) if register else None
    rules = kit["slot_rules"]
    rules_text = rules.get(kind, "") if isinstance(rules, dict) else str(rules)
    head = tune_world(kit_head_block(kit, kind, view), register)
    return head + ("\n" + register_text(reg, kind, view) if reg else "") + "\n" + rules_text

