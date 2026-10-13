"""Prompting: from the GM's description to the drawing model's prompt and to dispatches.

* ``lore``     — the world for the drawing side: frame subtypes, registers, anchors, replacing Earth words;
* ``prose``    — the hub instruction and assembling the prompt line from its parts;
* ``inpaint``  — the area edit instruction;
* ``kit``      — defaults plus admin edits;
* ``dispatch`` — journalist dispatches and comments.
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
