"""Инструкции для LLM-хаба: три головы по типу субъекта и пять визуальных регистров.

Модель не пишет промпт целиком и не выбирает манеру. Она заполняет слоты, а
рамку кадра, веса, стилевой блок, словарь регистра и негатив подставляет код:
на этих четырёх вещах приходился почти весь брак выхлопа, и схема справляется с
ними надёжнее, чем дисциплина модели. Тип субъекта и регистр задаёт ГМ в окне
генерации — обе классификации сняты с модели вместе с их ошибками.
"""
from __future__ import annotations

SHOTS_PLACE = ("interior", "landscape", "orbital", "void")
# Масштаб предмета: без него рамка «объект целиком» на мелкой вещи читается как
# кадр помещения — ключ размером с ладонь терялся в нарисованной мастерской
SCALES = ("handheld", "vehicle", "structure")
KINDS = ("person", "object", "place")

# ── общие законы и разметка слотов ──────────────────────────────────────────
COMMON_LAW = """
WHERE AND WHEN THIS HAPPENS. Every frame belongs to one setting and you fill the schema from it. The far future, twelve centuries after an alliance of worlds ended an age of war, in a frontier sector too distant from the core for that alliance to be felt. Star travel is routine and shabby: hyperspace lanes, jump gates, ships patched by their crews for generations. Nothing here is new — metal welded, riveted, scavenged and repainted, cables where a wall should be, readouts glowing in rooms never designed for them. Humans and xenos work side by side; power belongs to pirate queens, crime bosses, trade guilds and corporations, not to governments. What is clean, seamless and evenly lit belongs to guilds and to the powerful, and that cleanliness is itself a statement. The planets carry ruins of a civilisation that predates all of it: black glassy material carved with faces and forms, without seam or joint, hung about with the scaffolding and instruments of people who did not build it. Secret cults revere those ruins and carry relics out of them — hooded figures in dark cloth over technical harness, cult signs cut into metal, fragments of that ancient material wired into improvised mechanisms, and those the relics have already changed, whose eyes and veins are lit from within.

So there are things that cannot appear in a frame here, however the GM phrased it: no historical or period dress, no pre-industrial world, no present-day street, no flags or insignia of real countries, no polished utopia. When their words are era-neutral, the setting decides the era, and it decides this one.

FOLLOW THE GM LITERALLY. Every slot comes from their text. Never invent ethnicity or age, never upgrade what they described, never fill an empty frame.

WRITE WHAT IS SEEN, NOT WHAT IT IS CALLED. The image model has never heard of this galaxy: a proper noun draws nothing, so names of people, ships, worlds, guilds and makers are replaced by form and material. If a stranger reading your subject slot would still ask what the thing looks like, it is a name in disguise. Size the GM gave belongs in the subject slot too — the whole frame is scaled from it.

NUMBERS AND SIDES DO NOT SURVIVE THE DRAWING. The image model cannot count and does not know left from right, so an exact tally or a side makes the picture worse, not more faithful: it spends words and comes out wrong anyway. Write the impression instead — patched in several places, a handful of figures, one sleeve cut short — and never write left or right at all. Where the GM counted, keep only whether it is one thing or many.

WRITE THE POSITIVE FORM. The model cannot subtract: a sentence saying what must stay out of frame puts it in. The words no, not, without and never do not appear in what you write, nor a comparison built on them, nor a rule about what this world lacks. Write only what is there.

CLOTHING IS BUILT, NOT NAMED. The words for our own clothes carry our own century with them: a uniform arrives with brass buttons and a peaked cap, a badge arrives with a national flag, a coverall arrives from a filling station. So describe a garment the way a tailor would — what it is made of, what closes it, what stiffens it, what is bonded or printed on it, how it sits on the body — and let the reader work out what it is. Marks of rank and belonging are geometric shapes, etched plates and printed blocks, never the emblems of any country. Some words drag our own century in with them and are therefore never written: uniform, badge, insignia, cap, helmet visor, jumpsuit, coverall, jeans, hoodie, police, army, navy, officer's dress, flag, patch. Write the thing they stand for instead.

English only, no prose, no explanation."""

