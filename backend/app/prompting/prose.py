"""Сборка промпта прозой: хаб пишет один абзац видимого, код ставит стиль, рамку и якорь.

Z-Image читает текст энкодером Qwen3-4B, обученным на подписях-абзацах, а не на
тегах. Стенд `train/bench/light` (10.10.2026, 19 кейсов × 2 сида) показал: короткая
инструкция на ~3 тыс. знаков и абзац на 120–190 слов держат сеттинг не хуже
прежних 15 слотов по инструкции в 10–13 тыс. знаков, а текст ГМа — точнее.

Что держит код, а не хаб:
- голова стиля и рамка кадра — постоянны для направления;
- якорь класса у кадра: хаб выбирает пункт из закрытого списка, фраза встаёт первой;
- подмена земных слов (`wooden` → `riveted sheet`) — та же, что у тегов;
- регистр — словарь места и людей, дописанный к инструкции; он перебивает общий мир.
"""
from __future__ import annotations

import random
import re

from .lore import EN, FRAME_ANCHORS, OTHER, REGISTERS, VIEW_LAWS, swap_earth_words

_TASK = {
    "person": "You turn a game master's short description of a character (often Russian) into a picture "
              "of that one character in their place in this world.",
    "frame": "You turn a game master's short description of a thing or a place (often Russian) into a "
             "picture of it in this world. {view}",
    "action": "You turn a game master's short description of an action scene (often Russian) into a "
              "picture of that moment in this world.",
}
if EN:
    _TASK = {k: v.replace(" (often Russian)", "", 1) for k, v in _TASK.items()}

_WORLD = (
    "THE WORLD. Far future, a frontier sector far from any core; star travel is routine. Humans and xenos "
    "work side by side. Most things are kept running by the hands that use them, patched and refitted for "
    "generations; guilds, corporations and the rich own things that are clean, seamless and finely made. "
    "Planets hold ruins of a vanished pre-human civilisation: seamless black glassy material incised with "
    "dense geometric patterns, and cults that carry its relics. Built things are made of metal plate, "
    "composite and cast slab; clothing is synthetic fabric, hide and technical harness. Nothing here belongs "
    "to a historical period or to our present day: no period costume, no carpentry, no frontier-town or "
    "medieval look. Which corner of this world the picture belongs to is decided by the GM's words and by "
    "the corner named below."
)

_RULES = """RULES.
- Follow the GM literally: everything they named goes in; add only what the picture needs to be drawable.
- Write what the eye sees. Clothing and objects are described by cut, material, closure, length and wear, never by a purpose word alone (uniform, suit, jacket, cockpit, office): those draw our own century.
- Whatever has a familiar counterpart of ours (a vehicle, a weapon, a building, a whole planet) is drawn as ours unless you say how it visibly differs: what holds it up or moves it, its surface, colour and shape. Always write that difference.
- Proper names draw nothing: replace them with form and material.
- A living person opens with a face that lives before anything they wear: age, skin, hair, expression. Never call them a figure.
- Nobody here is called alien. Xenos are many different peoples and no two alike: each gets its own skin colour and texture, head, eyes and build, sometimes kin to an animal of ours, never the grey, big-eyed, eyeless or elongated-skull stereotype. A xenos opens with its body before anything it wears: head, skin, eyes and limbs, so it reads as non-human at a glance. It has as many limbs as the GM gave it, otherwise two arms and two legs.
- A vehicle is never named by our word for it (bike, car, truck, boat, plane): name its hull shape and what holds it up. Whatever floats: in the very sentence that first names it, say how high above the ground it hangs and that its shadow lies on the ground below it.
- English."""

_OUTPUT = ("Write one paragraph of 90 to 150 words describing exactly what is visible, most important first: "
           "the subject and what it is doing, then its clothing or form in concrete detail, then the place "
           "around it and what is far behind, then where the light comes from. Plain concrete visual "
           "language: no story, no feelings, no names, no camera or photography words, no art-style words.")

# Инструкция хабу по направлению — то, что ГМ видит и правит в Admin space.
# {view} у кадра — место закона подтипа, его ставит код
DOCS = {kind: "\n\n".join((_TASK[kind], _WORLD, _RULES, _OUTPUT)) for kind in _TASK}

# стойка корабля: без неё припаркованный борт выходит грузовиком на колёсах или висит в пустоте
SHIP_STANCE = (" A parked craft stands on extended landing gear on a landing pad or in a bay; a craft in "
               "motion has its engines lit with open space or sky around it.")

