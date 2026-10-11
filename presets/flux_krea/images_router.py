from __future__ import annotations

import io
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageFilter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import history as journal
from ..config import settings
from ..db import get_db
from ..deps import editor, gm_only, viewer
from ..image_prompts import (
    EARTH_WORDS,
    FRAME_LINES,
    HEADS,
    KINDS,
    KIT_SECTIONS,
    PLANS,
    PLAN_ORDER,
    REGISTER_ORDER,
    REGISTERS,
    SCALES,
    SHOTS_PLACE,
    STYLES,
    STYLE_ORDER,
    default_kit,
    head_block,
    kit_head_block,
    kit_system_prompt,
    merge_kit,
    system_prompt,
)
from ..models import Attachment, Campaign, Entity, ImageGenJob
from ..visibility import Viewer, apply_scope, can_see
from .entities import get_visible_entity
from .files import ALLOWED, MAX_BYTES, drop_files

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["images"])
worker_router = APIRouter(prefix="/api/worker", tags=["images-worker"])

CANDIDATES_PER_JOB = 4
ACTIVE_STATUSES = ("pending", "claimed", "ready")

# кандидат портрета живёт до выбора и виден только ГМу; кадр кампании остаётся
# насовсем и по умолчанию открыт столу
CANDIDATE = "image_candidate"
SCENE_FRAME = "scene_frame"
# служебные вложения заявки на инпеинт: маска и подготовленная копия исходника.
# Живут ровно столько, сколько заявка, и наружу не отдаются
MASK = "image_mask"
SOURCE = "image_source"
JOB_TEMP = (MASK, SOURCE)

# срок годности heartbeat: три пропущенных подряд при интервале воркера в 10 с.
# Единственное свидетельство живого воркера — свежий пинг; отсутствие пинга
# трактуем как выключенную генерацию, причину не различаем
HEARTBEAT_TTL = 30
_worker_beat: dict = {}

# Заявку в claimed держит ровно один воркер. Умер он (перезапуск, OOM, закрытая
# консоль) — вернуть её некому: она висит вечно, а картинка-исходник остаётся
# занятой навсегда. Поэтому висяки подбираем сами.
# grace — сколько ждём после claim, прежде чем верить пингу: первый пинг с job_id
# приходит не мгновенно. max — потолок на всю пачку из 4 кандидатов
CLAIM_GRACE = 90
CLAIM_MAX = 25 * 60
# «пинг свежий, но воркер занят другим» — сигнал слабее: воркеров может оказаться
# запущено несколько, и пингом они перебивают друг друга. Поэтому по нему ждём
# дольше самой длинной честной пачки из 4 кандидатов
CLAIM_IDLE = 12 * 60
MAX_ATTEMPTS = 2
LOST_ERROR = "воркер потерял заявку (перезапуск или сбой) — она вернулась в очередь"
LOST_FINAL = "воркер дважды не довёл заявку до конца — проверь, что он и ComfyUI живы"

DEFAULT_IMG_META_PROMPT = """\
You turn a GM's short description (often Russian) into an English tag list for a local SDXL model. Tags, not prose. You also classify the shot: the pipeline attaches the negative prompt itself, so you never write one.

FOLLOW THE GM LITERALLY. Sex, age, species, build, skin, hair, scars, implants, clothing, hull and props come from their text and nowhere else. Never change what they stated: if they wrote a woman, the subject is a woman. Never invent ethnicity, and never invent an age — if they gave none, write none.

WHAT KIND OF SUBJECT IS IT? Decide this first, it sets the framing.
A LIVING BEING — anyone who acts as a person: human, xeno, or a machine built to work alongside them. Extra limbs, scales, fur, a metre of height or three, a chassis instead of skin — none of it changes this. A six-limbed mechanic and a battered working robot are both characters and are framed as characters. The test is simple: if the GM gave it a name, a job or a history, it is somebody, and somebody is always a portrait — only an unmanned thing nobody is inside of is an object. A synthetic with a face, two arms and clothes is a living being here however damaged or inhuman it is: a mask instead of a face, a cracked shell, wires hanging out of it change nothing. Its housing is a body, never a hull, and it is framed like a person. Frame it medium shot, waist up, face clearly visible, three-quarter view, unless the GM asked for another framing; full body only when they asked for it. Classify shot as portrait.
A THING — starship, vehicle, weapon, artifact, machine, structure. It has neither waist nor face, so the portrait framing above is wrong for it. Put the whole of it in frame, seen from a three-quarter angle and slightly below. The words waist up, face, expression and portrait belong to living beings and must not appear. Classify shot as object.

NAMES. The image model has never heard of this galaxy and knows no name in it. Never write a proper noun — not a character's name, not a ship's, not a planet's, not a faction's. Replace it with what it looks like, using the visual glossary below. The words guild, legion, hegemony, syndicate and cult are names too: write what is seen, never the organisation. These are replacements for names, never extra ingredients: a portrait must not receive ruins because ruins are listed here.

HOW THIS GALAXY LOOKS. Reach for an entry only when the GM's own words point at that thing. A character they described is built from their description; an unfamiliar name is not a licence to pick an entry and dress them in something they never mentioned.
Imperial power, nobles, governors, officials — polished dark uniform, high collar, gold braid, formal sash.
Imperial soldiers, the military off-planet — matte armour plate over dark fatigues, full helmet, rank studs.
System police — dark green and black uniform, sidearm.
Licensed engineers and drive-smiths — clean coveralls with a badge, tool rig, precision instruments; corporate property is deliberately clean and well lit while everything else is worn.
Organised labour and union crews — worn coveralls, a blue stripe on the sleeve, tool belt.
Criminal syndicates and assassins — dark layered civilian clothes, concealed blades, quiet money.
Pirates — mismatched layers, patched armour, salvaged plating, trophies taken from ships.
Mystics, cultists, seekers — ascetic cloth over a tech underlayer, faint glowing veins, hooded.
Precursor ruins and artifacts — black glassy monoliths, strange faces and forms carved throughout, unbroken seamless material that hides whatever works inside, far older than everything around them.
A jumpgate — a colossal ring fixed in space, carved faces and forms across its face, material unlike any metal.
Urbots, working robots — utilitarian machine bodies, mismatched replacement parts, worn joints.
The strange, the Way, things touched by it — bioluminescence, wet organic growth over metal, unsettling symmetry.
Ocean xenos — black eyes, skin in shades of blue, purple and green, tentacles instead of hair.
Big scaled xenos — ten feet tall, reptile scales, dock labour and heavy lifting.
Small furry xenos — three feet tall, six limbs, delicate engineer's tools.
Ships of this galaxy — human-built hulls, welded patches, mismatched armour plates, exposed conduit, jump drive rings.

BODIES AS DESCRIBED, NOT AS FLATTERED. Never make a body fitter, younger or more heroic than the GM wrote. Heavy is heavy: a big man with a gut is a hulking slab of a man with a hanging belly and thick slack arms, not a muscular hero — the word muscular is wrong there and so is athletic, toned and chiselled. Fat, gaunt, stooped, short, ageing and scarred all survive into the prompt exactly as given. Weight shows in posture too: sloped heavy shoulders, a thick neck, a low centre of gravity, clothes straining where the body pushes them.

WEAPONS AND GEAR ARE LITERAL. The GM may describe a thing by comparison — a shield like an iron wall, a gun like a pipe. Write the object plainly and let the comparison set its size and material: a massive slab of iron carried as a shield, a stubby hand-held grenade launcher. A comparison written as-is confuses the model about what is even in the frame.

CASUAL RUSSIAN. The GM types the way they talk, and slang names for clothes and bodies do not survive a word-by-word translation — write the physical thing instead. An "алкоголичка" is a sleeveless undershirt, a "косуха" is a biker jacket, "берцы" are heavy combat boots, "тельняшка" is a striped undershirt, "ветровка" is a light windbreaker, "балахон" is a loose hooded robe. A "пузико" or "брюхо" is a heavy belly, "качок" is heavily muscled, "громадный" is huge and broad-shouldered, "щуплый" is skinny and slight, "мордоворот" is a thug with a brutal face. Build matters as much as clothing: when they name a body type it belongs in the subject or right beside it, never dropped.

TONE — SPACE WESTERN. This is a frontier, not a clean future: the far edge of an empire, worked by people who fix their own gear. It shows in the clothes and the props you fill in when the GM left them open — long worn coats and dusters, leather and canvas over practical work clothes, a holstered sidearm worn like a tool, boots, gloves, a scarf against dust, hats and goggles, a belt of pouches, tattoos and hand-made repairs. Faces are weathered, hair is cut by hand. Rooms look like frontier rooms: a bar of scavenged metal, hanging bulbs, a stove, cargo crates for furniture. Light behaves like a western's — low sun, long shadows, dust in the beam, a single lamp in a dark room. Indoors and in space that low sun does not exist: there it becomes a single hanging bulb, a work lamp, a strip light — write the light that could actually reach this place. Apply this only where the GM left a blank; it never overrides a thing they named, and it never adds a prop they did not ask for.

DESCRIBED BY ABSENCE. When the GM defines something by what it lacks, write the positive form of it instead — a face with no mouth is a smooth mouthless mask, a gate that will not light is a dark inert gate. The image model cannot subtract, so an absence written as an absence becomes the thing itself.

THE FRAME MUST READ AS SCIENCE FICTION. A dusty street, a bar, a workman in a jacket are all half a picture: without one unmistakably off-world note the shot lands as an ordinary western, which is wrong. You add that note without inventing a single new object, because it lives in what the named things are made of and lit by. Walls and floors are riveted hull plate, composite panelling, ceramic heat shielding, extruded alloy. Fastenings are welds, clamps and cable conduit, never nails and planks. Clothing has synthetic weave, sealed seams, a charge pack on the belt, a visor pushed up. Light comes from arc lamps, strip lights, indicator glow, a plasma torch. Outdoors, where the GM named no built thing, the sky carries it: twin suns, a second moon, a ringed world low on the horizon, the burn of a craft climbing out. At least one tag in every prompt is a thing that could exist nowhere but off Earth.

TECH LOOK. Used future: things are old, repaired, scratched, greasy. Never sterile, never glossy, except corporate property. Science fiction, never fantasy: no elves, no horns, no wizards, no magic. Space, never the sea: always write starship, spaceport, docking bay, hangar — the bare words ship, port and dock make the model draw sailing boats.

ADD NOTHING THE GM DID NOT ASK FOR. No extra starships, stations, drones, holographic displays, screens or props, no invented colour palette, no extra characters. Your job is to render their sentence precisely, filling in only framing, light and material wear. If they described an empty frame, keep it empty.

Never negate in a slot: the words no, without and not must not appear in one. Anything that must be kept out of the frame is handled by the pipeline, not by you.

CLASSIFY THE SHOT. Return shot as portrait for a living being, object for a thing. Return no_people true only when the frame must contain nobody at all — a thing photographed alone, or a place the GM described as deserted. For a portrait it is always false.

English only, comma separated tags, no Midjourney flags, no prose, no explanation."""