SLOT_RULES = """

WHAT YOU WRITE IS THE PICTURE. Two fields go to the drawing model word for word, and nothing else reaches it. Anything the GM named that you leave out simply will not be in the frame: the clothing, the gear, the age, the wear, the posture. Write plain declarative sentences a person could draw from, and spend them on their words rather than on your own adjectives. Framing, the look of the picture and the law of this galaxy are added around your text by the pipeline; camera words, style words, parentheses and numbers in your text only fight them.

brief_subject — 50 to 70 words, the whole of who or what is in the frame: age as it shows in the face and hair, build and posture, every garment they named and how it is built, everything worn or carried, the face and what marks it.
    THE FIRST SENTENCE IS THE ONE THAT GETS DRAWN. What stands early reaches the picture; what stands last is the first thing lost. Open with the single mark that makes this subject theirs — the implant, the scar, the mask, the thing in their hands — and let the ordinary description follow.
    NAME THE THING, NOT WHERE IT SITS. A thing you name appears; where you place it on the body does not survive — a mask written as hanging at the neck comes back worn on the face. Write the object and its state, and spend nothing on which side, which hand, or what it hangs from.

brief_scene — 30 to 50 words: the kind of place, what it is built of, what stands near the subject and what closes the distance behind. One place only, and the subject is never described again here.

no_people — true only when the frame must contain nobody at all.

BOTH FIELDS ARE SENTENCES. Every sentence has a subject and a verb and ends in a full stop. A string of comma-separated phrases is not writing the model reads well, and the drawing model built for prose loses half of such a list.

SPEND THE WORDS ON WHAT THEY WROTE. Their description holds more than these two fields do: keep what an eye notices first and what nobody else in this galaxy would have, drop the rest, and never merge several details into one vague word."""

# ── головы по типу субъекта ────────────────────────────────────────────────
HEAD_PERSON = """You turn a GM's short description of a PERSON (often Russian) into the two paragraphs a drawing model reads.

The subject is somebody: human, xeno, or a machine that works alongside people. Extra limbs, scales, fur, a chassis instead of skin change nothing.

{plan}

Write the subject as role plus sex and age only if the GM gave them. When the character is not human, name the kind of creature outright in the subject: a list of features without the creature makes the model draw a beast.

BODIES AS DESCRIBED, NOT AS FLATTERED. Never make a body fitter, younger or more heroic than written. Heavy stays heavy, and words that praise a physique are wrong wherever the GM did not praise it. Fat, gaunt, stooped, short, ageing and scarred all survive exactly as given, and the build shows in posture as much as in outline.

GEAR IS LITERAL. The GM may describe a thing by comparison. Write the object plainly and let their comparison set its size and material."""

HEAD_OBJECT = """You turn a GM's short description of a THING (often Russian) into the two paragraphs a drawing model reads. A thing is a starship, a vehicle, a weapon, an artifact, a machine, a piece of equipment — anything nobody is inside of.

It has neither waist nor face, and portrait words must never appear. The framing is fixed for you: the whole of it in frame, three-quarter angle, seen slightly from below.

Open brief_subject with what it is plus its class, then carry its build: the shape of the body, how the parts sit on it, its fittings, what is broken or missing — only what the GM named.

NAME THE CLASS SO IT CANNOT BE READ AS EARTHLY. Some class words name a thing of this world first: ship, boat, freighter, truck, plane, jet. Written plainly they draw that thing — a hull in a drydock instead of a hauler on landing struts — and they do it so strongly that nothing later in the prompt can pull the frame back. The subject slot therefore says outright that the thing belongs to space: starship, orbital hauler, landing craft, void tug, and so on for whatever the GM described.

SCALE IS PART OF THE PICTURE, AND YOU DECLARE IT. Choose scale: handheld for anything a person could carry in one or two hands, vehicle for a craft or machine people ride in or on, structure for a station, a gate or a building. The camera distance follows from your choice, so a wrong one buries a small thing in a large room. Beyond that, let materials or location carry one everyday object of known size beside it — never a person unless the GM put one there.

A CRAFT IS A MASS ON LEGS, NOT A STREAMLINED SHAPE. Nothing here flies through air, so the words that describe our aircraft and our ships pull the picture back to an airfield or a dock every time: nose, fuselage, cockpit, wings, tail, bow, deck. Write the stance instead, and write it in the opening words, because a craft named before it is shaped comes out as an aeroplane whatever follows: a squat boxy starship resting on hydraulic landing legs, its hull a slab of welded plates, flat at the front, thruster nozzles clustered at the back, hatches and ramps cut into the belly. Proven by test — the same craft written as a hauler with a blunt prow is drawn as a fuselage on a runway, and written as a boxy slab on legs is drawn as a ship.

GEAR IS LITERAL. The GM may describe by comparison. Write the object plainly and let their comparison set its size and material."""