STYLE = ("Painterly sci-fi concept art with visible brush strokes, a detailed environment, far future "
         "exotic clothes and devices.")
CLOSE = "Painted in visible brush strokes as sci-fi concept art."

# Облик регистра — голова стиля со своей палитрой и светом. Словарь регистра в
# инструкции меняет только то, что хаб назовёт; общая голова тянула любой угол
# мира к одному ржавому полумраку
LOOKS = {
    "derelict": ("Painterly sci-fi concept art with visible brush strokes, a decaying palette of rust brown, corroded "
                 "orange and grimy grey with peeling faded paint, cold shafts of dead light cutting through dust and "
                 "darkness, barren lifeless decay, atmospheric depth."),
    "junk": ("Painterly sci-fi concept art with visible brush strokes, a dusty palette of rust orange, oxidised "
             "green and sun-bleached grey, harsh light and drifting dust, heaps of scrap detail."),
    "frontier": ("Painterly sci-fi concept art with visible brush strokes, a lived-in far future of matte composite, "
                 "brushed alloy, technical fabric and light built into the surfaces, a neutral base of warm grey and "
                 "graphite with accents of rust red, ochre and warm light, everyday clutter and wear from use, "
                 "atmospheric depth."),
    "hightech": ("Painterly sci-fi concept art with visible brush strokes, a clean bright palette of white, pale "
                 "grey and chrome with cool cyan accents, even luminous light, sleek far future design."),
    "hegemony": ("Painterly sci-fi concept art with visible brush strokes, a stern palette of black, gunmetal "
                 "grey and crimson accents, cold directional light, monumental symmetrical scale."),
    "luxe": ("Painterly sci-fi concept art with visible brush strokes, a luminous palette of ivory, pearl and "
             "champagne gold with deep living green, sweeping sculptural far future architecture, soft light "
             "glowing from within the surfaces, vast serene space."),
    "precursor": ("Painterly sci-fi concept art with visible brush strokes, colossal ancient ruins of a vanished "
                  "non-human civilisation, a palette of obsidian black, dust grey and pale ochre with a faint "
                  "cyan glow in the incised patterns, shafts of light through broken masses, vast scale, dust and "
                  "atmospheric depth."),
}
# если ГМ угол не выбрал, хаб выбирает его сам по словам ГМа — иначе всё
# скатывается в общий облик мира
CORNERS = {
    "derelict": "abandoned and decaying places nobody keeps up",
    "junk": "scrapyards, rust and salvage, slums and junk markets, scavengers living off broken things",
    "frontier": "the ordinary working space of the sector: ports, hangars, working ships, cantinas, outposts",
    "hightech": "guilds, corporations and the core: designed, machined, immaculate",
    "hegemony": "the Hegemony, its military and its houses: imperial order, rank, power, monumental scale",
    "luxe": "the rich and powerful at home: chosen materials, comfort, ornament",
    "precursor": "ruins and relics of the vanished pre-human civilisation, cults and the uncanny",
}

FRAMING = {
    "person": "A full-body view of a single person, head to feet, face clearly visible.",
    "ship": "A three-quarter view of the whole craft with its surroundings around it.",
    "handheld": "A close study of one object centred in the frame against a dim plain background.",
    "structure": "A wide shot of the whole structure in open space, black airless space on every side.",
    "planet": "A view from orbit of a whole planet against black airless space.",
    "landscape": "A wide establishing shot from ground level, the scene filling all four edges.",
    "interior": "A wide establishing shot of an enclosed space, the scene filling all four edges.",
    "action": "A wide dynamic action scene with figures in motion, the scene filling all four edges.",
}

# Лишнюю пару рук Z-Image не рисует ни по счёту, ни по образу многорукой статуи
# (та даёт шесть-восемь): держит только анатомия плеч, дописанная после абзаца
FOUR_ARMS = re.compile(r"(?<![\w-])four[- ]arm(?:ed|s)(?!\w)", re.I)
FOUR_ARMS_BODY = ("Four arms in total: two shoulders on each side, an upper pair of arms and a lower pair "
                  "of arms, each pair holding something different.")

GM_FOUR_ARMS = re.compile(r"четыр[её]хрук|четыре\s+рук|four[- ]arm", re.I)
XENO_KIN = ("a lizard", "a toad", "a heron", "an owl", "a big cat", "a hound", "a badger", "a boar",
            "an ox", "a goat", "a seal", "an octopus", "a catfish", "a beetle", "a moth", "a bat",
            "a hare", "a tortoise", "a crocodile", "a mole")
