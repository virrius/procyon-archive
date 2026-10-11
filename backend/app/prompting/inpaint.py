"""Правка области: хаб переписывает просьбу ГМа в короткий абзац для куска кадра."""
from __future__ import annotations

from .lore import EN
from .prose import STYLE

INPAINT_PROMPT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ImagePrompt",
        "schema": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


DEFAULT_INPAINT_META_PROMPT = (
    "You write the prompt for repainting one masked region of an existing picture. You are given the "
    "prompt the picture was drawn from (may be unknown) and the GM's request for what the region must "
    "become (often Russian). Return the repaint prompt in English.\n\n"
    "HOW THE REPAINT SEES IT: the image model gets a close crop around the masked region, not the whole "
    "picture, and reads plain descriptive sentences. The requested thing is the subject of the prompt; "
    "the original prompt is only context. A prompt that still describes the whole original scene makes "
    "the model refill the region with more of that scene instead of the requested thing.\n\n"
    "WRITE one short paragraph of 40 to 80 words:\n"
    "1. the opening style sentence of the original prompt, word for word — it holds the manner;\n"
    "2. the requested thing as the subject: what it is, its shape, material and state of wear, in "
    "concrete visual words taken from the GM's request;\n"
    "3. one sentence of context from the original prompt: the surface or place the thing sits against "
    "and where the light comes from. Whatever of the original the request contradicts is left out.\n\n"
    "Every object you name comes from the GM's request or from the original prompt — nothing invented. "
    "Write only what is there: never no, not or without. No proper names, no weights or brackets, no "
    "lists of tags.\n\n"
    f"IF THE ORIGINAL PROMPT IS UNKNOWN: open with \"{STYLE}\" and write only the subject — no place, no "
    "background, no light: the pixels around the region already carry them, and a guessed setting "
    "repaints the region for a different scene.\n\n"
    "FLAVOUR of the subject: far future, worn and repaired where the request implies wear. A word that "
    "could name a sea vessel or an aircraft is written as a spacecraft."
)
if EN:
    DEFAULT_INPAINT_META_PROMPT = DEFAULT_INPAINT_META_PROMPT.replace(" (often Russian)", "", 1)