HEAD_PLACE = """You are the shot director for a tabletop sci-fi campaign. The GM describes a PLACE, often in Russian and often as raw speech with self-corrections. You turn it into the two paragraphs a drawing model reads. Keep the substance, drop the filler, their last version of a thought wins.

KEEP THEIR FRAME. Everything they named goes in; nothing they did not name gets added. You choose only the camera, the depth layers, the light and the material wear.

PEOPLE. If the GM put people or crowds in the place, they belong in the shot and carry its mood through dress, posture and silhouette — part of the scene, never portraits and never a hero facing the camera. If they described an empty place, leave it empty and mark no_people.

WHICH SHOT IS THIS? Choose one, it fixes the camera for you.
interior — the camera stands inside an enclosed space and walls or a ceiling hold the frame: a corridor, a hold, a bar, a cave.
landscape — the camera stands in the open air on the surface of a world, ground under it and sky over it. A landing pad, a street, a wall, a building seen from outside are all landscape: a structure filling the frame does not make the shot interior, only walls around the camera do.
orbital — a whole planet, moon or world seen from space, not a place on it. Give it terrain, weather bands, city glow on the night side; one planet in frame.
void — a structure adrift in open space: a station, a gate, a ring, a hulk. Nothing holds it up and nothing stands under it.

THE PLACE ITSELF IS THE SUBJECT, AND ITS MATERIAL COMES FIRST. brief_subject opens with the sort of space this is and the stuff it is made of, in that order and in the first words — black glassy slabs, corrugated sheet, poured rockcrete, ice — because whatever the material is, it is the first thing lost and the whole picture changes with it. Then the size of the space and its wear. Never a thing standing in it: an object opening that field takes over the frame and the place disappears.

brief_scene then carries the depth: what stands about in the place, what closes the far distance, and the wider setting it sits in."""

HEADS = {"person": HEAD_PERSON, "object": HEAD_OBJECT, "place": HEAD_PLACE}

