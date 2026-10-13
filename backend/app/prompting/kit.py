"""Prompt kit: defaults from code plus admin edits.

The server stores only the differences from the defaults, so code updates arrive on their own.
The wardrobe is what a particular table found, so it lives with the campaign.
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
# journalist dispatch sections have nothing to do with the drawing model
NEWS_SECTIONS = ("news_templates", "dispatch_journalists", "dispatch_lenses",
                 "comment_manners", "comment_lengths", "comment_writing")

# Parts a look replaces whole. Everything else in the frame comes from the
# description: a look covers what the subject wears and nothing more
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
        # the wardrobe is empty in code: looks are not a property of the world, they are
        # what a particular table found, and are created from a good generation
        "wardrobe": {},
        "news_templates": dict(NEWS_TEMPLATES),
        "dispatch_journalists": {k: dict(v) for k, v in DISPATCH_JOURNALISTS.items()},
        "dispatch_lenses": dict(DISPATCH_LENSES),
        "comment_manners": dict(COMMENT_MANNERS),
        "comment_lengths": dict(COMMENT_LENGTHS),
        "comment_writing": dict(COMMENT_WRITING),
    }


def outfit_slots(kit: dict, key: str) -> dict:
    """A look's clothing: good clothing is repeated word for word, while the hub rewrites it
    on every run — that is how ten rings turned into "several rings"."""
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
    """Apply edits over the defaults. Dicts are merged by key, everything else
    is replaced whole. null in an edit means the entry is deleted, including one that came from code."""
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
    """Store only the differences from code: an entry equal to the default would otherwise freeze on the old text."""
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
    """Store null only where it hides an entry from code; a deleted added entry just disappears."""
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
