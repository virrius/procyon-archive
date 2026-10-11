"""Промптинг: из описания ГМа в промпт рисующей модели и в депеши.

* ``lore``     — мир для рисующей стороны: подтипы кадра, регистры, якоря, подмена земных слов;
* ``prose``    — инструкция хабу и сборка строки промпта из его частей;
* ``inpaint``  — инструкция правки области;
* ``kit``      — дефолты плюс правки админа;
* ``dispatch`` — депеши журналистов и отклики.
"""
from __future__ import annotations

from .inpaint import DEFAULT_INPAINT_META_PROMPT, INPAINT_PROMPT_SCHEMA
from .kit import KIT_SECTIONS, NEWS_SECTIONS, WARDROBE_SLOTS, default_kit, merge_kit
from .lore import FRAME_ANCHORS, KINDS, VIEWS, norm_register, swap_earth_words

__all__ = [
    "DEFAULT_INPAINT_META_PROMPT",
    "FRAME_ANCHORS",
    "INPAINT_PROMPT_SCHEMA",
    "KINDS",
    "KIT_SECTIONS",
    "NEWS_SECTIONS",
    "VIEWS",
    "WARDROBE_SLOTS",
    "default_kit",
    "merge_kit",
    "norm_register",
    "swap_earth_words",
]