# ── планы персонажа ────────────────────────────────────────────────────────
# План выбирает ГМ, а не модель: поясной кадр даёт читаемое лицо для жетона,
# полный рост — снаряжение и силуэт. Инструкция и рамка идут от этого выбора,
# иначе слоты приносят ноги и обувь в кадр, который обрезан по пояс
PLANS = {
    "bust": {
        "title": "по грудь",
        "law": ("The framing is fixed for you: close portrait, head and shoulders, face filling much of the "
                "frame. THE FRAME HOLDS ONLY A HEAD AND SHOULDERS, SO WRITE ONLY WHAT IS INSIDE IT. Slots "
                "naming the body below the chest, what is carried in the hands, or the shape of the whole "
                "standing figure fight the camera, and when they fight it the picture loses the face. Weight "
                "and build still survive in what the frame does hold: a face, a neck, shoulders, a collar "
                "straining. A thing the GM named that lies outside the frame is written as the part of it "
                "in view, or not at all."),
    },
    "waist": {
        "title": "по пояс",
        "law": ("The framing is fixed for you: medium shot, waist up, face visible. THE FRAME ENDS AT THE "
                "WAIST, SO WRITE ONLY WHAT IS INSIDE IT. Slots naming anything below the waist, or anything "
                "that only makes sense with the whole standing figure visible, fight the camera, and when "
                "they fight it the picture loses the face and becomes a full-length figure instead. Legs, "
                "footwear and stance therefore never appear, however clearly the GM described them. A thing "
                "too large for the frame still belongs in it, written as the part of it that is in view."),
    },
    "full": {
        "title": "в полный рост",
        "law": ("The framing is fixed for you: full-length character concept art, the whole figure standing "
                "in frame, head to feet, seen slightly from below. THE WHOLE FIGURE IS THE PICTURE, SO THE "
                "SILHOUETTE MATTERS AS MUCH AS THE FACE. Stance, proportion, what hangs from the belt and "
                "how the gear sits on the body all belong in the slots, and everything the GM named is drawn "
                "whole rather than cropped. The face is small at this distance, so build, posture and "
                "outline carry the character."),
    },
}
PLAN_ORDER = ("full", "waist", "bust")