# Облик ксеноса — человекоподобное тело и несколько ярких черт из разных групп, как у
# мемцев из рульника; родство с животным — лишь один из исходов кубика
XENO_TRAITS = {
    "skin": ("fine overlapping scales", "glossy segmented chitin plates", "smooth hairless hide",
             "short dense fur", "translucent skin with faint veins showing beneath", "thick wrinkled hide",
             "skin set with small bony studs", "soft mottled skin like a frog's"),
    "head": ("a bony crest running back over the skull", "short tentacles growing instead of hair",
             "two curved horns", "fleshy frills at the jaw and neck", "a flat face with no nose, only two slits",
             "a long narrow skull", "a broad flat head", "feathery quills instead of hair",
             "long ears that move on their own"),
    "eyes": ("pure black eyes with no whites", "four eyes in two pairs", "large faceted eyes",
             "small eyes glowing faintly amber", "eyes with horizontal slit pupils", "wide golden eyes"),
    "build": ("very tall and thin with long limbs", "short, heavy and broad", "stooped with long arms",
              "lean and wiry", "massive, with a thick neck and shoulders", "slight and narrow-shouldered"),
}
ANIMAL_SHARE = 3
# канонические народы сектора: ГМ назвал народ — облик из рульника, кубик молчит
PEOPLES = {
    re.compile(r"мем(?:ец|ц[аыеуо]|ка|ки|ск)", re.I):
        "a Memian: a humanoid xenos with jet-black eyes, scaled skin in some shade of blue, violet or green, "
        "short tentacles growing instead of hair, ritual patterns carved into the scales and glowing algae "
        "worn on them",
}
if EN:
    PEOPLES = {
        re.compile(r"\bmemish\b", re.I):
            "a Memish: a humanoid xenos with jet-black eyes, scaled skin in some shade of blue, violet or green, "
            "short tentacles growing instead of hair, ritual patterns carved into the scales and glowing algae "
            "worn on them",
    }
XENO_HUES = ("ochre", "rust red", "olive green", "deep blue", "violet", "teal", "sand yellow", "chalk white",
             "coal black", "mottled orange and brown", "pale pink", "moss green with dark spots",
             "striped grey and white", "copper", "bone white with blue veins")

# парящий транспорт хаб зовёт каждый раз по-новому (skiff, frame, cycle), а модель
# на любое «hover-существительное» с наездником дорисовывает колёса
# Z-Image-Turbo почти не меняет кадр от сида к сиду: разных кандидатов дают только
# разные абзацы. Хаб пишет их в том же вызове — те же факты, другой взгляд
VARIANTS = 3
VARIANTS_RULE = (f"Then write {VARIANTS} more paragraphs (variants) of the same picture by the same rules: the same "
                 "subject, everything the GM named, the same clothing and the same place, but each one a "
                 "different take — another moment or pose, seen from another side, higher or lower, another "
                 "time of day and another light source. The variants differ from the paragraph and from each "
                 "other. Each variant is read alone, never next to the paragraph: it is complete and as long, and "
                 "describes in full again the body, the clothing and the place. A person or a creature is never seen from behind: the face stays visible.")

# Сборка частями: хаб пишет именованные части, код склеивает их в абзац в постоянном
# порядке. Общие части одни на все дубли — персонаж один, разные только кадры
TAKES = 4
PARTS = {
    "person": (("look", 0), ("face", 1), ("outfit", 0), ("pose", 1), ("place", 0), ("light", 1)),
    "frame": (("subject", 0), ("people", 0), ("place", 0), ("angle", 1), ("light", 1)),
    "action": (("subject", 0), ("place", 0), ("angle", 1), ("light", 1)),
}
PART_RULES = {
    "look": "who this is, in one or two sentences: human or xenos (a xenos opens with its most striking "
            "traits), sex, age, build, skin and hair or hide",
    "face": "the face and its expression; each take has its own face, but the same people, sex, age and "
            "colouring",
    "outfit": "what they wear, in concrete detail",
    "pose": "their pose and what they are doing",
    "place": "what kind of place this is and the things that make it that kind of place, then what is far "
             "behind; as a place only: nobody's pose or action in it",
    "time": "the time of day the GM named, in one sentence of how it shows on the sky and the place; an empty "
            "string when they named none",
    "light": "where the light comes from and from which side and height we see it; the light falls on the "
             "front of a person or a creature and they are never seen from behind or in silhouette",
    "subject": "what is pictured: shape, material, size and state",
    "people": "who is in the picture and what they are doing; empty when nobody is there",
    "angle": "from which side, height and distance we see it this time, and what is going on at this moment",
}
ACTION_SUBJECT = ("the action at its peak, frozen in one instant: who does what to whom, every side of it in "
                  "the frame, each figure caught mid-movement, and what the action itself throws into the air at "
                  "this instant; then each figure's body and clothing")
