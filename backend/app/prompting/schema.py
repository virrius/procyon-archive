"""Structured output для хаба: форма ответа Квена.

Модель не пишет промпт целиком — она заполняет слоты, а строку собирает
рендерер. Схема слотов и есть контракт между хабом и сборкой; правка по маске
живёт отдельно, там промпт и негатив по-прежнему пишет модель.
"""
from __future__ import annotations

from .kit import default_kit
from .lore import AGE_BANDS, ARENAS, EN, FRAME_ANCHORS, PERSON_ROLES

# Модель не пишет промпт целиком — она заполняет слоты, а собирает строку код.
# Рамка кадра, порядок тегов, стилевой блок и длина заданы схемой, а не
# дисциплиной модели: именно на них приходился почти весь брак выхлопа.
def slots_schema(kind: str, view: str = "interior", kit: dict | None = None) -> dict:
    """Схема слотов по направлению. Порядок полей — порядок рассуждения: guided
    decoding идёт по полям, поэтому черновик стоит первым — модель обязана описать
    кадр целиком прежде, чем выбирать якорь и сжимать его в теги. Якорь до брифа
    выбирался наугад: пять ролей из пятнадцати уходили в «mechanic»."""

    def arr(lo, hi):
        return {"type": "array", "items": {"type": "string"}, "minItems": lo, "maxItems": hi}

    # Окна энкодера хватает на восемьдесят тегов, и дороже недосказать — особенно
    # одежду, которая на этой модели единственная несёт сеттинг
    n_wear = arr(4, 6)
    n_pair = arr(2, 3)
    n_form = arr(3, 5)
    n_actors = arr(2, 4)

    anchors = (kit or default_kit()).get("anchors") or {}
    props: dict[str, dict] = {}
    if kind == "person":
        props["brief"] = {"type": "string"}
        props["role"] = {"type": "string",
                         "enum": list(anchors.get("person") or PERSON_ROLES)}
        props |= {
            "subject": {"type": "string"},
            "age": {"type": "string",
                    "enum": list((kit or default_kit()).get("ages", AGE_BANDS))},
            "face": n_pair,
            "build": {"type": "string"},
            "pose": {"type": "string"},
            "wear": n_wear,
            "gear": n_pair,
            "location": n_pair,
            "place_object": {"type": "string"},
            "depth": {"type": "string"},
            "tech_marker": {"type": "string"},
            "light": {"type": "string"},
        }
    elif kind == "frame":
        props["brief"] = {"type": "string"}
        # у планеты якорь постоянный и зашит в рамку
        view_anchors = anchors.get(f"frame:{view}") or FRAME_ANCHORS.get(view)
        if view_anchors:
            props["anchor"] = {"type": "string", "enum": list(view_anchors)}
        props |= {
            "subject": {"type": "string"},
            "form": n_form,
            "marks": n_pair,
            "surround": n_pair,
            "tech_marker": {"type": "string"},
            "light": {"type": "string"},
            "no_people": {"type": "boolean"},
        }
    else:  # action
        props["brief"] = {"type": "string"}
        props["arena"] = {"type": "string", "enum": list(ARENAS)}
        props |= {
            "action": {"type": "string"},
            "actors": n_actors,
            "crew": n_pair,
            "place": {"type": "string"},
            "place_detail": n_pair,
            "effects": n_pair,
            "light": {"type": "string"},
        }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ImageSlots",
            "schema": {"type": "object", "properties": props,
                       "required": list(props), "additionalProperties": False},
            "strict": True,
        },
    }


INPAINT_PROMPT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "ImagePrompt",
        "schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "negative_prompt": {"type": "string"},
            },
            "required": ["prompt", "negative_prompt"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


DEFAULT_INPAINT_META_PROMPT = (
    "You write the prompt for repainting one masked region of an existing image. "
    "You are given the prompt the image was drawn from (may be unknown) and the "
    "GM's request for what the region must become (often Russian). Return the "
    "repaint prompt in English.\n\n"
    "TWO HARD RULES, above everything else:\n"
    "A. Every object word in your output must come from the GM's request or from "
    "the original prompt. Nothing from your imagination, nothing from these "
    "instructions, however typical for the genre it feels.\n"
    "B. The requested thing never appears in negative_prompt — not its name, not "
    "a synonym, not an adjective describing it. Negating what the GM asked for "
    "guarantees a wrong image.\n\n"
    "HOW THE REPAINT PASS SEES IT: the image model gets a close crop around the "
    "masked region, not the whole picture, and it cannot know what you meant — "
    "only what you wrote. The requested thing is therefore the SUBJECT of the "
    "prompt; the original prompt is only context, carried in a few tags so style "
    "and light hold. A prompt that still describes the whole original scene makes "
    "the model refill the region with more of that same scene instead of the "
    "requested thing.\n\n"
    "PROMPT, in this order:\n"
    "1. the original opening style tags verbatim — they hold the medium\n"
    "2. the requested thing as the subject: 2-5 concrete tags — what it is, its "
    "material, its state of wear. Weight the single most important of these tags "
    "by wrapping its words in parentheses and appending a colon and a number "
    "between 1.2 and 1.4 before the closing parenthesis. Write that tag once, "
    "only in weighted form\n"
    "3. 4-6 context tags taken from the original prompt: the place, the surface "
    "the thing sits against or hangs over, the light and its colour. Nothing "
    "else\n"
    "4. every original tag the request contradicts is dropped here and moved to "
    "negative_prompt\n"
    "12-16 tags total. Never negate in the prompt: the words no, without, not, "
    "minimal must not appear there — exclusions belong to negative_prompt.\n\n"
    "IF THE ORIGINAL PROMPT IS UNKNOWN: open with \"sci-fi digital painting, "
    "confident brushwork, clean skin and fabric rendering, soft atmospheric "
    "light\" and then write only the subject tags of step 2. No place, "
    "no background, no lighting — you cannot see the picture, and a guessed "
    "setting repaints the region for a different scene than the one around it. "
    "The surrounding pixels already carry the light and the place.\n\n"
    "FLAVOUR of the subject itself: used-future — worn, repaired, patched where "
    "the GM's request implies wear, but never dirty or sterile by default. No "
    "proper nouns of factions or places, visuals only. If a word could name a "
    "sea vessel or its parts, qualify it with space- or star- so the model draws "
    "spacecraft, not boats.\n\n"
    "NEGATIVE_PROMPT: start from the original negative if given, minus what now "
    "contradicts the request. Add the thing the request replaces — whatever used "
    "to occupy the region, if the request names or implies it. 8-14 tags, no "
    "colour words. Rule B applies to every tag you add.\n\n"
    "Both fields English only, comma-separated tags only, no Midjourney flags, "
    "no prose, no explanation."
)
if EN:
    DEFAULT_INPAINT_META_PROMPT = DEFAULT_INPAINT_META_PROMPT.replace(" (often Russian)", "", 1)
