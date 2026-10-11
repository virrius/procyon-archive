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

WRITE THE POSITIVE FORM. The model cannot subtract, so a thing defined by what it lacks is written as what it is instead. The words no, not and without never appear in a slot, nor a comparison built on them; keeping things out of frame is the pipeline's job.

English only, no prose, no explanation."""

SLOT_RULES = """

WHAT YOU WRITE IS THE PICTURE. These fields go to the drawing model word for word — they are not notes and nothing else reaches it. Anything the GM named that you leave out simply will not be in the frame: the clothing, the gear, the age, the wear, the posture. Write plain declarative sentences a person could draw from, and spend them on their words rather than on your own adjectives.

brief_subject — 50 to 70 words, the whole of who or what is in the frame: age as it shows in the face and hair, build and posture, every garment they named and its state, everything worn or carried, the face and what marks it. Their words about clothing and gear survive here or nowhere.
    THE FIRST SENTENCE IS THE ONE THAT GETS DRAWN. What stands early in this field reaches the picture; what stands last is the first thing lost. So open with the single mark that makes this subject theirs — the implant, the scar, the mask, the thing in their hands — and let the ordinary description follow it.
    NAME THE THING, NOT WHERE IT SITS. A thing you name appears; where you place it on the body does not survive — a mask written as hanging at the neck comes back worn on the face. Write the object and its state, and spend nothing on which side, which hand, or what it hangs from.
brief_scene — 30 to 50 words: the kind of place, what it is built of, what stands near the subject and what closes the distance behind.
brief_light — one sentence, the source and direction of the light.

YOU FILL SLOTS, NOT A PROMPT. Framing, weights, style tags, register vocabulary and the negative prompt are added by the pipeline; parentheses, numbers, camera and style words in a slot spoil the prompt.

Every slot value is a lowercase noun phrase of one to four English words with no comma inside it.

subject — what the picture is of, 2-4 words.
accent — the one thing besides the subject the picture dies without. For a person it is something about them: build, face, hair, marking or bearing. Gear belongs in attributes however striking, because at the weight of an accent a large piece of equipment grows until it replaces whoever holds it.
age — person only, pick the band that holds the years the GM gave, from the fixed list: their number of years decides the band, and when they gave no number their words about the face and hair decide it. A number draws nothing; the band is what carries the years into the face and the posture. Pick the unspecified band only when their text says nothing about age at all.
face — 2 phrases, person only: the face and gaze, and what marks it — scars, implants, hair, the state of the skin.
subject_detail — 3 phrases describing the subject up close, in the GM's own terms.
attributes — 3 things worn, carried or fitted; only what they named.
location — 2 phrases for the single place it is in.
layers — 2 phrases, place only: what stands in the near ground and what closes the far ground.
materials — 1 phrase of surface, wear and texture.
light — one phrase naming the source and how it falls.
scifi_note — one detail of this galaxy that could already belong to the frame they described, in your own words. It is what keeps the picture from reading as an ordinary western or a present-day room, so it has to be a thing this world has and ours does not, at the scale of the frame: what fits a hand-sized object is not what fits a city. Attach it to something they named, never drag a new object into the shot.
mood — 1 phrase of atmosphere or palette.
no_people — true only when the frame must contain nobody at all.

THE SLOTS ARE FEW ON PURPOSE. The image model reads about sixty words and paints the rest from its own habits, so a long list of details does not add them to the picture — it dilutes the ones that matter. Their description will hold more than the slots do: keep what an eye notices first and what nobody else in this galaxy would have, drop the rest, and never merge several details into one vague word."""

# ── головы по типу субъекта ────────────────────────────────────────────────
HEAD_PERSON = """You turn a GM's short description of a PERSON (often Russian) into slots for an SDXL prompt.

The subject is somebody: human, xeno, or a machine that works alongside people. Extra limbs, scales, fur, a chassis instead of skin change nothing.

{plan}

Write the subject as role plus sex and age only if the GM gave them. When the character is not human, name the kind of creature outright in the subject: a list of features without the creature makes the model draw a beast.