CAST = {
    "human": "The character is human, not a xenos.",
    "male": "The character is male.",
    "female": "The character is female.",
}
NOBODY = "Nobody is in the picture: no people and no creatures anywhere."
BLANKS = ("empty", "none", "n/a", "unspecified", "not specified")
DESERTED = "The place is deserted."


def own_parts(kind: str, people: str = "") -> list[tuple[str, int]]:
    """Части кадра. Людей нет — нет и их части: маркер «none» уходил в строку буквально."""
    return [(k, t) for k, t in PARTS[kind] if not (k == "people" and people == "none")]


def part_rule(kind: str, people: str = "") -> str:
    parts = own_parts(kind, people)
    rule = {**PART_RULES, "subject": ACTION_SUBJECT} if kind == "action" else PART_RULES
    shared = "; ".join(f"{k} — {rule[k]}" for k, t in [("time", 0), *parts] if not t)
    take = "; ".join(f"{k} — {rule[k]}" for k, t in parts if t)
    order = ", ".join(k for k, _ in parts)
    return (f"Write the picture as named parts, never as one paragraph: the code joins them in a fixed order — "
            f"{order} — into the paragraph the painter reads, so each part is plain visible description in full "
            f"sentences that reads on from the part before, and no part repeats another. Written once for the "
            f"whole picture: {shared}. Then {TAKES} takes of the same picture, each with: {take}. The takes "
            f"differ from each other: another moment, side, height and light, while a time of day the GM named "
            f"stays the same in all of them. One take with the parts written "
            f"once runs 90 to 150 words.")


def xeno_look(rng: random.Random) -> str:
    """Черты ксеноса: окрас и ещё три из разных групп, иногда родство с животным."""
    hue = rng.choice(XENO_HUES)
    if rng.randrange(ANIMAL_SHARE) == 0:
        rest = [f"kin to {rng.choice(XENO_KIN)} in the face and skin",
                rng.choice(XENO_TRAITS[rng.choice(("eyes", "build"))])]
    else:
        groups = ["skin"] + rng.sample(("head", "eyes", "build"), 2)
        rest = [rng.choice(XENO_TRAITS[g]) for g in groups]
    return f"a colouring of {hue}, " + ", ".join(rest)


def named_people(text: str) -> str:
    return next((look for pat, look in PEOPLES.items() if pat.search(text or "")), "")


def cast_rule(who: str = "", sex: str = "", seed_key: str = "", text: str = "") -> str:
    """Кто на портрете — по развилкам ГМа. Черты ксеноса того же персонажа всегда одни:
    кубик сеется ключом карточки. Что ГМ описал сам, кубик не трогает."""
    rng = random.Random(seed_key) if seed_key else random.Random()
    out = []
    people = named_people(text)
    if who == "human":
        out.append(CAST["human"])
    elif people:
        out.append(f"The character is {people}.")
    elif who == "xenos":
        out.append(f"The character is a xenos: humanoid in body plan, upright on two legs, yet plainly not "
                   f"human. Where the GM's words leave its body open, it has {xeno_look(rng)}. Whatever the GM "
                   f"described of its body wins over these. The look part names its most striking traits first.")
    else:
        out.append(xeno_seed(rng))
    if sex in ("male", "female"):
        out.append(CAST[sex])
    return " ".join(out)


def _sentence(text: str) -> str:
    text = str(text or "").strip()
    return text if not text or text[-1] in ".!?" else text + "."


def fold_time(slots: dict) -> dict:
    """Время суток ГМа хаб выписывает отдельным полем, а код вклеивает в общее место: так оно в каждом дубле."""
    hour = _sentence(slots.pop("time", ""))
    if hour and hour.strip(" .").lower() not in BLANKS and "place" in slots:
        slots["place"] = f"{_sentence(slots['place'])} {hour}".strip()
    return slots