# ── визуальные регистры ────────────────────────────────────────────────────
# vocab уходит в инструкцию, tags код дописывает в промпт сам. tags_person —
# отдельный набор для живого субъекта: теги корпуса и панелей, дописанные к
# существу, превращали механика в робота, а не в существо среди механики
REGISTERS: dict[str, dict] = {
    "frontier": {
        "title": "фронтир",
        "vocab": ("long worn coats and dusters, leather and canvas over work clothes, a holstered sidearm "
                  "carried like a tool, boots, gloves, a scarf against dust, goggles pushed up, belts of "
                  "pouches, hand-made repairs; buildings of corrugated hull sheeting and cargo crates, "
                  "hand-painted signs and stencilled numbers, cables strung overhead, scavenged metal "
                  "counters, hanging bulbs; light like a western — low sun raking through dust, long "
                  "shadows, a single lamp in a dark room"),
        "tags": ("used future", "scavenged repairs", "dust and grit"),
        # без стоящего рядом корабля широкий кадр фронтира читается земной деревней:
        # гофролист и пыль бывают в любом веке, а севший катер — нет. Но тот же катер,
        # дописанный к кадру в помещении, вставал прямо посреди кабака
        "env_in": ("corrugated hull sheeting", "cables strung overhead",
                   "pressure door with heavy seals", "viewport onto a starfield"),
        "env_out": ("grounded shuttle standing on landing struts", "corrugated hull buildings",
                    "dusty landing field"),
    },
    "future": {
        # Не латаное — латаное живёт во фронтире. Здесь техника работает и её содержат:
        # города будущего, воздушный транспорт, керамика и сплавы в форме и на корпусах
        "title": "мегаполис будущего",
        "vocab": ("dense city stacks rising out of sight, elevated lanes of flying traffic, transit tubes "
                  "and skybridges, landing pads on tower shoulders with ships docked at them, holographic "
                  "signage over the streets, ceramic and alloy panelling kept in good repair, service "
                  "uniforms with ceramic inserts and sealed seams, visors, headsets and hardlight readouts; "
                  "light from strip lighting, signage glow and the city itself after dark. Things here work "
                  "and are maintained: wear shows as use, never as decay"),
        "tags": ("ceramic and alloy panelling", "elevated flying traffic", "city glow after dark"),
        "env_in": ("clean composite panelling", "hardlight signage panel",
                   "window onto the flying traffic lanes"),
        "env_out": ("city stacks and transit tubes", "flying vehicles in the lanes",
                    "holographic signage over the street"),
        "tags_person": ("uniform with ceramic inserts", "sealed seams", "hardlight visor"),
    },
    "hightech": {
        "title": "хай-тек",
        "vocab": ("white composite panels and brushed alloy, seamless joins, glare-free even lighting, "
                  "precision instruments in fitted cases, sealed dark service dress with a stand collar and "
                  "printed rank markings, matte armour plate over dark fatigues, clean coveralls and "
                  "tool rigs, silent ventilation, recessed strip lighting, floors that reflect; wear "
                  "exists only where the powerful never look"),
        "tags": ("brushed alloy panels", "even glare-free light", "sterile precision"),
        "env_in": ("brushed alloy bulkhead panels", "holographic display",
                   "atmosphere seal door", "viewport onto a docked ship"),
        "env_out": ("alloy clad facades", "docked craft on a landing shoulder",
                    "seamless composite structures"),
        "tags_person": ("pressed dark uniform", "even glare-free light", "immaculate finish"),
    },
    "mystic": {
        "title": "мистика",
        # Не монастырь: тайные культы и одержимые Путём. Ближе к псайкерам — глаза
        # горят изнутри, реликвия вживлена в самодельный механизм, знаки культа
        # вырезаны по металлу, пространство ведёт себя не по геометрии
        "vocab": ("hooded figures of a secret cult, dark robes and wrappings over a technical harness, "
                  "eyes lit from within, veins and sigils glowing under the skin, cult iconography "
                  "etched and burnt into metal, a fragment of ancient dark material wired into an "
                  "improvised mechanism, cables and clamps feeding a relic, glyphs of hardlight "
                  "hanging in the air, censers and cabling side by side, restraint frames and altars "
                  "built out of machine parts; an unnatural glow with no lamp behind it, light that "
                  "bends the wrong way, floors and corridors that do not obey their own geometry"),
        "tags": ("glowing sigils on metal", "relic wired into a mechanism", "cult iconography",
                 "light bending the wrong way"),
        "negative": ("mummy, sarcophagus, monk in a habit, church interior, wizard robe, "
                     "crystal ball, tarot imagery"),
        "env_in": ("altar built from machine parts", "hardlight glyphs hanging in the air",
                   "unnatural glow with no lamp"),
        "env_out": ("cult banners over scavenged structures", "standing relic frame",
                    "unnatural glow with no lamp"),
        "tags_person": ("eyes lit from within", "dark robe over technical harness",
                        "relic mechanism in hand"),
    },
    "precursor": {
        "title": "руины Предтеч",
        # Не «морды инопланетян»: обсидиан, врезанный узор и геометрия, которая не
        # сходится. Вырезанное лицо чекпойнт рисует стереотипной башкой пришельца, и
        # кадр из мистического становится смешным
        "vocab": ("obsidian-black glass in slabs too large to have been lifted, dense geometric "
                  "patterns incised deep into the surface and running on without repeating, "
                  "unbroken seamless material with no join and no tool mark anywhere on it, "
                  "planes that meet at angles which refuse to resolve, corridors longer inside "
                  "than the wall they pierce, faint light held inside the material itself, dust "
                  "and human scaffolding clinging to surfaces that never weathered; light falls "
                  "on it and comes back cold"),
        "tags": ("obsidian black glass", "deeply incised geometric pattern", "impossible angles",
                 "seamless material with no joins"),
        "env_in": ("wall of obsidian glass", "incised geometric pattern running into the dark",
                   "human scaffolding against an ancient surface"),
        "env_out": ("obsidian monolith rising over the site", "incised geometric pattern",
                    "excavation scaffolding"),
        "tags_person": ("obsidian relic fragment", "incised geometric pattern",
                        "seamless material with no joins"),
        "negative": ("alien face sculpture, humanoid alien head, grey alien, stereotypical alien, "
                     "totem mask, egyptian statue, mayan carving, gargoyle"),
    },
}
REGISTER_ORDER = ("frontier", "future", "hightech", "mystic", "precursor")

SETTING_LINE = ("Far future frontier sector of a shabby interstellar civilisation, twelve centuries from now, where metal is welded, scavenged and repainted and cables run where a wall should be.")