DEFAULT_SCENE_META_PROMPT = """\
You are the shot director for a tabletop sci-fi campaign. The GM describes a place, often in Russian and often as raw speech with self-corrections. You turn it into an English tag list for a local SDXL model. Keep the substance, drop the filler, their last version of a thought wins. You also classify the shot: the pipeline attaches the negative prompt itself, so you never write one.

KEEP THEIR FRAME. Everything they named goes in; nothing they did not name gets added. You choose only the camera, the depth layers, the light and the material wear.

PEOPLE. If the GM put people, crowds or figures in the place, they belong in the shot and carry its mood — dress, posture, silhouette. Keep them part of the scene, not portraits: no close-up faces, no single hero centred and staring at the camera. If the GM described an empty place, leave it empty and mark no_people.

WHICH KIND OF SHOT IS THIS? Decide first, it sets both the camera and the tags you must avoid.
INTERIOR — the camera stands inside an enclosed space and walls or a ceiling hold the frame: a station corridor, a hold, a bar, a cave. Wide establishing from a doorway or a high corner.
LANDSCAPE — the camera stands in the open air on the surface of a world, with ground under it and sky over it. A landing pad, a street, a wall, a building seen from outside are all landscape: a structure filling the frame does not make the shot interior, only walls around the camera do. Wide establishing, ground level or high angle.
ORBITAL — a whole planet, moon or world seen from space, not a place on it. The frame is the full globe or a low-orbit arc of its horizon against black airless space. The planet is the single subject and carries the weight; give it 3-4 tags of its own character — terrain, weather bands, city glow on the night side — plus a thin atmosphere rim and terminator light. One planet in frame, stars faint. The words landscape, horizon line, ground level and sky must not appear in the prompt.
VOID — a structure adrift in open space: a station, a gate, a ring, a hulk. Nothing holds it up and nothing stands under it. Black airless space on every side, stars faint, light from one far source raking across the hull. The words landscape, horizon line, ground level, terrain and surface must not appear in the prompt.

NAMES. The image model has never heard of this galaxy and knows no name in it. Never write a proper noun — not a planet's name, not a station's, not a faction's, not a person's. Replace it with what it looks like, using the visual glossary below. The words guild, legion, hegemony, syndicate and cult are names too: write what is seen, never the organisation. These are replacements for names, never extra ingredients: a landscape the GM described must not receive a uniform because uniforms are listed here.

HOW THIS GALAXY LOOKS. Reach for an entry only when the GM's own words point at that thing. A place they described is built from their description; an unfamiliar name is not a licence to pick an entry and paint something they never mentioned. When they name a world and then say what it looks like, their words win and no entry applies.
Imperial power, nobles, governors, officials — polished dark uniform, high collar, gold braid, formal sash.
Imperial soldiers, the military off-planet — matte armour plate over dark fatigues, full helmet.
Licensed engineers and drive-smiths — clean coveralls with a badge, tool rig; corporate property is deliberately clean, bright and monitored while everything around it is worn.
Organised labour and union crews — worn coveralls, a blue stripe on the sleeve, tool belt.
Pirates — mismatched layers, patched armour, salvaged plating.
Mystics, cultists, seekers — ascetic cloth over a tech underlayer, faint glowing veins, hooded.
Precursor ruins and artifacts — black glassy monoliths, strange faces and forms carved throughout, unbroken seamless material that hides whatever works inside, far older than everything around them.
A jumpgate — a colossal ring fixed in space, carved faces and forms across its face, material unlike any metal.
Urbots, working robots — utilitarian machine bodies, mismatched replacement parts.
The strange, the Way, things touched by it — bioluminescence, wet organic growth over metal, unsettling symmetry.
A capital world — an ecumenopolis of neon high-rises, hovercar streams between towers, street markets in a dozen scripts.
A licensed corporate station — bright clean concourse above dim cramped working levels.
A pirate haven — a station welded together from derelict freighters, cargo containers and stolen scrap.
A crystal world — a surface of graphite and diamond, the largest formations glowing at night.
An ocean world — see-through spires rising from an underwater palace, submersibles, open-air pavilions.
A jungle world — tall walls and flamethrower emplacements holding back carnivorous growth.
A manufacturing world — thick cloud, city sprawl and toxic industrial waste to the horizon.
A mined-out world — scaffolding of bare rock, the planet stripped towards its core.
A junkyard — a free-floating mass of hulls and parts held together by magnets and cabling.

TONE — SPACE WESTERN. This is a frontier, not a clean future: the far edge of an empire, held together by people who repair their own machines. It shows in what you fill in where the GM left a blank — dust and grit over every surface, hand-painted signs and stencilled numbers, cables strung overhead, corrugated sheeting and cargo crates used as building material, a hitching line of parked craft outside a low frontier building, saloon-like bars with a scavenged metal counter and hanging bulbs, figures in long worn coats with a holstered sidearm. Light behaves like a western's: low sun raking across a dusty street, long shadows, haze in the beam, a single lamp in a dark interior, hard silhouettes against a bright doorway. Indoors and in space that low sun does not exist: there it becomes a single hanging bulb, a work lamp, a strip light — write the light that could actually reach this place. Apply this only where the GM left a blank; it never overrides what they named and never adds an object they did not ask for.

DESCRIBED BY ABSENCE. When the GM defines something by what it lacks, write the positive form of it instead — a face with no mouth is a smooth mouthless mask, a gate that will not light is a dark inert gate. The image model cannot subtract, so an absence written as an absence becomes the thing itself.

THE FRAME MUST READ AS SCIENCE FICTION. A dusty street, a bar, a workman in a jacket are all half a picture: without one unmistakably off-world note the shot lands as an ordinary western, which is wrong. You add that note without inventing a single new object, because it lives in what the named things are made of and lit by. Walls and floors are riveted hull plate, composite panelling, ceramic heat shielding, extruded alloy. Fastenings are welds, clamps and cable conduit, never nails and planks. Clothing has synthetic weave, sealed seams, a charge pack on the belt, a visor pushed up. Light comes from arc lamps, strip lights, indicator glow, a plasma torch. Outdoors, where the GM named no built thing, the sky carries it: twin suns, a second moon, a ringed world low on the horizon, the burn of a craft climbing out. At least one tag in every prompt is a thing that could exist nowhere but off Earth.

TECH LOOK. Used future: things are old, repaired, scratched, greasy. Never sterile, never glossy, except corporate property. Science fiction, never fantasy: no elves, no horns, no wizards, no magic. Space, never the sea: always write starship, spaceport, docking bay, hangar — the bare words ship, port and dock make the model draw sailing boats.

ADD NOTHING THE GM DID NOT ASK FOR. No extra starships, stations, drones, holographic displays, screens or props, no invented colour palette, no extra characters. Your job is to render their sentence precisely, filling in only framing, light and material wear.

Never negate in a slot: the words no, without and not must not appear in one. Anything that must be kept out of the frame is handled by the pipeline, not by you.

CLASSIFY THE SHOT. Return shot as interior, landscape, orbital or void per the definitions above. Return no_people true when the frame must contain nobody — the GM described the place as deserted, or it is a structure alone in space.

English only, comma separated tags, no Midjourney flags, no prose, no explanation."""


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
    "IF THE ORIGINAL PROMPT IS UNKNOWN: open with \"gritty sci-fi concept art, "
    "digital painting\" and then write only the subject tags of step 2. No place, "
    "no background, no lighting — you cannot see the picture, and a guessed "
    "setting repaints the region for a different scene than the one around it. "
    "The surrounding pixels already carry the light and the place.\n\n"
    "FLAVOUR of the subject itself: gritty used-future — worn, repaired, greasy, "
    "never sterile, never fantasy. No proper nouns of factions or places, visuals "
    "only. If a word could name a sea vessel or its parts, qualify it with "
    "space- or star- so the model draws spacecraft, not boats.\n\n"
    "NEGATIVE_PROMPT: start from the original negative if given, minus what now "
    "contradicts the request. Add the thing the request replaces — whatever used "
    "to occupy the region, if the request names or implies it. 8-14 tags, no "
    "colour words. Rule B applies to every tag you add.\n\n"
    "Both fields English only, comma-separated tags only, no Midjourney flags, "
    "no prose, no explanation."
)