BODIES AS DESCRIBED, NOT AS FLATTERED. Never make a body fitter, younger or more heroic than written. Heavy stays heavy, and words that praise a physique are wrong wherever the GM did not praise it. Fat, gaunt, stooped, short, ageing and scarred all survive exactly as given, and the build shows in posture as much as in outline.

GEAR IS LITERAL. The GM may describe a thing by comparison. Write the object plainly and let their comparison set its size and material."""

HEAD_OBJECT = """You turn a GM's short description of a THING (often Russian) into slots for an SDXL prompt. A thing is a starship, a vehicle, a weapon, an artifact, a machine, a piece of equipment — anything nobody is inside of.

It has neither waist nor face, and portrait words must never appear. The framing is fixed for you: the whole of it in frame, three-quarter angle, seen slightly from below.

Write the subject as what it is plus its class. subject_detail carries its build: the shape of the body, how the parts sit on it, what is broken or missing. attributes carry its fittings — only what the GM named.

NAME THE CLASS SO IT CANNOT BE READ AS EARTHLY. Some class words name a thing of this world first: ship, boat, freighter, truck, plane, jet. Written plainly they draw that thing — a hull in a drydock instead of a hauler on landing struts — and they do it so strongly that nothing later in the prompt can pull the frame back. The subject slot therefore says outright that the thing belongs to space: starship, orbital hauler, landing craft, void tug, and so on for whatever the GM described.

SCALE IS PART OF THE PICTURE, AND YOU DECLARE IT. Choose scale: handheld for anything a person could carry in one or two hands, vehicle for a craft or machine people ride in or on, structure for a station, a gate or a building. The camera distance follows from your choice, so a wrong one buries a small thing in a large room. Beyond that, let materials or location carry one everyday object of known size beside it — never a person unless the GM put one there.

GEAR IS LITERAL. The GM may describe by comparison. Write the object plainly and let their comparison set its size and material."""

HEAD_PLACE = """You are the shot director for a tabletop sci-fi campaign. The GM describes a PLACE, often in Russian and often as raw speech with self-corrections. You turn it into slots for an SDXL prompt. Keep the substance, drop the filler, their last version of a thought wins.

KEEP THEIR FRAME. Everything they named goes in; nothing they did not name gets added. You choose only the camera, the depth layers, the light and the material wear.

PEOPLE. If the GM put people or crowds in the place, they belong in the shot and carry its mood through dress, posture and silhouette — part of the scene, never portraits and never a hero facing the camera. If they described an empty place, leave it empty and mark no_people.

WHICH SHOT IS THIS? Choose one, it fixes the camera for you.
interior — the camera stands inside an enclosed space and walls or a ceiling hold the frame: a corridor, a hold, a bar, a cave.
landscape — the camera stands in the open air on the surface of a world, ground under it and sky over it. A landing pad, a street, a wall, a building seen from outside are all landscape: a structure filling the frame does not make the shot interior, only walls around the camera do.
orbital — a whole planet, moon or world seen from space, not a place on it. Give it terrain, weather bands, city glow on the night side; one planet in frame.
void — a structure adrift in open space: a station, a gate, a ring, a hulk. Nothing holds it up and nothing stands under it.