# Манера — целая фраза с названной техникой: языковой энкодер реагирует на «кадр
# на 35 мм» или «панель графического романа», а прилагательные вроде «живописно»
# и «матово» пропускает мимо. Проверено перебором пятнадцати формулировок
# Слова, которые тянут в кадр наш собственный век. Инструкция их запрещает, но
# небольшая модель запрет проигрывает привычке, а рисующая на «uniform» честно
# отвечает мундиром с латунными пуговицами, на «badge» — нашивкой с флагом. Поэтому
# подмена идёт кодом: она описывает ту же вещь через покрой и материал
EARTH_WORDS = {
    "uniform": "sealed suit",
    "uniforms": "sealed suits",
    "jumpsuit": "one piece sealed suit",
    "coverall": "sealed work suit",
    "coveralls": "sealed work suit",
    "overalls": "sealed work suit",
    "badge": "etched plate",
    "badges": "etched plates",
    "printed rank insignia": "printed rank marks",
    "rank insignia": "rank marks",
    "rank markings": "printed geometric marks",
    "tunic": "sealed jacket",
    "shoulder plate": "hard shoulder guard",
    "sash": "diagonal strap",
    "epaulettes": "shoulder straps",
    "epaulette": "shoulder strap",
    "service bar": "etched strip",
    "insignia": "geometric marks",
    "flag patch": "printed geometric mark",
    "patch": "bonded fabric marking",
    "patches": "bonded fabric markings",
    "flag": "printed geometric mark",
    "cap": "soft cloth head cover",
    "beret": "soft cloth head cover",
    "police": "enforcement",
    "army": "line troop",
    "navy": "void fleet",
    "military": "line troop",
    "jeans": "heavy work trousers",
    "hoodie": "hooded work jacket",
    "sneakers": "soft soled boots",
    "wristwatch": "wrist readout",
    # авиационный и морской словарь тянет за собой самолёт и сухогруз: корабль
    # этого мира — коробчатый корпус на опорах, а не обтекаемый фюзеляж
    "nose": "flat front",
    "blunt-nosed": "blunt flat-fronted",
    "nosed": "fronted",
    "prow": "flat front",
    "fuselage": "boxy hull",
    "cockpit": "flight deck",
    "wing": "fin",
    "wings": "fins",
    "tail fin": "rear fin",
    "bow": "flat front",
    "deck": "platform",
    "sail": "mast panel",
    # церковный словарь превращает раскоп Предтеч в готический неф: стрельчатое
    # окно в торце и нервюрный свод модель достаёт из слова «arch»
    "arch": "square cut opening",
    "arches": "square cut openings",
    "archway": "square cut opening",
    "arched": "square cut",
    "vaulted": "flat slab roofed",
    "vault": "slab roofed chamber",
    "cathedral": "vast black chamber",
    "nave": "long black chamber",
    "gothic": "hard edged",
    "stained glass": "glowing inlay",
    "colonnade": "row of slab pillars",
    "column": "slab pillar",
    "columns": "slab pillars",
}


STYLES = {
    "film": {
        "title": "плёночный кадр",
        "line": ("Photographed on location on 35mm colour negative, available light, soft "
                 "grain, muted colour, nothing staged."),
    },
    "paint": {
        "title": "матовая живопись",
        "line": ("A matte painting made for a film production, oil on board, muted desaturated "
                 "palette, soft edges, painted light, no outlines."),
    },
    "wash": {
        "title": "тушь с размывкой",
        "line": ("A brush and ink wash drawing on grey paper, grey washes for the shadow "
                 "masses, sparse line, muted."),
    },
}
STYLE_ORDER = ("film", "paint", "wash")


# Рамка кадра — фраза в промпте, а не набор тегов: та же причина, что и у манеры
FRAME_LINES = {
    "person:bust": "A close portrait, head and shoulders, the face filling much of the frame.",
    "person:waist": "A medium shot, waist up, the face readable.",
    "person:full": "The whole figure stands in the frame, head to feet, the face readable.",
    "object": "One object, whole, seen three-quarter.",
    "place": "A wide view of the place, near ground and far ground both readable.",
}