def picture_of(kind: str, slots: dict, take: int = 0) -> str:
    takes = slots.get("takes") or [{}]
    one = takes[min(take, len(takes) - 1)] or {}
    nobody = slots.get("people") == "none"
    parts = [_sentence((one if t else slots).get(k, ""))
             for k, t in own_parts(kind if kind in PARTS else "frame", "none" if nobody else "")]
    if nobody:
        parts.append(DESERTED)
    return " ".join(x for x in parts if x)


HOVER = re.compile(r"(?<![\w-])hover(?:-[a-z]+?|[ ]?(?:bike|frame|cycle|skiff|skid|sled|vehicle|craft|car|board|platform))(s?)(?![\w-])",
                   re.I)

# планету с орбиты модель тянет к Земле, а при cfg 1 «no oceans or continents»
# вносит в кадр именно океаны и материки: такие фразы выкидываются целиком
PLANET_DENIAL = re.compile(r"\b(?:no|not|without|devoid|lacking|absent)\b[^.]*"
                           r"\b(?:oceans?|seas?|continents?|landmass(?:es)?|water)\b", re.I)
PLANET_WORDS = {r"\bterrestrial\b": "rocky", r"\blandmass(?:es)?\b": "regions", r"\bEarth\b": "a living world"}


def _planet(picture: str) -> str:
    kept = [s for s in re.split(r"(?<=[.!?])\s+", picture) if not PLANET_DENIAL.search(s)]
    picture = " ".join(kept)
    for word, swap in PLANET_WORDS.items():
        picture = re.sub(word, swap, picture, flags=re.I)
    return picture


def live_registers(kit: dict | None) -> dict:
    """Регистры кита в его порядке. Регистр без словаря выключен."""
    table = (kit or {}).get("registers")
    table = REGISTERS if table is None else table
    return {k: r for k, r in table.items() if isinstance(r, dict) and str(r.get("vocab") or "").strip()}


def _look(kit: dict | None, key: str) -> str:
    reg = live_registers(kit).get(key) or {}
    return str(reg.get("look") or "").strip() or LOOKS.get(key, STYLE)


def _corners(kit: dict | None) -> dict:
    return {k: str(r.get("corner") or "").strip() or CORNERS.get(k) or str(r.get("title") or k)
            for k, r in live_registers(kit).items()}


def _anchors(kit: dict, view: str) -> dict:
    table = (kit or {}).get("anchors")
    if table is None:
        return FRAME_ANCHORS.get(view) or {}
    return table.get(f"frame:{view}") or {}


def xeno_seed(rng: random.Random | None = None) -> str:
    """Кубик облика ксеноса: на низкой температуре хаб каждый раз писал одного и того же
    серого широкоплечего — разнообразие народов даёт только случайная подсказка."""
    rng = rng or random.Random()
    return (f"If the picture has a xenos, then where the GM's words leave its body open it has {xeno_look(rng)}; "
            f"whatever the GM described of its body wins over these.")


def gm_four_arms(text: str) -> bool:
    """Четыре руки ГМ назвал сам. Иначе хаб их выдумал, и анатомию плеч код не дописывает."""
    return bool(GM_FOUR_ARMS.search(text or ""))


def system_prompt(doc: str, kit: dict, kind: str, register: str, view: str = "interior",
                  outfit: dict | None = None, xeno: str = "", parts: bool = True, people: str = "") -> str:
    """Инструкция ГМа плюс то, что задают развилки окна: закон подтипа, регистр, якоря, наряд."""
    law = ((kit.get("views") or {}).get(view) or {}).get("law") or VIEW_LAWS.get(view, "")
    if view == "ship":
        law += SHIP_STANCE
    lines = [doc.replace("{view}", law if kind == "frame" else "").strip()]
    reg = live_registers(kit).get(register) if register else None
    if reg:
        vocab = reg.get("vocab", "")
        if kind == "person" and reg.get("vocab_person"):
            vocab = f"The place: {vocab} The people: {reg['vocab_person']}"
        elif kind == "frame" and view == "ship" and reg.get("vocab_ship"):
            vocab = f"{vocab} {reg['vocab_ship']}"
        lines.append("THIS CORNER OF THE WORLD — it overrides the general picture above wherever they "
                     "differ, including how clean or worn everything is. " + vocab)
    elif _picks_corner(register, kind, view):
        listed = "; ".join(f"{k} = {v}" for k, v in _corners(kit).items())
        lines.append("Also pick the corner of the world this picture belongs to (corner) from the fixed list, "
                     "by the GM's words — " + listed + ". Write the paragraph in that corner's look: its "
                     "materials, its state of repair, its light and colours.")
    if kind == "frame" and _anchors(kit, view):
        listed = "; ".join(f"{k} = {v}" for k, v in _anchors(kit, view).items() if v)
        lines.append("Also pick the class of the thing (anchor) from the fixed list — " + listed
                     + ". The nearest entry wins; " + OTHER + " only when nothing is close.")
    if kind == "person":
        if outfit and (outfit.get("wear") or outfit.get("gear")):
            fixed = []
            if outfit.get("wear"):
                fixed.append("They wear exactly: " + "; ".join(outfit["wear"]) + ".")
            if outfit.get("gear"):
                fixed.append("They carry: " + "; ".join(outfit["gear"]) + ".")
            lines.append("THEIR CLOTHING IS FIXED. " + " ".join(fixed)
                         + " Describe these as they are, and list them as wear and gear.")
        else:
            lines.append("Also list what the picture puts on them (wear) and what they carry (gear), "
                         "each as a short phrase.")
    if xeno and kind != "frame":
        lines.append(xeno)
    if people == "none" and kind != "person":
        lines.append(NOBODY)
    lines.append(part_rule(kind, people) if parts else VARIANTS_RULE)
    return "\n\n".join(lines)