THE PLACE ITSELF IS THE SUBJECT, AND THE SUBJECT SLOT NAMES A KIND OF PLACE. Two to four words for the sort of space this is, never a thing standing in it: an object in that slot takes over the frame and the place around it disappears. What makes the place unlike anywhere else goes into accent, location carries the wider setting it sits in, and the things that stand about in it are attributes."""

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

# Закрытый список внеземных нот. Свободным текстом модель заполняла его земными
# вещами («кобура», «неоновая вывеска»), и кадр читался обычным вестерном — enum
# делает внеземную деталь гарантией схемы, а не удачей прогона. Ноты разбиты по
# тому, к чему крепятся: небо не бывает в коридоре, ремень — у пустого кадра
# Архетип кадра — закрытый список, якорь к нему дописывает код перед субъектом.
# Работает как перевод: слова ГМа модель кладёт в слоты как есть, а якорь уводит
# чекпойнт от приора этого мира — «офицер» без него выходил патрульным с бляхой,
# «солдат» — сегодняшней пехотой, «корабль» — сухогрузом в доке. Якорь называет
# класс и, где важно, форму; одежду и приметы несут слоты, чтобы он не спорил
# с описанием. Ключ «прочее» оставляет кадр без якоря.
PERSON_ROLES = {
    # «trooper» приводил клонический шлем, «bounty hunter» — мандалорца целиком:
    # франшизный токен рисует своего героя вперёд описания
    "soldier": "armoured soldier in sealed fatigues",
    # «флотский офицер» приводил фуражку и золотое шитьё, а слово uniform в
    # позитиве заодно снимало условный негатив против парадного мундира
    "officer": "trade guild officer in a sealed high-collared dark uniform",
    "pilot": "starship pilot",
    "ship crew": "starship crew hand",
    "mechanic": "starship mechanic",
    "scavenger": "frontier scavenger",
    "bounty hunter": "armed tracker in practical fieldwear",
    "criminal": "syndicate enforcer",
    "trader": "frontier trader",
    "official": "trade guild functionary",
    "medic": "field medic",
    "scholar": "xenoarchaeologist at a dig",
    "cultist": "hooded cult devotee",
    "psyker": "relic-touched psyker, glow beneath the skin",
    "courier": "city courier",
    "civilian": "colony civilian",
    "xeno": "non-human alien being",
    "прочее": "",
}
PLACE_KINDS = {
    "ship interior": "starship interior with bulkhead ribs and pressure doors",
    "station interior": "orbital station interior",
    "colony interior": "colony room built of scavenged hull sheeting",
    "drinking hall": "frontier drinking hall",
    "market": "covered frontier market",
    "workshop": "repair shop full of salvaged parts",
    "hangar": "landing bay with craft on struts",
    "city street": "street between city stacks",
    "landing field": "dusty landing field",
    "wilderness": "open planetary surface under an alien sky",
    "ruin": "ruin of black seamless precursor material",
    "open space": "open space with faint stars",
    "прочее": "",
}
OBJECT_FAMILIES = {
    "starship": ("boxy industrial starship hull on landing struts, exposed piping and "
                 "mismatched plating"),
    "small craft": "blunt nosed shuttle craft on landing struts",
    "ground vehicle": "ground vehicle with wheels or tracks",
    "walking machine": "walking machine on legs",
    "industrial machine": "industrial machine bolted to a deck",
    "handheld tool": "handheld tool",
    "weapon": "weapon",
    "relic artifact": "alien artifact",
    "orbital structure": "structure in open space",
    "building": "building on a planet surface",
    "прочее": "",
}
# Возраст словами, не числом: «forty five years old» рисующая модель не читает, и
# сорокапятилетняя выходила девушкой. Слова градации она знает, а приметы лет
# приходится называть прямо — иначе они не появляются
# Постоянный тег эпохи и сектора в начале строки: без него кадр сползал в
# сегодняшний день — бар выходил земным пабом, охотник вестерном. Проверено
# прогоном: тег держит жанр, а вот утяжеление манеры ломает кадр
SETTING_TAG = "far future frontier sector"
W_SETTING = 1.2

# Ключи по-английски и с годами: по русским ярлыкам модель мазала — «лет
# пятидесяти» попадало в «молодой»
AGE_BANDS = {
    "child": "child",
    "teenager": "teenaged",
    "twenties": "young adult in their twenties",
    "thirties": "in their thirties, first lines at the eyes",
    "forties": "middle-aged in their forties, lined face, greying hair",
    "fifties or sixties": "in their fifties, deeply lined weathered face, grey hair",
    "seventy or older": "elderly, heavily lined face, thin white hair, stooped",
    "unspecified": "",
}
ANCHORS = {"person": PERSON_ROLES, "object": OBJECT_FAMILIES, "place": PLACE_KINDS}
# слот, из которого код берёт ключ якоря, — по типу субъекта
ANCHOR_SLOT = {"person": "role", "object": "family", "place": "place_kind"}


# ── рамка, веса, манеры и негатив ──────────────────────────────────────────
# рамка кадра постоянна для своего типа — модели её больше не доверяем
FRAMING = {
    # план персонажа выбирает ГМ: лицо для жетона или снаряжение и силуэт целиком
    "person": ("medium shot", "face clearly visible"),
    "person:bust": ("close-up portrait", "face clearly visible"),
    "person:waist": ("medium shot", "waist up", "face clearly visible"),
    # лицо на ростовой дистанции занимает десятки пикселей и оплывает первым, поэтому
    # его читаемость приходится требовать отдельным тегом
    "person:full": ("full body character concept art", "head to feet",
                    "clearly defined facial features"),
    "object": ("three-quarter exterior view", "whole object in frame"),
    # мелкая вещь требует другой дистанции, иначе её съедает окружение
    # «product shot» и «depth of field» — слова фотостудии, на них кадр уходил
    # в фотографию: мелкую вещь держит крупный план и простой фон, не оптика
    "object:handheld": ("close-up study of one object", "dim plain background"),
    "object:vehicle": ("three-quarter exterior view", "whole craft in frame"),
    "object:structure": ("wide shot", "whole structure in frame"),
    "interior": ("wide establishing shot",),
    "landscape": ("wide establishing shot", "ground level"),
    "orbital": ("view from orbit", "full globe against black airless space"),
    "void": ("wide shot in open space", "black airless space on every side"),
}
# Манера — постоянная величина кампании, а не выбор модели. Но перевешивать субъект
# ей нельзя: с весом 1.4 стилевой тег оказывался сильнейшим в промпте и тянул кадр
# в жанровую картинку — вместо поясного портрета в майке выходил герой в броне во
# весь рост. Живописность держат негатив и хвост, а не вес
# Манера кампании — величина кампании, а не выбор модели. Варианты живут здесь,
# чтобы их можно было сравнить прогоном: ключ приходит запросом, по умолчанию
# базовый. Узнаваемых чернильных обводок и cel-shading нет намеренно — это
# подпись чужой игры
STYLES = {
    "concept": {
        "title": "концепт-арт (базовый)",
        "lead": "gritty sci-fi concept art",
        "tail": ("painterly digital painting",),
    },
}
# «Грязная кисть» (сухая кисть, зерно, приглушённая палитра) убрана: она уводила
# кадр в чёрно-белое. Если понадобится пыльная манера — задавать её цветом, а не
# ограничением палитры
STYLE_ORDER = ("concept",)
# Манера идёт первой в строке, как в кадрах, которые ГМ отметил удачными, и её
# вес зависит от типа кадра. У предмета отнимать внимание не у кого, и без веса
# выше субъекта борт выходил фотографией; у персонажа и локации тот же вес крал
# содержание — механик молодела, а колония превращалась в земную закусочную
# Вес имеет смысл только против невзвешенного окружения: когда взвешено почти всё,
# не взвешено ничто, а слова ГМа идут единицей под этой стеной. Вес остался на
# субъекте, якоре и манере — рамка, акцент, свет и нота держатся местом в строке
W_SUBJECT, W_ACCENT, W_LIGHT, W_STYLE, W_FRAME = 1.4, 1.0, 1.0, 1.2, 1.0
# Вес манеры по типу кадра: у персонажа тяжёлая манера уводила фигуру в жанровую
# картинку — механик выходила шагающим роботом; у локации и предмета отнимать
# внимание не у кого, и там она как раз даёт нужную рисовку
W_STYLE_OBJECT = 1.3
W_STYLE_PLACE = 1.25
# Якорь предмета должен перебивать приор этого мира и потому весит как субъект;
# у персонажа и локации субъект уже назван ролью или видом места, и такой же вес
# делал кадр типовым — архетип съедал приметы, которые описал ГМ
W_ANCHOR = 1.2
# нота сеттинга — единственный тег, отвечающий за «это фантастика»; без веса он
# терялся среди двадцати других и кадр читался историческим
W_NOTE = 1.0
# по схеме значение слота — фраза в 1-4 слова; пятое допускаем, дальше это проза
MAX_SLOT_WORDS = 5
# Окно CLIP — 77 токенов, около шестидесяти слов. Строка длиннее режется на куски,
# каждый кодируется отдельно, и всё после первого куска влияет на кадр слабо и
# размыто. Сборка прежде выдавала 130 слов, и слова ГМа лежали как раз в хвосте:
# кадр выходил «на тему». Отсюда потолки — на источник и на строку целиком
LIMITS = {
    "location": 2,
    "layers": 2,
    "face": 2,
    "subject_detail": 3,
    "attributes": 3,
    "materials": 1,
    "mood": 1,
    "env": 2,
    "register_tags": 2,
    "max_words": 62,
}



# Негатив делится на два свода. Безусловный — про качество и анатомию: он не
# подчиняется дедупу, потому что тот снимал тег по одному общему слову, а в позитиве
# всегда стоит «face clearly visible» — и вся защита лица улетала целиком.
# Условный — про содержание кадра: если ГМ попросил броню или парад, эти теги
# честно уступают его словам.
NEGATIVE_QUALITY = ("blurry, watermark, text, lowres, jpeg artifacts, 3d render, "
                    "videogame screenshot, photorealistic, dslr photo, airbrushed")
NEGATIVE_ANATOMY = {
    "person": ("bad anatomy, extra limbs, extra fingers, deformed hands, distorted face, "
               "exposed muscle and bone"),
    "object": "bad anatomy, extra limbs, deformed hands",
}
# только то, что несовместимо с самим типом кадра: в негативе не должно оказаться
# ничего, что ГМ может попросить в кадре этого типа
NEGATIVE_BY_SHOT = {
    # три приора, каждый ловился на прогоне: броня чужой франшизы поверх открытого
    # лица, парадный портрет позапрошлого века с земной формой, и общее
    # похорошение — сорокапятилетняя механик выходила молодой красавицей
    "person": ("mandalorian armour, t-visor helmet, stormtrooper armour, power armor, exosuit, "
               "19th century, naval dress uniform, present-day police uniform, "
               "peaked officer cap, gold braid, epaulettes, necktie, army fatigues, "
               "beautiful face, glamour portrait, flawless skin, makeup, hourglass figure, "
               "youthful face, teenager, young woman"),
    # «крупный план одного предмета» модель охотно понимает как лист ассетов
    # «корабль» чекпойнт понимает как морское судно и держит этот приор крепче
    # любой ноты: кадр борта выходил сухогрузом в сухом доке
    "object": ("asset sheet, grid of objects, item icons, "
               "sailing boat, ocean liner, drydock, harbour crane, sea water, waves, "
               "propeller and rudder, airliner fuselage, swept wings, jet fighter, tail fin, "
               "glass cockpit canopy, airport runway, streamlined spaceplane, chrome finish"),
    "interior": "sailing boat, ocean, waves",
    # наружный кадр чекпойнт охотно застраивает земной улицей: седаны у обочины,
    # асфальт, телеграфные столбы — в этом секторе их не бывает
    "landscape": ("sailing boat, ocean liner, harbour, automobile, sedan, pickup truck, "
                  "asphalt road, telephone pole, traffic sign"),
    "orbital": "landscape, horizon line, ground level, terrain, planet surface, foreground rocks",
    "void": "landscape, horizon line, ground level, terrain, planet surface, foreground rocks",
}
# Кадр сползает в сегодняшний день сам собой: чекпойнт знает эту одежду и эти
# помещения лучше всего, и без свода бар выходил закусочной, а мастерская —
# гаражом с улицы. Свод условный: назвал ГМ джинсы — джинсы и будут
# Манера с ограниченной палитрой и обводкой временами уводит кадр в серое: свод
# условный, поэтому чёрно-белое по замыслу ГМа он не тронет
NEGATIVE_MONOCHROME = "greyscale, monochrome, black and white, desaturated, colourless"
NEGATIVE_MUNDANE = ("present day, contemporary earth, modern city street, suburban house, "
                    "roadside diner, denim jeans, baseball cap, hoodie")
NEGATIVE_NO_PEOPLE = "person, figure, crowd, face, silhouette of a person"
# У CLIP окно 77 токенов: свод длиннее нескольких окон размывает вес каждого тега,
# и своды начинают мешать друг другу вместо того, чтобы работать. Хвост режется с
# условной стороны — безусловные своды короткие и стоят первыми
NEGATIVE_MAX_TAGS = 55
# Описанное лицо чекпойнт закрывает шлемом, стоит манере принести с собой своего
# героя в броне. Свод включается только там, где лицо и описано, и открыто: у
# субъекта в шлеме по словам ГМа он не применяется вовсе
# Простое «helmet» здесь необходимо: приор брони надевал шлем даже там, где ГМ
# написал, что шлем снят и висит у бедра. Свод срабатывает только при описанном
# лице, поэтому закрытая голова по замыслу ГМа им не задета
NEGATIVE_FACE_COVER = "helmet, visor down, face covering mask, gas mask, hidden face"
# план держится негативом: чекпойнт сам тянет персонажа в героя во весь рост,
# а в полном росте — обрезает по пояс
NEGATIVE_BY_PLAN = {
    "bust": "full body, full length portrait, waist up, legs visible, standing figure",
    "waist": "full body, full length portrait, legs visible, feet visible, standing figure",
    "full": "close-up portrait, head and shoulders, cropped legs, cropped at the waist",
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
KIT_SECTIONS = ("heads", "common_law", "plans", "registers", "slot_rules", "anchors", "ages", "setting_tag",
                "framing", "weights", "limits", "styles", "negatives")


def default_kit() -> dict:
    return {
        "heads": {k: HEADS[k] for k in KINDS},
        "common_law": COMMON_LAW,
        "slot_rules": SLOT_RULES,
        "plans": {k: {"title": v["title"], "law": v["law"]} for k, v in PLANS.items()},
        "registers": {k: {"title": v["title"], "vocab": v["vocab"],
                          "tags": list(v.get("tags", ())),
                          "negative": v.get("negative", ""),
                          "env_in": list(v.get("env_in", ())),
                          "env_out": list(v.get("env_out", ())),
                          "tags_person": list(v.get("tags_person", ()))}
                      for k, v in REGISTERS.items()},
        "anchors": {k: dict(v) for k, v in ANCHORS.items()},
        "ages": dict(AGE_BANDS),
        "setting_tag": SETTING_TAG,
        "framing": {k: list(v) for k, v in FRAMING.items()},
        "limits": dict(LIMITS),
        "weights": {"subject": W_SUBJECT, "accent": W_ACCENT, "frame": W_FRAME,
                    "light": W_LIGHT, "note": W_NOTE, "style": W_STYLE,
                    "style_object": W_STYLE_OBJECT, "style_place": W_STYLE_PLACE,
                    "anchor": W_ANCHOR,
                    "setting": W_SETTING,
                    "max_slot_words": MAX_SLOT_WORDS},
        "styles": {k: dict(title=v["title"], lead=v["lead"], tail=list(v["tail"]))
                   for k, v in STYLES.items()},
        "negatives": {"quality": NEGATIVE_QUALITY,
                      "anatomy": dict(NEGATIVE_ANATOMY),
                      "by_shot": dict(NEGATIVE_BY_SHOT),
                      "by_plan": dict(NEGATIVE_BY_PLAN),
                      "mundane": NEGATIVE_MUNDANE,
                      "colour": NEGATIVE_MONOCHROME,
                      "no_people": NEGATIVE_NO_PEOPLE,
                      "face_cover": NEGATIVE_FACE_COVER},
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