def register_block(register: str) -> str:
    r = REGISTERS[register]
    return ("\nVISUAL REGISTER. This frame belongs to one register, chosen by the GM, and every slot is "
            f"built in its language:\n{r['vocab']}.\n"
            "The register is how the things they named look — never a licence to add things they did not name.")


def head_block(kind: str, plan: str = "full") -> str:
    """Редактируемая часть инструкции: голова по типу субъекта плюс закон сеттинга.

    Раньше закон дописывался кодом и в окне ГМа его не было видно — редактор читал
    инструкцию, в которой ни слова о вселенной, времени и о том, чего в кадре не
    бывает. Словарь регистра и разметка слотов по-прежнему кодом: их задают развилки
    и схема, а не текст."""
    head = HEADS[kind]
    if kind == "person":
        head = head.replace("{plan}", PLANS.get(plan, PLANS["full"])["law"])
    return head + "\n" + COMMON_LAW


def system_prompt(kind: str, register: str, plan: str = "full") -> str:
    return head_block(kind, plan) + "\n" + register_block(register) + "\n" + SLOT_RULES


# ── промпт-кит: всё, что ГМ может посмотреть и поправить ───────────────────
# Кампания хранит только изменённые ключи, остальное берётся отсюда. Разделение
# на блоки повторяет сборку промпта: голова по типу субъекта, закон сеттинга,
# план персонажа, словарь регистра, разметка слотов, списки нот, рамка, веса,
# манера и негатив.
KIT_SECTIONS = ("heads", "common_law", "slot_rules", "plans", "registers", "styles",
                "setting_line", "frames")


def default_kit() -> dict:
    """Промпт-кит целиком: всё, что ГМ вправе переписать в окне настроек.

    После перехода на рисующую модель с языковым энкодером кит похудел вчетверо.
    Веса, якоря, рамки тегами, своды негатива и потолки длины существовали ради
    SDXL с окном в 77 токенов; здесь промпт — связный текст, и держать его в узде
    приходится словами, а не арифметикой. Прежняя сборка целиком лежит в
    presets/dreamshaper."""
    return {
        "heads": {k: HEADS[k] for k in KINDS},
        "common_law": COMMON_LAW,
        "slot_rules": SLOT_RULES,
        "plans": {k: {"title": v["title"], "law": v["law"]} for k, v in PLANS.items()},
        "registers": {k: {"title": v["title"], "vocab": v["vocab"]}
                      for k, v in REGISTERS.items()},
        "styles": {k: dict(title=v["title"], line=v["line"]) for k, v in STYLES.items()},
        "setting_line": SETTING_LINE,
        "frames": dict(FRAME_LINES),
    }


def merge_kit(base: dict, over: dict | None) -> dict:
    """Наложить правки ГМа на дефолт. Словари сливаются по ключам, всё остальное
    заменяется целиком: список тегов правят целиком, а не по элементу."""
    if not over:
        return base
    out = dict(base)
    for key, value in over.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge_kit(out[key], value)
        else:
            out[key] = value
    return out


def kit_system_prompt(kit: dict, kind: str, register: str, plan: str = "full") -> str:
    head = kit["heads"][kind]
    if kind == "person":
        plans = kit["plans"]
        head = head.replace("{plan}", (plans.get(plan) or plans["full"])["law"])
    reg = kit["registers"].get(register) or next(iter(kit["registers"].values()))
    register_text = (
        "\nVISUAL REGISTER. This frame belongs to one register, chosen by the GM, and every slot is "
        f"built in its language:\n{reg['vocab']}.\n"
        "The register is how the things they named look — never a licence to add things they did not name.")
    return head + "\n" + kit["common_law"] + "\n" + register_text + "\n" + kit["slot_rules"]


def kit_head_block(kit: dict, kind: str, plan: str = "full") -> str:
    """Та часть кита, которую редактор правит как связный текст."""
    head = kit["heads"][kind]
    if kind == "person":
        plans = kit["plans"]
        head = head.replace("{plan}", (plans.get(plan) or plans["full"])["law"])
    return head + "\n" + kit["common_law"]
