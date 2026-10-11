"""Промптинг: из описания ГМа в промпт рисующей модели.

Разделение модулей повторяет разделение ответственности:

* ``lore``   — мир и работа с описанием ГМа; от рисующей модели не зависит;
* ``schema`` — форма ответа хаба (слоты), контракт между Квеном и сборкой;
* ``kit``    — дефолты плюс правки ГМа, сборка инструкции для хаба;
* ``zimage`` — рендерер Z-Image-Turbo: строка тегов без весов и без негатива.
"""
from __future__ import annotations

from . import zimage
from .kit import (
    KIT_SECTIONS,
    NEWS_SECTIONS,
    WARDROBE_SLOTS,
    apply_outfit,
    default_kit,
    kit_head_block,
    kit_system_prompt,
    merge_kit,
    put_view,
)
from .lore import (
    AGE_BANDS,
    ARENAS,
    EARTH_WORDS,
    FRAME_ANCHORS,
    KINDS,
    PERSON_ROLES,
    REGISTER_ORDER,
    norm_register,
    swap_earth_words,
    VIEW_ORDER,
    VIEWS,
)
from .schema import (
    DEFAULT_INPAINT_META_PROMPT,
    INPAINT_PROMPT_SCHEMA,
    slots_schema,
)
from .zimage import build_prompt, instruction_addendum

__all__ = [
    "AGE_BANDS",
    "ARENAS",
    "DEFAULT_INPAINT_META_PROMPT",
    "EARTH_WORDS",
    "FRAME_ANCHORS",
    "INPAINT_PROMPT_SCHEMA",
    "KINDS",
    "KIT_SECTIONS",
    "NEWS_SECTIONS",
    "PERSON_ROLES",
    "REGISTER_ORDER",
    "norm_register",
    "VIEWS",
    "VIEW_ORDER",
    "WARDROBE_SLOTS",
    "apply_outfit",
    "build_prompt",
    "default_kit",
    "instruction_addendum",
    "kit_head_block",
    "kit_system_prompt",
    "merge_kit",
    "put_view",
    "slots_schema",
    "swap_earth_words",
    "zimage",
]