DEFAULT_BASE_URL = ""

# structured output — хаб (vLLM guided JSON) гарантирует именно эту форму ответа,
# не приходится парсить произвольный текст модели
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

SHOTS = ("person", "object") + SHOTS_PLACE
NEGATION = re.compile(r"\b(no|not|without|lacking)\b", re.I)
# Модель просят писать по-английски, но в слот иногда уезжает русское слово прямо
# из описания ГМа. Рисующая модель кириллицу не понимает, а постановка задачи
# отвергает такой промпт целиком — тег выбрасываем на сборке
CYR_SLOT = re.compile(r"[а-яё]", re.I)
EARTH_RE = re.compile(r"\b(" + "|".join(sorted(EARTH_WORDS, key=len, reverse=True)) + r")\b", re.I)

# Модель не пишет промпт целиком — она заполняет слоты, а собирает строку код.
# Рамка кадра, порядок тегов, синтаксис веса, стилевой блок, словарь регистра и
# длина заданы схемой, а не дисциплиной модели: именно на них приходился почти
# весь брак выхлопа. Негатив собирается кодом по той же причине.
def slots_schema(kind: str, brief: bool = True, kit: dict | None = None) -> dict:
    """Три поля вместо пятнадцати: рисующая модель читает связный текст, и то, что
    прежде резалось на слоты, теперь пишется прозой.

    Порядок полей — порядок рассуждения: сперва субъект, потом место вокруг него.
    Схема нужна ради дисциплины ответа: только английский, только эти поля, без
    предисловий вроде «here is the prompt»."""
    props: dict[str, dict] = {
        "brief_subject": {"type": "string"},
        "brief_scene": {"type": "string"},
        "no_people": {"type": "boolean"},
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


def swap_earth_words(text: str) -> str:
    """Заменить слова нашего века на описание покроя и материала.

    Рисующая модель на «uniform» отвечает мундиром позапрошлого века, на «badge» —
    нашивкой с флагом: эти слова несут с собой земную форму целиком. Замена идёт по
    целым словам и сохраняет регистр первой буквы."""
    def repl(m: re.Match) -> str:
        word = m.group(0)
        swap = EARTH_WORDS[word.lower()]
        return swap[0].upper() + swap[1:] if word[0].isupper() else swap

    return EARTH_RE.sub(repl, text)


def build_prompt(kind: str, register: str, slots: dict, plan: str = "full",
                 style: str = "film", kit: dict | None = None) -> tuple[str, str]:
    """Собрать промпт прозой: закон сеттинга, манера, рамка кадра, текст модели.

    Ни весов, ни якорей, ни тегов регистра: рисующая модель читает предложения
    языковым энкодером, и всё, что было арифметикой прежней сборки, здесь либо
    не действует, либо мешает. Регистр остаётся выбором ГМа, но живёт в инструкции
    для LLM, а не в строке промпта."""
    kit = kit or default_kit()
    manner = (kit.get("styles") or {}).get(style) or next(iter(kit["styles"].values()))
    frames = kit.get("frames") or FRAME_LINES
    frame_key = f"person:{plan}" if kind == "person" else kind
    frame_line = str(frames.get(frame_key, "")).strip()
    parts = [frame_line, str(kit.get("setting_line", "")).strip(),
             str(manner.get("line", "")).strip()]
    for key in ("brief_subject", "brief_scene"):
        text = str(slots.get(key, "")).strip()
        if text and not CYR_SLOT.search(text):
            text = swap_earth_words(text)
            parts.append(text if text.endswith(".") else text + ".")
    # рамка повторяется в хвосте: середина строки — самое слабое место, и ростовой
    # план, названный один раз в начале, приезжал поясным портретом
    if frame_line:
        parts.append(frame_line)
    shot = str(slots.get("shot", "")).strip() if kind == "place" else kind
    return " ".join(p for p in parts if p), shot


def img_settings_out(camp: Campaign) -> dict:
    kit = campaign_kit(camp)
    return {
        # редактору отдаём инструкцию вместе с законом сеттинга: без него в окне
        # читалась голова, в которой ни слова о вселенной и времени действия.
        # План подставлен ростовой — остальные подставляются на запросе
        "meta_prompt": camp.img_meta_prompt or kit_head_block(kit, "person", "full"),
        "object_prompt": camp.img_object_prompt or kit_head_block(kit, "object"),
        "scene_prompt": camp.img_scene_prompt or kit_head_block(kit, "place"),
        "inpaint_prompt": camp.img_inpaint_prompt or DEFAULT_INPAINT_META_PROMPT,
        "base_url": camp.img_base_url,
        "model": camp.img_model,
        "api_key": camp.img_api_key,
    }


class PromptKitIn(BaseModel):
    """Правки ГМа поверх дефолтного кита. Полный кит присылать не нужно: сервер
    хранит только отличия, поэтому обновления кода доезжают до кампании сами."""

    kit: dict


def kit_out(camp: Campaign) -> dict:
    over = {}
    if (camp.img_prompt_kit or "").strip():
        try:
            over = json.loads(camp.img_prompt_kit)
        except ValueError:
            over = {}
    return {"kit": campaign_kit(camp), "defaults": default_kit(), "overrides": over,
            "sections": list(KIT_SECTIONS)}


@router.get("/prompt-kit")
def get_prompt_kit(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Весь набор промптов: что применяется сейчас, что лежит в коде и что ГМ уже
    переопределил. Правится по секциям — головы, планы, регистры, ноты, рамка,
    веса, манеры, негативы."""
    return kit_out(db.get(Campaign, v.campaign_id))


@router.patch("/prompt-kit")
def patch_prompt_kit(
    body: PromptKitIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    unknown = set(body.kit) - set(KIT_SECTIONS)
    if unknown:
        raise HTTPException(400, f"неизвестные секции: {', '.join(sorted(unknown))}")
    camp = db.get(Campaign, v.campaign_id)
    over = {}
    if (camp.img_prompt_kit or "").strip():
        try:
            over = json.loads(camp.img_prompt_kit)
        except ValueError:
            over = {}
    merged = merge_kit(over, body.kit)
    # секция, совпавшая с дефолтом, из переопределений уходит: иначе кампания
    # навсегда застынет на старой версии текста, который правился в коде
    base = default_kit()
    merged = {k: v for k, v in merged.items() if v != base.get(k)}
    camp.img_prompt_kit = json.dumps(merged, ensure_ascii=False) if merged else ""
    db.commit()
    return kit_out(camp)


@router.delete("/prompt-kit")
def reset_prompt_kit(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """Сбросить все правки и вернуться к набору из кода."""
    camp = db.get(Campaign, v.campaign_id)
    camp.img_prompt_kit = ""
    camp.img_meta_prompt = camp.img_object_prompt = camp.img_scene_prompt = ""
    db.commit()
    return kit_out(camp)


@router.get("/image-gen-settings")
def get_image_gen_settings(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    return img_settings_out(db.get(Campaign, v.campaign_id))


class ImgSettingsIn(BaseModel):
    meta_prompt: str | None = None
    object_prompt: str | None = None
    scene_prompt: str | None = None
    inpaint_prompt: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


@router.patch("/image-gen-settings")
def patch_image_gen_settings(
    body: ImgSettingsIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    camp = db.get(Campaign, v.campaign_id)
    if body.meta_prompt is not None:
        camp.img_meta_prompt = body.meta_prompt.strip()
    if body.object_prompt is not None:
        camp.img_object_prompt = body.object_prompt.strip()
    if body.scene_prompt is not None:
        camp.img_scene_prompt = body.scene_prompt.strip()
    if body.inpaint_prompt is not None:
        camp.img_inpaint_prompt = body.inpaint_prompt.strip()
    if body.base_url is not None:
        camp.img_base_url = body.base_url.strip() or DEFAULT_BASE_URL
    if body.model is not None:
        camp.img_model = body.model.strip()
    if body.api_key is not None:
        camp.img_api_key = body.api_key.strip()
    db.commit()
    return img_settings_out(camp)


class PromptDraftIn(BaseModel):
    """Описание ГМа плюс его развилки: кто в кадре, в какой манере, каким планом."""

    text: str
    kind: str = "person"
    register: str = "frontier"
    plan: str = "full"
    style: str = "concept"


def compose_negative(prompt: str, shot: str, no_people: bool, plan: str = "full",
                    kit: dict | None = None, face_open: bool = False,
                    register: str = "") -> str:
    """Негатива больше нет.

    У рисующей модели guidance дистиллирован: вторая ветвь не считается, и всё,
    что мы пишем в негатив, просто не участвует в выводе. Свод из полусотни тегов
    жил ради SDXL и лежит вместе с ней в presets/dreamshaper."""
    return ""


def hub_call(camp: Campaign, system: str, text: str, schema: dict) -> dict:
    """Один поход в LLM-хаб со structured output. Возвращает разобранный ответ."""
    if not camp.img_api_key:
        raise HTTPException(400, "не задан api_key LLM-хаба — заполни в настройках генерации (окно ГМа)")
    body = {
        "model": camp.img_model or "",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        # ниже 0.5 выхлоп заметно стабильнее: половина брака была не ошибкой
        # инструкции, а разбросом от прогона к прогону
        "temperature": 0.3,
        # рассуждающая модель здесь не годится: она съедает тысячи токенов до
        # того, как начнёт отвечать, и возвращает пустой content
        "max_tokens": 900,
        "response_format": schema,
    }
    try:
        r = httpx.post(
            f"{(camp.img_base_url or DEFAULT_BASE_URL).rstrip('/')}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {camp.img_api_key}"},
            timeout=120,
        )
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"LLM-хаб не ответил: {exc}") from exc


def campaign_kit(camp: Campaign) -> dict:
    """Промпт-кит кампании: дефолт из кода плюс то, что ГМ поправил в окне."""
    over = None
    if (camp.img_prompt_kit or "").strip():
        try:
            over = json.loads(camp.img_prompt_kit)
        except ValueError:
            over = None
    return merge_kit(default_kit(), over)


def face_open(kind: str, slots: dict) -> bool:
    """Лицо описано — значит оно в кадре, и свод против шлема применяется.

    Раньше свод отключало любое упоминание шлема в слотах, и снятый шлем, висящий
    у бедра, надевался обратно на голову. Описанное лицо — само по себе признак:
    ГМ, которому нужна закрытая голова, лица не описывает."""
    return kind == "person" and bool(slots.get("face"))


def draft_slots(camp: Campaign, kind: str, register: str, text: str, plan: str = "full",
                style: str = "concept") -> dict:
    """Промпт для рисующей модели: слоты от хаба, сборка и негатив кодом."""
    kit = campaign_kit(camp)
    head = {"person": camp.img_meta_prompt, "object": camp.img_object_prompt,
            "place": camp.img_scene_prompt}.get(kind) or ""
    system = kit_system_prompt(kit, kind, register, plan)
    if head.strip():
        # кампания переопределила инструкцию — словарь регистра и разметку слотов
        # всё равно дописываем: их задают развилки ГМа и схема ответа
        system = system.replace(kit_head_block(kit, kind, plan), head.strip(), 1)
    parsed = hub_call(camp, system, text, slots_schema(kind, kit=kit))
    prompt, shot = build_prompt(kind, register, parsed, plan, style, kit=kit)
    return {
        # слоты отдаём наружу: без них сборку промпта не сравнить с другой сборкой,
        # а именно сборка — то, что мы подбираем
        "slots": parsed,
        "prompt": prompt,
        "negative_prompt": compose_negative(prompt, shot, bool(parsed.get("no_people")), plan,
                                            kit=kit, face_open=face_open(kind, parsed),
                                            register=register),
        "shot": shot,
        "register": register,
        "plan": plan if kind == "person" else None,
        "style": style,
    }


def draft_inpaint_prompt(camp: Campaign, system: str, text: str) -> dict:
    """Правка по маске — единственный случай, где негатив зависит от контекста кадра,
    там его по-прежнему пишет модель."""
    parsed = hub_call(camp, system, text, INPAINT_PROMPT_SCHEMA)
    return {
        "prompt": str(parsed.get("prompt", "")).strip(),
        "negative_prompt": str(parsed.get("negative_prompt", "")).strip(),
    }


@router.post("/image-prompt")
def create_image_prompt(
    body: PromptDraftIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    """Собрать промпт для рисующей модели из свободного описания ГМа через LLM-хаб.
    Писать можно по-русски; тип субъекта и визуальный регистр выбирает ГМ в окне."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "опиши, что нужно сгенерировать")
    if body.kind not in KINDS:
        raise HTTPException(400, f"тип субъекта — одно из: {', '.join(KINDS)}")
    if body.register not in REGISTER_ORDER:
        raise HTTPException(400, f"регистр — один из: {', '.join(REGISTER_ORDER)}")
    if body.plan not in PLAN_ORDER:
        raise HTTPException(400, f"план — один из: {', '.join(PLAN_ORDER)}")
    if body.style not in STYLE_ORDER:
        raise HTTPException(400, f"манера — одна из: {', '.join(STYLE_ORDER)}")
    camp = db.get(Campaign, v.campaign_id)
    return draft_slots(camp, body.kind, body.register, text, body.plan, body.style)


class InpaintPromptIn(BaseModel):
    """Что перепечатать (по-русски можно) плюс промпт, из которого кадр вырос."""

    text: str
    base_prompt: str = ""
    base_negative: str = ""


def source_prompt(db: Session, campaign_id: str, a: Attachment) -> tuple[str, str]:
    """Промпт, которым нарисован исходник: заявка после выбора не удаляется, а
    правка области без исходного промпта вырождается в перерисовку всего кадра.

    У кадра кампании вложение указывает на заявку напрямую, у портрета — на карточку,
    поэтому там берём последнюю завершённую заявку этой карточки.
    """
    job = None
    if a.target_type == SCENE_FRAME and a.target_id:
        job = db.get(ImageGenJob, a.target_id)
    elif a.target_type == "entity" and a.target_id:
        job = (
            db.query(ImageGenJob)
            .filter(ImageGenJob.campaign_id == campaign_id,
                    ImageGenJob.entity_id == a.target_id, ImageGenJob.prompt != "")
            .order_by(ImageGenJob.created_at.desc())
            .first()
        )
    if not job or job.campaign_id != campaign_id:
        return "", ""
    return job.prompt or "", job.negative_prompt or ""


@router.get("/inpaint-base/{attachment_id}")
def get_inpaint_base(
    attachment_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Чем рисовали исходник — окно правки показывает это и даёт поправить руками."""
    src = inpaint_source(db, v, attachment_id)
    prompt, negative = source_prompt(db, v.campaign_id, src)
    return {"prompt": prompt, "negative_prompt": negative, "caption": src.caption}


@router.post("/inpaint-prompt")
def create_inpaint_prompt(
    body: InpaintPromptIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Промпт для правки области: хабу нужен и исходный промпт кадра, и просьба ГМа —
    инпеинт кондишенит весь холст, поэтому на выходе полный промпт, а не фрагмент."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "опиши, что должно оказаться в закрашенной области")
    camp = db.get(Campaign, v.campaign_id)
    said = "\n".join([
        f"ORIGINAL PROMPT: {body.base_prompt.strip() or '(unknown)'}",
        f"ORIGINAL NEGATIVE: {body.base_negative.strip() or '(none)'}",
        f"MASKED AREA REQUEST: {text}",
    ])
    return draft_inpaint_prompt(camp, camp.img_inpaint_prompt or DEFAULT_INPAINT_META_PROMPT, said)


@router.post("/scene-prompt")
def create_scene_prompt(
    body: PromptDraftIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Живая надиктовка локации: тип субъекта фиксирован, регистр по-прежнему за ГМом."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "опиши локацию — голосом или текстом")
    if body.register not in REGISTER_ORDER:
        raise HTTPException(400, f"регистр — один из: {', '.join(REGISTER_ORDER)}")
    camp = db.get(Campaign, v.campaign_id)
    return draft_slots(camp, "place", body.register, text)


def job_out(job: ImageGenJob, db: Session) -> dict:
    candidates = []
    if job.status == "ready":
        rows = (
            db.query(Attachment)
            .filter(Attachment.campaign_id == job.campaign_id, Attachment.target_id == job.id,
                    Attachment.target_type.in_((CANDIDATE, SCENE_FRAME)))
            .order_by(Attachment.created_at)
            .all()
        )
        candidates = [
            {"id": a.id, "url": f"/api/campaigns/{job.campaign_id}/files/{a.id}"} for a in rows
        ]
    src = job.source_attachment_id
    return {
        "id": job.id,
        "entity_id": job.entity_id,
        "kind": job.kind or "txt2img",
        "prompt": job.prompt,
        "negative_prompt": job.negative_prompt,
        "width": job.width,
        "height": job.height,
        "n_images": job.n_images,
        "denoise": job.denoise,
        "status": job.status,
        "error": job.error,
        "candidates": candidates,
        "source_url": f"/api/campaigns/{job.campaign_id}/files/{src}" if src else None,
        "created_at": job.created_at,
    }


def reap_stale_jobs(db: Session) -> None:
    """Вернуть в очередь заявки, которые держит мёртвый воркер.

    Живой воркер пингует каждые 10 с и называет заявку, над которой сидит. Пинг
    пропал — рисовать некому, заявка потеряна. Пинг есть, но про другую заявку —
    сигнал слабее (воркеров может быть запущено несколько), и такую ждём дольше.

    Первый заход возвращаем в pending: чаще всего воркер просто перезапустили, и он
    дорисует сам. Второй — гасим в failed, чтобы не гонять по кругу сбоящую задачу.
    """
    rows = db.query(ImageGenJob).filter(ImageGenJob.status == "claimed").all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    fresh = bool(_worker_beat) and time.time() - _worker_beat["ts"] <= HEARTBEAT_TTL
    live = (_worker_beat.get("job") or {}).get("id") if fresh else None
    changed = False
    for job in rows:
        claimed = job.claimed_at
        if claimed and claimed.tzinfo is None:
            claimed = claimed.replace(tzinfo=timezone.utc)
        # заявка из времён до этой колонки: возраста нет, считаем потерянной
        age = (now - claimed).total_seconds() if claimed else CLAIM_MAX + 1
        if age <= CLAIM_GRACE:
            continue
        # воркер жив и держит именно эту заявку — не трогаем до самого потолка
        if age < CLAIM_MAX and (live == job.id or (fresh and age < CLAIM_IDLE)):
            continue
        if job.attempts >= MAX_ATTEMPTS:
            job.status, job.error = "failed", LOST_FINAL
        else:
            job.status, job.error = "pending", LOST_ERROR
        job.claimed_at = None
        changed = True
    if changed:
        db.commit()


def get_own_job(db: Session, campaign_id: str, job_id: str) -> ImageGenJob:
    job = db.get(ImageGenJob, job_id)
    if not job or job.campaign_id != campaign_id:
        raise HTTPException(404, "not found")
    return job


# --- GM-facing: создать заявку, следить, выбрать -------------------------------


class JobIn(BaseModel):
    prompt: str
    negative_prompt: str = ""
    # сид по заявке: ноль — случайный, как и было
    seed: int = 0
    # нативный SDXL-бакет ~1 Мп: вне бакетов модель дублирует объекты и рвёт анатомию
    width: int = 896
    height: int = 1152


MIN_SIDE, MAX_SIDE = 256, 1536
# CLIP-энкодер не понимает кириллицу — промпт должен быть на английском
CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")


def tag_words(text: str) -> list[str]:
    low = text.lower()
    for ch in "(),.:":
        low = low.replace(ch, " ")
    # веса словами не считаем: (arm:1.3) и (arm:1.2) — один и тот же тег
    return [w for w in low.split() if not w.replace(".", "").isdigit()]


def drop_self_negation(prompt: str, negative: str) -> str:
    """Выкинуть из негатива то, что просят нарисовать в позитиве.

    Хаб регулярно кладёт заказанное и в негатив («протез» в обоих полях): модель тогда
    обходит область стороной и заполняет её тем, что вокруг. Ловим здесь, а не только в
    воркере, — тот живёт на машине ГМа и обновляется отдельно.
    """
    words = set(tag_words(prompt))
    keep = []
    for tag in negative.split(","):
        t = tag.strip()
        if not t:
            continue
        parts = tag_words(t)
        if parts and all(w in words for w in parts):
            continue
        keep.append(t)
    return ", ".join(keep)


def check_prompt(prompt: str, negative: str) -> tuple[str, str]:
    prompt, negative = prompt.strip(), negative.strip()
    if not prompt:
        raise HTTPException(400, "prompt required")
    if CYRILLIC.search(prompt) or CYRILLIC.search(negative):
        raise HTTPException(400, "промпт должен быть на английском — модель не понимает кириллицу")
    return prompt, drop_self_negation(prompt, negative)


def build_job(v: Viewer, body: JobIn, entity_id: str | None, n_images: int) -> ImageGenJob:
    prompt, negative = check_prompt(body.prompt, body.negative_prompt)
    return ImageGenJob(
        campaign_id=v.campaign_id, entity_id=entity_id, prompt=prompt[:2000],
        negative_prompt=negative[:1000],
        width=max(MIN_SIDE, min(MAX_SIDE, body.width)),
        height=max(MIN_SIDE, min(MAX_SIDE, body.height)),
        n_images=n_images, created_by=v.member_id,
        seed=max(0, min(2**31 - 1, body.seed or 0)),
    )


@router.post("/entities/{entity_id}/image-jobs")
def create_image_job(
    entity_id: str, body: JobIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    get_visible_entity(db, v, entity_id)
    existing = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.entity_id == entity_id,
                ImageGenJob.kind == "txt2img", ImageGenJob.status.in_(ACTIVE_STATUSES))
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    if existing:
        if existing.status == "pending":
            # воркер её ещё не взял — новая заявка важнее: тихо вернуть старую
            # значило бы молча выбросить правки промпта, которые ГМ только что сделал
            db.delete(existing)
            db.flush()
        else:
            # уже рисуется или готова — отдаём её же, новую не плодим
            return job_out(existing, db)
    job = build_job(v, body, entity_id=entity_id, n_images=CANDIDATES_PER_JOB)
    db.add(job)
    db.flush()
    db.commit()
    return job_out(job, db)


@router.get("/entities/{entity_id}/image-jobs/active")
def get_active_entity_job(
    entity_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    job = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.entity_id == entity_id,
                ImageGenJob.kind == "txt2img", ImageGenJob.status.in_(ACTIVE_STATUSES))
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    return {"job": job_out(job, db) if job else None}


@router.get("/image-jobs/active")
def list_active_jobs(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    rows = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.status.in_(ACTIVE_STATUSES))
        .all()
    )
    return [{"id": j.id, "entity_id": j.entity_id, "status": j.status} for j in rows]


@router.get("/image-worker/status")
def image_worker_status(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    # воркер может быть выключен совсем — тогда его поллинг висяки не разгребёт,
    # а плашку статуса интерфейс дёргает и без него
    reap_stale_jobs(db)
    beat = _worker_beat
    age = time.time() - beat["ts"] if beat else None
    if age is None or age > HEARTBEAT_TTL:
        state = "offline"
    elif beat.get("comfy") == "up":
        state = "online"
    else:
        state = "degraded"

    rows = (
        db.query(ImageGenJob.status)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.status.in_(ACTIVE_STATUSES))
        .all()
    )
    queue = {s: 0 for s in ACTIVE_STATUSES}
    for (status,) in rows:
        queue[status] = queue.get(status, 0) + 1

    last_failed = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.status == "failed")
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    return {
        "state": state,
        "age_s": round(age, 1) if age is not None else None,
        "comfy": beat.get("comfy") if beat else None,
        "checkpoint": beat.get("checkpoint") if beat else None,
        "inpaint_checkpoint": beat.get("inpaint_checkpoint") if beat else None,
        "job": beat.get("job") if state != "offline" else None,
        "queue": queue,
        "last_error": last_failed.error if last_failed else None,
    }


# --- кадры кампании: заявка без карточки, одна картинка, сразу в галерее -------

SCENE_HISTORY = 24


@router.post("/scene-jobs")
def create_scene_job(body: JobIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Кадр кампании: к сущности не привязан, рисуется в одном экземпляре и
    остаётся в галерее раздела «Кадры кампании». Кадры рисует весь стол, не только ГМ."""
    job = build_job(v, body, entity_id=None, n_images=1)
    db.add(job)
    db.flush()
    db.commit()
    return job_out(job, db)


def own_scene_job(db: Session, v: Viewer, job_id: str) -> ImageGenJob:
    """Своя заявка на кадр: черновик до сохранения принадлежит тому, кто его завёл.
    Правка кадра по маске к карточке тоже не привязана — её отсекаем по kind, иначе
    экран генерации подхватит её как свой недорисованный кадр."""
    job = db.get(ImageGenJob, job_id)
    if (not job or job.campaign_id != v.campaign_id or job.entity_id is not None
            or (job.kind or "txt2img") != "txt2img" or job.created_by != v.member_id):
        raise HTTPException(404, "not found")
    return job


@router.get("/scene-jobs")
def list_scene_jobs(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Свои незакрытые заявки: экран генерации подхватывает их после перезагрузки —
    и ту, что ещё рисуется, и ту, что ждёт решения «сохранить или сбросить»."""
    rows = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id,
                ImageGenJob.entity_id.is_(None),
                ImageGenJob.kind == "txt2img",
                ImageGenJob.created_by == v.member_id,
                ImageGenJob.status.in_(ACTIVE_STATUSES))
        .order_by(ImageGenJob.created_at.desc())
        .limit(SCENE_HISTORY)
        .all()
    )
    return [job_out(j, db) for j in rows]


@router.get("/scene-jobs/{job_id}")
def get_scene_job(job_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    return job_out(own_scene_job(db, v, job_id), db)


class KeepIn(BaseModel):
    caption: str = ""


@router.post("/scene-jobs/{job_id}/keep")
def keep_scene_frame(
    job_id: str, body: KeepIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Сохранить нарисованный кадр в коллекцию: черновик открывается столу и получает
    подпись, заявка на этом закрыта."""
    job = own_scene_job(db, v, job_id)
    if job.status != "ready":
        raise HTTPException(409, "кадр ещё не готов")
    frame = (
        db.query(Attachment)
        .filter_by(campaign_id=v.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .first()
    )
    if not frame:
        raise HTTPException(404, "кадра нет")
    frame.target_type = SCENE_FRAME
    frame.visibility = "crew"
    frame.visible_to = []
    frame.caption = body.caption.strip()[:300]
    job.status = "done"
    journal.log(db, v, "file", "upload", target_id=frame.id,
                title=frame.caption or "кадр кампании", detail=frame.mime,
                visibility=frame.visibility)
    db.commit()
    return frame_out(frame, v, {job.id: job})


@router.delete("/scene-jobs/{job_id}")
def cancel_scene_job(job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    job = own_scene_job(db, v, job_id)
    rows = (
        db.query(Attachment)
        .filter(Attachment.campaign_id == v.campaign_id, Attachment.target_id == job.id,
                Attachment.target_type.in_((CANDIDATE, SCENE_FRAME)))
        .all()
    )
    for a in rows:
        drop_files(a)
        db.delete(a)
    db.delete(job)
    db.commit()
    return {"ok": True}


# --- галерея кадров: то же вложение, но с подписью и своей видимостью ---------


def frame_out(a: Attachment, v: Viewer, jobs: dict[str, ImageGenJob]) -> dict:
    job = jobs.get(a.target_id or "")
    data = {
        "id": a.id,
        "url": f"/api/campaigns/{a.campaign_id}/files/{a.id}",
        "caption": a.caption,
        "width": job.width if job else 0,
        "height": job.height if job else 0,
        # свой кадр игрок подписывает и убирает сам, чужой не трогает
        "mine": bool(a.uploaded_by) and a.uploaded_by == v.member_id,
        "created_at": a.created_at,
    }
    if v.is_gm:
        data["visibility"] = a.visibility
        data["prompt"] = job.prompt if job else ""
    return data


@router.get("/scene-frames")
def list_scene_frames(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Галерея кадров. Игрок видит только открытое столу, порядок — свежие сверху."""
    q = db.query(Attachment).filter(
        Attachment.campaign_id == v.campaign_id, Attachment.target_type == SCENE_FRAME
    )
    rows = apply_scope(q, Attachment, v).order_by(Attachment.created_at.desc()).all()
    ids = [a.target_id for a in rows if a.target_id]
    jobs = (
        {j.id: j for j in db.query(ImageGenJob).filter(ImageGenJob.id.in_(ids)).all()}
        if ids else {}
    )
    return [frame_out(a, v, jobs) for a in rows]


def get_frame(db: Session, v: Viewer, frame_id: str) -> Attachment:
    a = db.get(Attachment, frame_id)
    if (not a or a.campaign_id != v.campaign_id or a.target_type != SCENE_FRAME
            or not can_see(a, v)):
        raise HTTPException(404, "not found")
    return a


def own_frame(db: Session, v: Viewer, frame_id: str) -> Attachment:
    """Правит и убирает кадр ГМ или тот, кто его завёл."""
    a = get_frame(db, v, frame_id)
    if not v.is_gm and a.uploaded_by != v.member_id:
        raise HTTPException(403, "чужой кадр — правит его автор или ГМ")
    return a


class FrameIn(BaseModel):
    caption: str | None = None
    # у кадра нет владельца и адресата: он либо на столе, либо у ГМа
    visibility: str | None = None


@router.patch("/scene-frames/{frame_id}")
def patch_scene_frame(
    frame_id: str, body: FrameIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    a = own_frame(db, v, frame_id)
    if body.visibility is not None:
        # что стол видит — решает только ГМ
        if not v.is_gm:
            raise HTTPException(403, "видимость кадра держит ГМ")
        if body.visibility not in ("crew", "gm"):
            raise HTTPException(422, "bad visibility")
        a.visibility = body.visibility
    if body.caption is not None:
        a.caption = body.caption.strip()[:300]
    journal.log(db, v, "file", "update", target_id=a.id, title=a.caption or "кадр кампании",
                detail=a.mime, visibility=a.visibility)
    db.commit()
    jobs = {}
    if a.target_id:
        job = db.get(ImageGenJob, a.target_id)
        if job:
            jobs[job.id] = job
    return frame_out(a, v, jobs)


@router.delete("/scene-frames/{frame_id}")
def delete_scene_frame(
    frame_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    a = own_frame(db, v, frame_id)
    job = db.get(ImageGenJob, a.target_id) if a.target_id else None
    journal.log(db, v, "file", "delete", target_id=a.id, title=a.caption or "кадр кампании",
                detail=a.mime, visibility=a.visibility)
    drop_files(a)
    db.delete(a)
    if job and job.campaign_id == v.campaign_id and job.entity_id is None:
        db.delete(job)
    db.commit()
    return {"ok": True}


# --- инпеинт: перерисовать область сохранённой картинки по маске ---------------

# ниже этого максимума маска считается пустой — кисть не коснулась холста
MASK_MIN_WHITE = 16
# радиус размытия кромки маски: доля меньшей стороны кадра
FEATHER_DIVISOR = 170
# запас окружения вокруг закрашенного, долями его размера с каждой стороны
CROP_PAD = 0.55
# к этой стороне тянем вырезанный кусок: рабочее разрешение SDXL
INPAINT_TARGET = 1024
INPAINT_BUSY = ("pending", "claimed")


def inpaint_source(db: Session, v: Viewer, attachment_id: str) -> Attachment:
    """Что можно перерисовать: сохранённый портрет карточки или кадр кампании.
    Кандидаты генерации сюда не попадают — сперва выбор, потом правка."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, "not found")
    if not a.mime.startswith("image/") or a.mime == "image/svg+xml":
        raise HTTPException(415, "перерисовать можно только растровую картинку")
    if a.target_type == SCENE_FRAME:
        if not v.is_gm and a.uploaded_by != v.member_id:
            raise HTTPException(403, "чужой кадр — правит его автор или ГМ")
    elif a.target_type == "entity":
        if not v.is_gm:
            raise HTTPException(403, "портрет карточки перерисовывает ГМ")
    else:
        raise HTTPException(409, "перерисовать можно портрет карточки или кадр кампании")
    return a


def crop_window(mask: Image.Image, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Кусок кадра вокруг закрашенного, который уйдёт в модель.

    Инпеинт по всему холсту — главная причина «просил дрона, получил кусок корабля»:
    закрашенная область занимает пару процентов кадра, в латенте от неё остаются
    считаные клетки, а промпт при этом описывает весь кадр — модель и дорисовывает
    то, что вокруг. Кусок вокруг маски даёт области полное разрешение модели.

    Пусто — маска и так во весь кадр, резать нечего.
    """
    bbox = mask.point(lambda p: 255 if p >= MASK_MIN_WHITE else 0).getbbox()
    if not bbox:
        return None
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # запас вокруг маски: без окружения модель не знает, во что вписывать объект
    side = max(bw, bh) * (1 + 2 * CROP_PAD)
    side = int(min(max(side, MIN_SIDE), w, h))
    side -= side % 8
    if side >= min(w, h) * 0.9:
        return None
    cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
    x = max(0, min(w - side, cx - side // 2))
    y = max(0, min(h - side, cy - side // 2))
    return x - x % 8, y - y % 8, side, side


def prepare_inpaint_pair(
    src: Attachment, mask_raw: bytes
) -> tuple[bytes, bytes, int, int, str]:
    """Свести исходник и маску к одному размеру, кратному 8, размыть кромку маски и
    вырезать рабочий кусок вокруг закрашенного.

    Кратность 8 — требование латента: иначе декодированный кадр разъезжается с
    оригиналом на пару пикселей и композит по маске оставляет полосу по краю.
    Жёсткая кромка кисти даёт видимый шов, поэтому маску размываем.

    Возвращает пару для воркера, размер подготовленного кадра целиком и вырезанное
    окно "x,y,w,h" — по нему кандидаты вклеиваются обратно (см. stitch_candidate).
    """
    path = os.path.join(settings.upload_dir, src.campaign_id, src.url)
    if not os.path.exists(path):
        raise HTTPException(410, "исходник пропал с диска")
    try:
        with Image.open(path) as im:
            full = im.convert("RGB")
            full_size = (full.width, full.height)
            box = (0, 0, full.width - full.width % 8, full.height - full.height % 8)
            full = full.crop(box)
            w, h = full.size
            if w < MIN_SIDE or h < MIN_SIDE:
                raise HTTPException(422, "картинка слишком мелкая для перерисовки")
        with Image.open(io.BytesIO(mask_raw)) as mi:
            mask = mi.convert("L")
            # маску рисуют поверх картинки во всю величину, поэтому и обрезаем её
            # так же, как исходник, а не масштабируем в кадр — иначе сдвиг до 7 px
            if mask.size != full_size:
                mask = mask.resize(full_size, Image.LANCZOS)
            mask = mask.crop(box)
            if mask.getextrema()[1] < MASK_MIN_WHITE:
                raise HTTPException(400, "область не закрашена — отметь кистью, что перерисовать")

        window = crop_window(mask, w, h)
        crop = ""
        if window:
            x, y, cw, ch = window
            full = full.crop((x, y, x + cw, y + ch))
            mask = mask.crop((x, y, x + cw, y + ch))
            crop = f"{x},{y},{cw},{ch}"
            # мелкий кусок тянем к рабочему разрешению SDXL: на 300 px модель рисует
            # кашу, вклеиваем всё равно с уменьшением обратно
            if max(full.size) != INPAINT_TARGET:
                side = INPAINT_TARGET - INPAINT_TARGET % 8
                full = full.resize((side, side), Image.LANCZOS)
                mask = mask.resize((side, side), Image.LANCZOS)

        mask = mask.filter(
            ImageFilter.GaussianBlur(max(3, min(mask.size) // FEATHER_DIVISOR)))
        src_buf, mask_buf = io.BytesIO(), io.BytesIO()
        full.save(src_buf, "PNG")
        mask.save(mask_buf, "PNG")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — битый файл или незнакомый формат
        raise HTTPException(422, f"не удалось прочитать картинку или маску: {exc}") from exc
    return src_buf.getvalue(), mask_buf.getvalue(), w, h, crop


def stitch_candidate(db: Session, job: ImageGenJob, data: bytes) -> bytes:
    """Вклеить перерисованный кусок обратно в целый кадр.

    Воркер видел только окно вокруг маски — кандидат приходит куском. Возвращаем его
    на место по маске заявки: вне маски остаются исходные пиксели, поэтому кадр не
    уезжает по цвету от прогона через VAE.
    """
    src = db.get(Attachment, job.source_attachment_id) if job.source_attachment_id else None
    mask_row = (
        db.query(Attachment).filter_by(target_type=MASK, target_id=job.id).first()
    )
    if not src or not mask_row:
        return data
    src_path = os.path.join(settings.upload_dir, src.campaign_id, src.url)
    mask_path = os.path.join(settings.upload_dir, mask_row.campaign_id, mask_row.url)
    if not os.path.exists(src_path) or not os.path.exists(mask_path):
        return data
    try:
        x, y, cw, ch = (int(n) for n in job.crop_box.split(","))
        with Image.open(src_path) as im:
            full = im.convert("RGB").crop((0, 0, job.width, job.height))
        with Image.open(io.BytesIO(data)) as ci:
            piece = ci.convert("RGB").resize((cw, ch), Image.LANCZOS)
        with Image.open(mask_path) as mi:
            mask = mi.convert("L").resize((cw, ch), Image.LANCZOS)
        full.paste(piece, (x, y), mask)
        out = io.BytesIO()
        full.save(out, "PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 — кусок не вклеился, отдаём как пришло
        return data


def store_job_blob(job: ImageGenJob, data: bytes, target_type: str, name: str) -> Attachment:
    folder = os.path.join(settings.upload_dir, job.campaign_id)
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4()}.png"
    with open(os.path.join(folder, stored), "wb") as fh:
        fh.write(data)
    return Attachment(
        campaign_id=job.campaign_id, filename=name, url=stored, mime="image/png",
        size=len(data), target_type=target_type, target_id=job.id,
        visibility="gm", uploaded_by=job.created_by,
    )


def own_inpaint_job(db: Session, v: Viewer, job_id: str) -> ImageGenJob:
    job = db.get(ImageGenJob, job_id)
    if (not job or job.campaign_id != v.campaign_id or job.kind != "inpaint"
            or (not v.is_gm and job.created_by != v.member_id)):
        raise HTTPException(404, "not found")
    return job


@router.post("/inpaint-jobs")
async def create_inpaint_job(
    source_attachment_id: str = Form(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(default=""),
    denoise: float = Form(default=1.0),
    mask: UploadFile = File(...),
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Заявка на правку области: маска приходит картинкой (белое — перерисовать),
    размер кадра берём у исходника, а не у ГМа."""
    src = inpaint_source(db, v, source_attachment_id)
    if mask.content_type not in ALLOWED:
        raise HTTPException(415, f"маска пришла как {mask.content_type}")
    raw = await mask.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "маска слишком тяжёлая")
    prompt, negative = check_prompt(prompt, negative_prompt)
    # висяк от умершего воркера иначе навсегда закрывает эту картинку для правки
    reap_stale_jobs(db)
    busy = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.kind == "inpaint",
                ImageGenJob.source_attachment_id == src.id,
                ImageGenJob.status.in_(INPAINT_BUSY))
        .first()
    )
    if busy:
        raise HTTPException(409, "правка этой картинки уже рисуется — дождись или отмени её")
    # сорвавшуюся правку ГМ обычно не отменяет, а закрывает окно: её маска и копия
    # исходника иначе остались бы на диске навсегда
    for stale in (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.kind == "inpaint",
                ImageGenJob.source_attachment_id == src.id, ImageGenJob.status == "failed")
        .all()
    ):
        drop_job_attachments(db, stale, (CANDIDATE, *JOB_TEMP))
        db.delete(stale)
    strength = max(0.2, min(1.0, denoise))
    src_png, mask_png, width, height, crop = prepare_inpaint_pair(src, raw)
    job = ImageGenJob(
        campaign_id=v.campaign_id, kind="inpaint",
        # правка портрета остаётся при карточке: так её видно в аудите и уборке
        entity_id=src.target_id if src.target_type == "entity" else None,
        source_attachment_id=src.id, prompt=prompt[:2000], negative_prompt=negative[:1000],
        # размер держим полный: кандидат вклеивается обратно в целый кадр, а окно
        # правки и галерея показывают пропорции исходника, а не куска
        width=width, height=height, crop_box=crop, n_images=CANDIDATES_PER_JOB,
        denoise=strength, created_by=v.member_id,
    )
    db.add(job)
    db.flush()
    db.add(store_job_blob(job, src_png, SOURCE, "source.png"))
    db.add(store_job_blob(job, mask_png, MASK, "mask.png"))
    db.commit()
    return job_out(job, db)


@router.get("/inpaint-jobs/active")
def get_active_inpaint_job(
    source_attachment_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Незакрытая правка этой картинки. Окно правки спрашивает её при открытии: заявка
    переживает закрытие модалки, и без такого подхвата ГМ упирался в «уже рисуется» без
    единого способа посмотреть или отменить её."""
    reap_stale_jobs(db)
    job = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.kind == "inpaint",
                ImageGenJob.source_attachment_id == source_attachment_id,
                ImageGenJob.status.in_(ACTIVE_STATUSES))
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    if job and not v.is_gm and job.created_by != v.member_id:
        job = None
    return {"job": job_out(job, db) if job else None}


@router.get("/inpaint-jobs/{job_id}")
def get_inpaint_job(job_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    reap_stale_jobs(db)
    return job_out(own_inpaint_job(db, v, job_id), db)


def drop_job_attachments(db: Session, job: ImageGenJob, types: tuple[str, ...]) -> None:
    rows = (
        db.query(Attachment)
        .filter(Attachment.campaign_id == job.campaign_id, Attachment.target_id == job.id,
                Attachment.target_type.in_(types))
        .all()
    )
    for a in rows:
        drop_files(a)
        db.delete(a)


class InpaintPickIn(BaseModel):
    candidate_id: str
    # исходник по умолчанию уходит: раунды правок иначе засыпают медиа копиями
    keep_source: bool = False


@router.post("/inpaint-jobs/{job_id}/pick")
def pick_inpaint_job(
    job_id: str, body: InpaintPickIn, v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Выбранная правка занимает место исходника: тот же адресат, та же видимость,
    та же подпись. Портрет карточки переезжает на неё, если смотрел на исходник."""
    job = own_inpaint_job(db, v, job_id)
    if job.status != "ready":
        raise HTTPException(409, "правка ещё не готова")
    src = db.get(Attachment, job.source_attachment_id) if job.source_attachment_id else None
    if not src or src.campaign_id != job.campaign_id:
        raise HTTPException(409, "исходник удалён — правку некуда положить")
    rows = (
        db.query(Attachment)
        .filter_by(campaign_id=job.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .all()
    )
    winner = next((a for a in rows if a.id == body.candidate_id), None)
    if not winner:
        raise HTTPException(404, "candidate not found")

    old_url = f"/api/campaigns/{job.campaign_id}/files/{src.id}"
    new_url = f"/api/campaigns/{job.campaign_id}/files/{winner.id}"
    winner.caption = src.caption
    winner.visibility = src.visibility
    winner.visible_to = list(src.visible_to or [])
    if src.target_type == SCENE_FRAME:
        # кадру нужна заявка рядом: из неё галерея берёт размер и промпт
        winner.target_type = SCENE_FRAME
        winner.target_id = job.id
    else:
        winner.target_type = "entity"
        winner.target_id = src.target_id
        ent = db.get(Entity, src.target_id) if src.target_id else None
        if ent and ent.campaign_id == job.campaign_id and ent.image_url == old_url:
            ent.image_url = new_url

    for a in rows:
        if a.id != winner.id:
            drop_files(a)
            db.delete(a)
    drop_job_attachments(db, job, JOB_TEMP)
    if not body.keep_source:
        drop_files(src)
        db.delete(src)
    job.status = "done"
    journal.log(db, v, "file", "update", target_id=winner.id,
                title=winner.caption or "правка картинки",
                entity_id=winner.target_id if winner.target_type == "entity" else None,
                detail=winner.mime, visibility=winner.visibility)
    db.commit()
    return {"ok": True, "url": new_url, "frame_id": winner.id}


@router.delete("/inpaint-jobs/{job_id}")
def cancel_inpaint_job(
    job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    job = own_inpaint_job(db, v, job_id)
    drop_job_attachments(db, job, (CANDIDATE, *JOB_TEMP))
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/image-jobs/{job_id}")
def get_image_job(job_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    job = get_own_job(db, v.campaign_id, job_id)
    return job_out(job, db)


class PickIn(BaseModel):
    candidate_id: str
    # выбранный кадр всегда остаётся вложением карточки; портретом он становится,
    # только если этого попросили — иначе просто пополняет медиа
    set_avatar: bool = True


@router.post("/image-jobs/{job_id}/pick")
def pick_image_job(
    job_id: str, body: PickIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)
):
    job = get_own_job(db, v.campaign_id, job_id)
    if job.status != "ready":
        raise HTTPException(409, "job is not ready")
    entity = get_visible_entity(db, v, job.entity_id)
    rows = (
        db.query(Attachment)
        .filter_by(campaign_id=v.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .all()
    )
    winner = next((a for a in rows if a.id == body.candidate_id), None)
    if not winner:
        raise HTTPException(404, "candidate not found")
    winner.target_type = "entity"
    winner.target_id = entity.id
    winner.visibility = "crew"
    url = f"/api/campaigns/{v.campaign_id}/files/{winner.id}"
    if body.set_avatar:
        entity.image_url = url
    for a in rows:
        if a.id != winner.id:
            drop_files(a)
            db.delete(a)
    job.status = "done"
    db.commit()
    return {"ok": True, "image_url": entity.image_url, "attachment_url": url}


@router.delete("/image-jobs/{job_id}")
def cancel_image_job(job_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    job = get_own_job(db, v.campaign_id, job_id)
    rows = (
        db.query(Attachment)
        .filter(Attachment.campaign_id == v.campaign_id, Attachment.target_id == job.id,
                Attachment.target_type.in_((CANDIDATE, SCENE_FRAME)))
        .all()
    )
    for a in rows:
        drop_files(a)
        db.delete(a)
    db.delete(job)
    db.commit()
    return {"ok": True}


# --- воркер: забрать задачу, принести кандидатов, сообщить об ошибке ----------


def worker_auth(authorization: str | None = Header(default=None)) -> None:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not settings.worker_token or token != settings.worker_token:
        raise HTTPException(401, "invalid worker token")


class HeartbeatIn(BaseModel):
    comfy: str = "unknown"
    checkpoint: str | None = None
    # чем воркер правит область: без отдельного inpaint-чекпоинта правка идёт базой
    # и мылит стык — ГМ должен видеть это в плашке, а не гадать
    inpaint_checkpoint: str | None = None
    job_id: str | None = None
    progress: str | None = None


@worker_router.post("/heartbeat")
def worker_heartbeat(body: HeartbeatIn, _: None = Depends(worker_auth)):
    # храним только снимок; свежесть считается на чтении, поэтому писателя
    # срока годности нет и рестарт бэкенда лечится первым же пингом
    _worker_beat.clear()
    _worker_beat.update({
        "ts": time.time(),
        "comfy": body.comfy,
        "checkpoint": body.checkpoint,
        "inpaint_checkpoint": body.inpaint_checkpoint,
        "job": {"id": body.job_id, "progress": body.progress} if body.job_id else None,
    })
    return {"ok": True}


@worker_router.get("/image-jobs/next")
def next_image_job(
    caps: str = "", _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """caps — что воркер умеет, через запятую. Воркер без inpaint не должен получить
    заявку на правку: он нарисует по её промпту обычную картинку и молча подменит кадр."""
    # поллинг воркера — самый частый тик в системе: на нём и подбираем висяки
    reap_stale_jobs(db)
    can = {c.strip() for c in caps.split(",") if c.strip()}
    q = db.query(ImageGenJob).filter_by(status="pending")
    if "inpaint" not in can:
        q = q.filter(ImageGenJob.kind == "txt2img")
    job = q.order_by(ImageGenJob.created_at).first()
    if not job:
        return {"job": None}
    job.status = "claimed"
    job.claimed_at = datetime.now(timezone.utc)
    job.attempts = (job.attempts or 0) + 1
    db.commit()
    return {"job": {
        "id": job.id, "campaign_id": job.campaign_id, "kind": job.kind or "txt2img",
        "prompt": job.prompt, "negative_prompt": job.negative_prompt,
        "width": job.width, "height": job.height,
        "n_images": job.n_images or CANDIDATES_PER_JOB, "denoise": job.denoise,
        "seed": job.seed or 0,
    }}


def job_blob(db: Session, job_id: str, target_type: str) -> FileResponse:
    a = (
        db.query(Attachment)
        .filter_by(target_type=target_type, target_id=job_id)
        .first()
    )
    if not a:
        raise HTTPException(404, f"{target_type} not found")
    path = os.path.join(settings.upload_dir, a.campaign_id, a.url)
    if not os.path.exists(path):
        raise HTTPException(410, "file missing on disk")
    return FileResponse(path, media_type=a.mime, filename=a.filename)


@worker_router.get("/image-jobs/{job_id}/source")
def worker_job_source(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """Подготовленная копия исходника: размер кратен 8 и совпадает с маской."""
    return job_blob(db, job_id, SOURCE)


@worker_router.get("/image-jobs/{job_id}/mask")
def worker_job_mask(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    return job_blob(db, job_id, MASK)


@worker_router.get("/image-jobs/{job_id}/state")
def worker_job_state(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """Жива ли заявка: ГМ мог отменить её посреди пачки — воркер сверяется между
    кандидатами и не жжёт GPU на уже выброшенную работу."""
    job = db.get(ImageGenJob, job_id)
    return {"status": job.status if job else "gone"}


@worker_router.post("/image-jobs/{job_id}/candidates")
async def upload_candidates(
    job_id: str,
    files: list[UploadFile] = File(...),
    _: None = Depends(worker_auth),
    db: Session = Depends(get_db),
):
    job = db.get(ImageGenJob, job_id)
    if not job or job.status != "claimed":
        raise HTTPException(404, "job not found or not claimed")
    if not files:
        raise HTTPException(400, "no files")
    folder = os.path.join(settings.upload_dir, job.campaign_id)
    os.makedirs(folder, exist_ok=True)
    # заявка без карточки — кадр кампании: он ждёт решения автора и виден только ему
    # (и ГМу), в галерею попадает по «сохранить»
    scene = job.entity_id is None
    for f in files[:CANDIDATES_PER_JOB]:
        if f.content_type not in ALLOWED:
            raise HTTPException(415, f"unsupported type {f.content_type}")
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "file too large")
        if job.kind == "inpaint" and job.crop_box:
            data = stitch_candidate(db, job, data)
        ext = os.path.splitext(f.filename or "")[1][:12] or ".png"
        stored = f"{uuid.uuid4()}{ext}"
        with open(os.path.join(folder, stored), "wb") as fh:
            fh.write(data)
        db.add(Attachment(
            campaign_id=job.campaign_id, filename=f.filename or stored, url=stored,
            mime=f.content_type, size=len(data),
            target_type=CANDIDATE, target_id=job.id,
            visibility="selected" if scene else "gm",
            visible_to=[job.created_by] if scene and job.created_by else [],
            uploaded_by=job.created_by,
        ))
    job.status = "ready"
    db.commit()
    return {"ok": True}


@worker_router.post("/image-jobs/{job_id}/fail")
def fail_image_job(
    job_id: str, error: str = Form(...), _: None = Depends(worker_auth),
    db: Session = Depends(get_db),
):
    job = db.get(ImageGenJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.status != "claimed":
        # заявку уже отменили, пересоздали или подобрал сборщик висяков — устаревший
        # отчёт о сбое не должен убивать не свою работу
        return {"ok": False, "ignored": job.status}
    job.status = "failed"
    job.claimed_at = None
    job.error = error[:2000]
    db.commit()
    return {"ok": True}