def _picks_corner(register: str, kind: str, view: str) -> bool:
    """Угол выбирает хаб, когда ГМ его не назвал. Планете угол не нужен — она целиком."""
    return not register and not (kind == "frame" and view == "planet")


def schema(kind: str, view: str = "interior", kit: dict | None = None, register: str = "",
           parts: bool = True, people: str = "") -> dict:
    props: dict = {"time": {"type": "string"}} if parts else {}
    if _picks_corner(register, kind, view):
        props["corner"] = {"type": "string", "enum": list(_corners(kit))}
    if kind == "frame" and _anchors(kit or {}, view):
        props["anchor"] = {"type": "string", "enum": list(_anchors(kit or {}, view))}
    if parts:
        own = own_parts(kind, people)
        for k, t in own:
            if not t:
                props[k] = {"type": "string"}
        take = {k: {"type": "string"} for k, t in own if t}
        props["takes"] = {"type": "array", "minItems": TAKES, "maxItems": TAKES, "items": {
            "type": "object", "properties": take, "required": list(take), "additionalProperties": False}}
    else:
        props["picture"] = {"type": "string"}
    if kind == "person":
        arr = {"type": "array", "items": {"type": "string"}}
        props["wear"] = arr
        props["gear"] = arr
    if not parts:
        props["variants"] = {"type": "array", "items": {"type": "string"}, "minItems": VARIANTS,
                             "maxItems": VARIANTS}
    return {"type": "json_schema", "json_schema": {"name": "Picture", "strict": True, "schema": {
        "type": "object", "properties": props, "required": list(props), "additionalProperties": False}}}


def build(kind: str, slots: dict, view: str = "interior", kit: dict | None = None, register: str = "",
          take: int = 0) -> str:
    """Облик угла, рамка, якорь класса, абзац хаба с подменой земных слов, стиль ещё раз."""
    key = view if kind == "frame" else kind
    planet = kind == "frame" and view == "planet"
    style = STYLE if planet else _look(kit, register or str(slots.get("corner", "")))
    text = picture_of(kind, slots, take) if "takes" in slots else str(slots.get("picture", "")).strip()
    picture = HOVER.sub(lambda m: "hovering jet-sled" + m.group(1), text)
    picture = swap_earth_words(picture, "frame" if kind == "frame" else kind, dedup=False)
    anchor = _anchors(kit or {}, view).get(str(slots.get("anchor", ""))) if kind == "frame" else ""
    lead = f"The subject is a {anchor}. " if anchor else ""
    if planet:
        picture = _planet(picture)
    if kind != "frame" and slots.get("four_arms", True) and FOUR_ARMS.search(picture):
        picture += " " + FOUR_ARMS_BODY
    return f"{style} {FRAMING.get(key, FRAMING['person'])} {lead}{picture} {CLOSE}"


def prompts(kind: str, slots: dict, view: str = "interior", kit: dict | None = None,
            register: str = "") -> list[str]:
    """Строка на каждого кандидата: абзац хаба, затем его варианты той же сборкой."""
    if "takes" in slots:
        return [build(kind, slots, view, kit, register, i) for i in range(len(slots["takes"] or [{}]))]
    out = [build(kind, slots, view, kit, register)]
    for variant in slots.get("variants") or []:
        if str(variant).strip():
            out.append(build(kind, {**slots, "picture": variant}, view, kit, register))
    return out
