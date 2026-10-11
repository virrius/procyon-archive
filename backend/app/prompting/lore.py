"""Лор кампании для рисующей модели — то, что не зависит от чекпойнта.

Здесь живёт всё, что описывает мир и работу с описанием ГМа: закон сеттинга,
головы направлений, законы подтипов кадра, визуальные регистры, якоря
архетипов, возрастные полосы и подмены земных слов. Сборка строки промпта —
дело рендерера (zimage.py).
"""
from __future__ import annotations

import re

from ..i18n import twin_lang

# английский экземпляр: инструкции рисующей стороне и так английские, меняется
# только то, что видит ГМ, и оговорка о русском описании
EN = twin_lang(__name__) == "en"

KINDS = ("person", "frame", "action")
# подтип кадра выбирает ГМ: раньше вид съёмки и масштаб классифицировала модель
# и путалась — станция выходила кораблём, работа снаружи рисовалась внутри
VIEWS = ("ship", "handheld", "structure", "planet", "landscape", "interior")
VIEW_ORDER = VIEWS
# где происходит экшн — единственная классификация, оставленная модели в этом
# направлении: она проста, а тащить её в UI — лишняя кнопка
ARENAS = ("interior", "outdoor", "void")
# пункт «ничего из списка» в закрытых перечнях ролей и якорей: якоря не даёт, а ГМ видит его в ките
OTHER = "other" if EN else "прочее"

# ── общий закон сеттинга ─────────────────────────────────────────────────────
COMMON_LAW = """
WHERE AND WHEN THIS HAPPENS. Every frame belongs to one setting and you fill the schema from it. The far future, twelve centuries after an alliance of worlds ended an age of war, in a frontier sector too distant from the core for that alliance to be felt. Star travel is routine and shabby: hyperspace lanes, jump gates, ships patched by their crews for generations. Nothing here is new — metal welded, riveted, scavenged and repainted, cables where a wall should be, readouts glowing in rooms never designed for them. Humans and xenos work side by side; power belongs to pirate queens, crime bosses, trade guilds and corporations, not to governments. What is clean, seamless and evenly lit belongs to guilds and to the powerful, and that cleanliness is itself a statement. The planets carry ruins of a civilisation that predates all of it: black glassy material incised with dense geometric patterns, without seam or joint, hung about with the scaffolding and instruments of people who did not build it. Secret cults revere those ruins and carry relics out of them — hooded figures in dark cloth over technical harness, cult signs cut into metal, fragments of that ancient material wired into improvised mechanisms, and those the relics have already changed, whose eyes and veins are lit from within.

So there are things that cannot appear in a frame here, however the GM phrased it: no historical or period dress, no pre-industrial world, no present-day street, no flags or insignia of real countries, no polished utopia. When their words are era-neutral, the setting decides the era, and it decides this one.

FOLLOW THE GM LITERALLY. Every slot comes from their text. Never invent ethnicity or age, never upgrade what they described, never fill an empty frame. Fill in nothing they did not name: your job is their sentence, made drawable.

WRITE WHAT IS SEEN, NOT WHAT IT IS CALLED. The image model has never heard of this galaxy: a proper noun draws nothing, so names of people, ships, worlds, guilds and makers are replaced by form and material. If a stranger reading your slots would still ask what the thing looks like, it is a name in disguise.

NAME THE CUT, NOT THE PURPOSE. This is the one slot rule the whole setting rests on: what the person wears, and how a thing is put together, is the only channel that carries this world into the picture. Words that name a purpose — uniform, suit, jacket, armour, cockpit, office, hospital — carry their earthly object whole, and the drawing model answers them with a photograph of our own century: a business suit in a glass meeting room, a camouflage flight suit, a hospital corridor. Write the cut, the seams and the material instead, and let the purpose be read off the shape. What the eye would report about this particular garment: what it is made of and how that material is finished, where it closes and by what, how far it falls, which way its seams run, how the sleeve meets the shoulder, what the collar does, what is fastened where. Write it in your own words for the garment in front of you — a phrase carried over from this instruction dresses every character in the same clothes, and the drawing model repeats it exactly. Never leave the wear slot vague — "worn jacket" is the same as writing nothing.

NUMBERS AND SIDES DO NOT SURVIVE THE DRAWING. The image model cannot count and does not know left from right. Write the impression instead — patched in several places, a handful of figures, one sleeve cut short — and never write left or right at all.

ONE WORD IS BANNED OUTRIGHT. The drawing model answers the words alien, extraterrestrial and ufo with a bald grey head and big black eyes, and that head then overrides everything else in the frame. None of them appears in any slot, in any form, for any subject — not for a creature, not for a place, not for a thing. A non-human person is named by its own kind and body, and the word of this setting for such people is xenos — but only for somebody the GM actually made non-human: written into a frame where they named nobody of the kind, it is an invention like any other. A thing of no human make is named by its shape, its material and what is wrong with it: a seamless black glass wedge, a knot of metal with no join. A sky of another world is named by its colour and its weather.

WRITE THE POSITIVE FORM. The model cannot subtract: the words no, not, without and never do not appear in a slot, nor a comparison built on them. Write only what is there; keeping things out of frame is the pipeline's job.

English only, no prose in the tag slots, no explanation."""

# ── разметка слотов по направлению ──────────────────────────────────────────
SLOT_RULES_PERSON = """

WHAT YOU WRITE IS THE PICTURE. The slots go to the drawing model word for word. Anything the GM named that you leave out will not be in the frame. Every slot value is a lowercase English phrase, no comma inside it: one to four words for a plain thing, up to eight when a cut needs them. The model reads the whole list and dilutes nothing, so an unwritten detail is the only detail that is lost.

brief — two or three plain sentences describing the whole frame to yourself before the slots: who this is, what they wear and carry, where they stand. Written first so the slots come from a considered picture; it is not sent to the drawing model.
role — the trade or standing this person lives by, picked from the fixed list after the brief is written. The nearest entry wins even when their title differs; прочее only when nothing on the list is anywhere close. The pipeline turns it into an anchor that keeps the checkpoint from drawing our own century, so a wrong pick dresses them in the wrong life.
subject — 2-4 words: role plus sex, and the build if the GM gave one. When the character is not human, the word for their kind draws nothing on its own — write the body instead: how many limbs, what the head and the skin are like, what is plainly not human. The name of the kind may stand beside that, never in place of it. When the body has more limbs than a human one, say what each pair is doing — the drawing model grows the extra pair out of the shoulders as a stump unless every pair has work of its own.
age — pick the band that holds the years the GM gave; their words about face and hair decide when there is no number. When they said nothing at all, pick the band the trade and standing imply — years of a craft, a rank, a command, a debt all take time to acquire. Unspecified is the last resort and it costs the frame: the pipeline then writes no age at all, and the drawing model answers with the unlined face of a catalogue model, whatever the person does for a living.
face — 2-3 phrases: the face and gaze, and what marks it — scars, implants, hair, the state of the skin. Smooth, unlined, flawless skin is not a description but the absence of one, and the drawing model answers it with the face of a catalogue model: write what the years and the work left on this face instead, and never contradict the age band you picked.
build — 1 phrase: posture and body as described. Never make a body fitter, younger or more heroic than written: fat, gaunt, stooped, ageing and scarred all survive exactly as given.
pose — 1 phrase naming a movement, not a stance: what the hands are doing with something already named in the other slots, or how the body is turned, bent, leaning, crouching, reaching or walking. Take it from the GM's text when they said what the person was doing; when they did not, use an ordinary working movement of this trade — nothing dramatic, no second person, no new object. Any phrase whose verb is only "standing" fails this slot, and "standing with the weight on one leg" fails it too: that is the catalogue photograph this slot exists to prevent. When the body has a pair of limbs a human body does not, this slot is where they are counted and each pair is given its own work, in as few words as the count allows: this phrase stands first in the drawn description, and a pair named anywhere later does not grow at all.
wear — 4-6 phrases, and this is the slot the whole setting rests on: the garments they named, each built the way a tailor would say it — the material, how much it weighs and how it hangs, and its finish, the closure and where it sits, the seams and their direction, how the sleeve meets the shoulder, the collar, the fastenings. When the GM named two garments, the cut of those two fills the four phrases; you are not inventing clothes, you are writing down how the named ones are made. A garment named by its purpose is a wasted phrase, and three words are the worst of them: suit, dress and outfit. Each one hands the drawing model a whole outfit of our own century — a jacket over a knee-length skirt, court shoes, a tailored two-piece — however cleanly the rest of the slot is written. Write instead what one garment is and how far it falls: a single closed piece to the ankle, a coat to mid-calf, a fitted over-layer to the hip. Length and closure are what carry the cut; without them the model falls back on office clothing. When the GM's own word for a material or trim names something historical or period (brocade, lace, corsetry, tricorne and the like), the common law still governs: keep the cut, the richness, the silhouette they described, but write the material and trim in period-neutral words — a heavy metallic-shot fabric, worked trim, structured layering — never the historical fabric name itself.
gear — 2-3 phrases: what is worn on top, carried or fitted; only what they named. Name the thing, never where it sits: placement does not survive the drawing.
location — 2-3 phrases: the kind of place and what it is made of, taken from the corner of the world described above. When the GM said nothing about where this is, the place is yours to invent, but it is specific and it belongs to this person's working life. A blank backdrop, a plain wall, an empty room or a bare floor is a failed slot: that is a product photo, not a scene.
place_object — 1 phrase: one thing with a shape of its own standing in that place beside the figure, close enough to share the light. A surface, a wall or a floor is not such a thing. It is what makes the place a scene the figure is inside of rather than a background they are pasted on.
tech_marker — 1 phrase: the one thing in this frame that could only exist in a spacefaring century, worn by them or fitted to what they stand in. It is not decoration and not a weapon by default: it is the working technology of their trade, named as a shape and a material rather than by its function. Without it a frame of plain clothes in a plain room reads as our own century in costume, which is the single most common way these images fail.
depth — 1 phrase: what the eye reaches furthest away past the figure — the far end of the place, what opens or closes it off. This is the layer that stops the frame from ending at a wall behind their shoulders.
light — 1 phrase: the source and the direction it falls from. Light with no direction — even, ambient, diffuse, overall — flattens the frame into a product photograph, and that happens most often in the clean corners of this world, where every surface is smooth. Even there the light comes from somewhere: name that somewhere and which way it rakes across the room."""

SLOT_RULES_FRAME = """

WHAT YOU WRITE IS THE PICTURE. The slots go to the drawing model word for word. Anything the GM named that you leave out will not be in the frame. Every slot value is a lowercase English phrase, no comma inside it: one to four words for a plain thing, up to eight when the build of it needs them. The model reads the whole list and dilutes nothing, so an unwritten detail is the only detail that is lost.

brief — two or three plain sentences describing the whole frame to yourself before the slots: what this is, what shape and material it has, what surrounds it. Written first so the slots come from a considered picture; it is not sent to the drawing model.
anchor — the class of the thing or place, picked from the fixed list after the brief is written. The nearest entry wins even when the GM's word differs; прочее only when nothing on the list is anywhere close. The pipeline turns it into an anchor that keeps the checkpoint from drawing a sea vessel, an aeroplane or an earthly room, so a wrong pick redraws the frame as the wrong thing.
subject — 2-4 words: what the frame is of. For a craft or a structure say outright that it belongs to space — starship, orbital hauler, void station — a bare ship, boat, plane draws the earthly thing and nothing later pulls the frame back.
form — 3-5 phrases: the shape and the parts, in the order a silhouette is read — the mass first, then what sits on it, then the openings. For a place: what the space is built of, first of all its material. Here form does for a thing what wear does for a person: it is the only slot the setting travels through, so write how it is put together, not what it is for. The material and the finish come from the register whenever the GM left them open: a hull, a room or a hall is not welded plate by default, it is whatever the register says it is.
marks — 2-3 phrases: wear, damage, repairs, paint — the register's texture on the named thing.
tech_marker — 1 phrase: the one thing in this frame that could only exist in a spacefaring century — the working technology of the place, named as a shape and a material rather than by its function. Without it the frame reads as an earthly workshop, yard or street, which is the single most common way these images fail.
surround — 2-3 phrases: what stands near and what closes the far distance. Figures the GM put in the place live here, as part of the scene, never as portraits.
light — 1 phrase: the source and how it falls.
no_people — true only when the frame must contain nobody at all."""

SLOT_RULES_ACTION = """

WHAT YOU WRITE IS THE PICTURE. The slots go to the drawing model word for word. Anything the GM named that you leave out will not be in the frame. Every slot value is a lowercase English phrase, no comma inside it. The model reads the whole list and dilutes nothing, so an unwritten detail is the only detail that is lost — but the action itself is written first.

Slot values here run up to eight words: an actor needs a verb.

brief — two or three plain sentences describing the whole moment to yourself before the slots: who does what, to whom, where, what the violence or motion looks like frozen in one frame. Written first so the slots come from a considered picture; it is not sent to the drawing model.
arena — where the moment happens, picked after the brief: interior when walls and a ceiling hold the frame, outdoor on the surface of a world, void in open space.
action — 2-5 words naming the act itself as one drawable moment: two men grappling, a firefight across crates, a speeder run through dust. This is the subject of the picture; the verb must survive into it.
actors — 2-4 phrases, one per participant or group: who they are and what each is doing right now — leaning out firing, pinned against the counter, hanging off the running board. Mid-motion, never standing. Every phrase carries a verb: a phrase about clothing, gear or a body part is not an actor and belongs in another slot, however loudly the register speaks. When the GM named a group and left its members unsaid, that group is one actor written as a group; a participant nobody asked for is invention, and the count of phrases is never a reason to add one.
crew — 1-2 phrases: what the people in the frame are wearing and carrying, written as cut and material for the whole group at once, not per person. This slot exists because the actors slot carries only motion, and a figure whose clothing is never written is dressed by the drawing model out of our own century: helmet, plate carrier, assault rifle, the same squad in every frame. The same law as the wear slot governs it — the cut, the closure, how far it falls, what the material is — and the same words are banned: suit, uniform, tactical, armour, gear. When the GM said what they wore, that is what goes here; when they did not, this is the working dress of the trade the frame is about.
place — 2-4 words: the kind of place it happens in and its material.
place_detail — 2-3 phrases: what of the place is in the shot — the cover, the furniture, the vehicles, the debris of the fight.
effects — 2-3 phrases: the visible traces of the action the GM named — muzzle flash, steam jet, dust wake, swinging lamp. Only what follows from their text.
light — 1 phrase: the source and how it falls."""

# ── головы по направлению ────────────────────────────────────────────────────
HEAD_PERSON = """You turn a GM's short description of a PERSON (often Russian) into slots for a drawing model.

The subject is somebody: human, xeno, or a machine that works alongside people. Extra limbs, scales, fur, a chassis instead of skin change nothing — except that a subject with no face at all takes the role machine, and then the frame is built around the whole unit instead of a face. Wear and face slots then describe the casing and what is mounted where a face would be.

The framing is fixed for you: the figure in frame with the face readable. Stance, silhouette and what hangs from the belt matter as much as the face, and everything the GM named is drawn whole rather than cropped.

GEAR IS LITERAL. The GM may describe a thing by comparison. Write the object plainly and let their comparison set its size and material."""

HEAD_FRAME = """You turn a GM's short description of a SHOT (often Russian) into slots for a drawing model. The shot is a thing or a place: a ship, a device, a station, a planet, a stretch of ground, a room. The GM has already chosen which, and the camera is fixed for you — you fill in what is in the frame.

{view}

NAME THE CLASS SO IT CANNOT BE READ AS EARTHLY. Some words name a thing of our world first: ship, boat, freighter, plane, port, dock. Written plainly they draw that thing — a hull in a drydock instead of a hauler resting on its landing gear. Nothing here flies through air or sails a sea, so the words for our aircraft and vessels never appear: no nose, fuselage, cockpit, wings, tail, bow, deck. Never write "legs" or "on legs" for a craft's stance — the drawing model reads it as an animal's limbs.

DECIDE THE STANCE FROM THE GM'S TEXT. If nothing in the brief puts the craft in motion, it is parked or docked — write it in the opening words with this exact phrase: "grounded on its extended landing gear". If the brief has it flying, chasing, fighting or under fire, it is in flight — write the opening words as the craft in motion instead: banking, thrusting, weapons firing, engines lit, with open space or sky around it, and never mention landing gear or a ground surface at all. Everything else about the hull's shape — bulk, panels, wings, silhouette — comes only from what the GM described, never from a fixed example.

KEEP THEIR FRAME. Everything they named goes in; nothing they did not name gets added. You choose only the depth layers, the light and the material wear. If the GM put people or crowds in the place, they belong in the shot through dress, posture and silhouette — part of the scene, never portraits. If they described an empty place, leave it empty and mark no_people."""

HEAD_ACTION = """You turn a GM's short description of an ACTION SCENE (often Russian) into slots for a drawing model. Somebody is doing something to somebody, and the picture is that moment frozen — a brawl, a firefight, a chase, a boarding, a ritual at its peak.

THE VERB IS THE SUBJECT. The image model happily draws the room and forgets the fight, so the act itself is named first and weighted by the pipeline. Every actor is written mid-motion: leaning, swinging, firing, falling. A figure with nothing to do in the sentence will stand and pose in the picture.

Choose the arena: interior when walls and a ceiling hold the frame, outdoor on the surface of a world, void in open space.

GEAR IS LITERAL. The GM may describe a thing by comparison. Write the object plainly and let their comparison set its size and material."""

if EN:
    HEAD_PERSON, HEAD_FRAME, HEAD_ACTION = (
        h.replace(" (often Russian)", "", 1) for h in (HEAD_PERSON, HEAD_FRAME, HEAD_ACTION))
    SLOT_RULES_PERSON = SLOT_RULES_PERSON.replace("прочее", OTHER)
    SLOT_RULES_FRAME = SLOT_RULES_FRAME.replace("прочее", OTHER)

HEADS = {"person": HEAD_PERSON, "frame": HEAD_FRAME, "action": HEAD_ACTION}
SLOT_RULES = {"person": SLOT_RULES_PERSON, "frame": SLOT_RULES_FRAME,
              "action": SLOT_RULES_ACTION}

# ── подтипы кадра ────────────────────────────────────────────────────────────
# Закон подтипа подставляется в голову кадра: камера и дистанция заданы выбором
# ГМа, модели остаётся содержание. Тексты короткие: рамку несут теги из FRAMING
VIEW_LAWS = {
    "ship": ("The thing is a craft or a vehicle, whole in frame, three-quarter view. "
             "Open form with its stance and mass — what it rests on, what shape the "
             "hull mass is — before any fitting."),
    "handheld": ("The thing fits in hands and fills the frame alone against a plain "
                 "dim background. Open form with what it is and its material; its "
                 "size is carried by materials and wear, never by a person. A thing "
                 "of no human make is carried by its shape and its material: name "
                 "what is strange about them in plain words."),
    "structure": ("The thing is a station, a gate, a hulk — a structure in open "
                  "space. Nothing holds it up and nothing stands under it; black "
                  "airless space on every side."),
    "planet": ("The frame is a whole planet, moon or world seen from space, not a "
               "place on it. Give it terrain, weather bands, city glow on the night "
               "side; one planet in frame. The whole sphere is the subject: anything built "
               "on it is a few specks of light seen from far above. Open with what kind of "
               "body it is and the colour and material of its whole surface, and name the "
               "moon or planet of our own solar system with the same colours; never Earth. "
               "Ice, frost and snow are white and grey; blue is only water, gas or what "
               "the GM called blue. The whole disc reads as one pattern from edge to edge "
               "(cloud cover, bands, cracks, dunes, craters), never patches of land among "
               "water unless the GM gave seas; write what is there, not what it lacks. The words landscape, horizon, ground and sky never appear."),
    "landscape": ("The camera stands in the open air on the surface of a world, "
                  "ground under it and sky over it. A structure filling the frame "
                  "does not make this an interior — only walls around the camera do."),
    "interior": ("The camera stands inside an enclosed space and walls or a ceiling "
                 "hold the frame: a corridor, a hold, a bar, a cave."),
}
VIEW_TITLES = {
    "ship": "корабль / техника",
    "handheld": "предмет крупно",
    "structure": "структура в пустоте",
    "planet": "планета с орбиты",
    "landscape": "место на поверхности",
    "interior": "интерьер",
}
if EN:
    VIEW_TITLES = {
        "ship": "ship / vehicle",
        "handheld": "object up close",
        "structure": "structure in the void",
        "planet": "planet from orbit",
        "landscape": "place on the surface",
        "interior": "interior",
    }

# ── визуальные регистры ──────────────────────────────────────────────────────
# vocab уходит в инструкцию, tags код дописывает в промпт сам. tags_person —
# отдельный набор для живого субъекта: теги корпуса и панелей, дописанные к
# существу, превращали механика в робота, а не в существо среди механики
REGISTERS: dict[str, dict] = {
    "derelict": {
        "title": "заброшка",
        # одежда регистра — только для живого субъекта: на вещи «швы и перчатки»
        # уезжали в приметы предмета
        "vocab_person": ("whoever the GM named came into this place from outside and is dressed "
                         "for it: a sealed working garment closed to the throat, patched at the "
                         "knees and elbows where it goes down on them, a harness of straps over "
                         "it carrying what must stay to hand, a lamp clipped at the chest, "
                         "breathing gear hanging at the neck, heavy gloves and boots, and the "
                         "dust of the place worked into every fold"),
        # Не постапокалипсис и не руины Предтеч: это человеческое, брошенное
        # недавно по меркам мира и с тех пор не чиненное
        "vocab": ("nothing here has been kept up for decades and the frame says so first of "
                  "all: panels hang from a single remaining fastening, cable looms pulled out of "
                  "their trunking and left swinging, floors under fallen ceiling plate, debris and "
                  "drifted grit, hatches jammed part open, whatever was worth taking already cut out "
                  "and carried off, the sockets it left standing empty. Corrosion is the first thing "
                  "the eye meets: metal rusted and scaling, rust running down in streaks and stains, "
                  "paint blistered and peeling away in sheets. Beside it each place has its own mix "
                  "of slower damage: dust laid thick over everything horizontal, damp grime where "
                  "water collected, scorch marks, cracked and clouded plastics, dead screens and "
                  "consoles gone dark. Light is what still leaks in — one failing source, a "
                  "beam through a breach, a hand lamp — and the rest of the frame keeps its dark. "
                  "Whatever the GM named is described in this state and by how it was made, and "
                  "the emptiness is itself part of the picture"),
        "tags": ("long abandoned interior", "dust and frost over dead consoles",
                 "light leaking through a breach"),
        "tags_person": ("gear patched against the cold", "hand lamp strapped on",
                        "dust ground into every seam"),
        "vocab_ship": ("whatever hull the GM named has been picked over by everyone who passed "
                      "through it since it died: access panels missing where someone needed the "
                      "plate elsewhere, conduit runs cut and left dangling, thruster bells "
                      "scorched and cold, viewports starred or blown out, drive systems dark with "
                      "only battery light holding in a compartment or two. The structure that "
                      "remains is honest about how it was built — ribs and spars showing where "
                      "skin has been stripped away — and nothing has been kept level or square "
                      "since"),
        "tags_ship": ("stripped hull with skin torn away", "dead scorched thrusters",
                     "structure showing through missing plate"),
        "negative": "pristine surfaces, showroom finish, fresh paint, tidy shelving",
    },
    "junk": {
        # Бывший фронтир: латаное железо, лом и ржавчина ушли сюда, чтобы
        # обычный рабочий космос перестал быть свалкой по умолчанию
        "title": "свалка",
        "vocab_person": ("clothing here is coarse fabric and hide worn soft and layered one "
                         "over another: a long outer garment open down the front, a closed work "
                         "garment under it with the sleeves pushed back, stitched patches where "
                         "it wore through, straps and buckles instead of fastenings, a belt "
                         "carrying tools and a holster, cuffs turned back, boots resoled more "
                         "than once, and grease and dust in every seam"),
        "vocab": ("this is where broken things end up and people live off them: heaps and "
                  "stacks of scrap, hulks cut open for parts, rust bleeding over every surface, "
                  "shacks, stalls and walkways bolted together from salvaged sheet and crate panel. "
                  "Everything that still works is kept running by the hands that use it: "
                  "manufactured plate and machined edges where the thing came from a yard, and "
                  "salvaged sheet, crate panel and hand-cut lettering everywhere it was mended "
                  "since; cable strung and clipped along the surfaces it feeds, straps and buckles "
                  "doing the work of fastenings, readouts glowing in places never designed for "
                  "them. People make it warm the only way they can: cloth hung over bare metal, "
                  "mismatched seats, strings of lamps, bottles and tools left where they are used, "
                  "grease and dust worked into every seam. Clothing is coarse fabric and hide worn "
                  "soft, layered, stitched and patched, cut for work and shaped by the body in it. "
                  "Light is harsh sun through drifting dust, or fires in drums, work lamps and the "
                  "spark of a cutting torch at night"),
        "tags": ("salvaged plate and crate panel", "cable strung along the surfaces",
                 "warm pooled lamp light"),
        # «stitched patches» модель рисует буквальными декоративными крестиками
        # на ткани — комикс-заплатка, а не потёртость; «mended» того не делает
        "tags_person": ("coarse fabric worn soft", "mended fabric, worn straps",
                        "grease worked into the seams"),
        "vocab_ship": ("whatever hull the GM named was built to be fixed by the people who fly "
                      "it, not by a yard: a manufactured frame under a skin of salvaged and "
                      "mismatched plate, patch welds and rivet rows where a hole was closed in a "
                      "hurry, hand-lettered hull numbers, thruster bells scorched and pitted from "
                      "use, conduit and cable run externally and clamped rather than concealed, a "
                      "boarding ramp or ladder welded on wherever it was needed. Nothing matches "
                      "anything else, and every mismatch marks a repair that kept it flying"),
        "tags_ship": ("mismatched patch plate and rivet rows", "scorched pitted thruster bells",
                     "externally clamped conduit"),
    },
    "frontier": {
        # Обжитой космос — люди здесь живут и сделали угол своим. Словарь —
        # качества, а не опись: перечисленные шлюзы, лифты и трафареты хаб
        # переносил в любое место, и кантина выходила ангаром
        "title": "обжитой космос",
        "vocab_person": ("clothing here is practical working gear made to last: a short jacket "
                         "or vest over a work shirt, utility trousers tucked into boots, belts, "
                         "a holster, pouches, a scarf or goggles against dust; creased and "
                         "scuffed with use, colours faded but whole, a crew or ship mark on "
                         "the shoulder"),
        "vocab": ("this is the ordinary lived-in space of the sector, where people work and live and "
                  "have made their corner their own. It is built to the design of the far future, not "
                  "to an earlier century's idea of the future: functional forms with crisp edges and "
                  "clear panel lines, matte composite and brushed alloy in a neutral base of warm grey "
                  "and graphite, technical fabric and worn upholstery, fittings made to be serviced, "
                  "light built into the structure as strips and panels. Colour comes as warm accents "
                  "of rust red, ochre and warm light on fabric, markings and wherever people gather, "
                  "never as an all-over cast. Everything is used every day and looked after: edges "
                  "polished by hands, scuffs where things are moved, fabric creased, repairs made "
                  "properly; visibly worn, never dirty or broken. People live here and it shows: their own "
                  "belongings, something green growing, things left where they were last used, a "
                  "little clutter. It is full of life: people of many kinds at their business, things "
                  "in use. Light is mixed: even light built into the structure, with warm pools where "
                  "people sit and work. Whatever the GM named looks used and lived in"),
        "tags": ("painted plate scuffed by use", "stencilled numbers and hazard stripes",
                 "busy working bay"),
        "tags_person": ("practical working gear", "scuffed boots and belts",
                        "faded crew mark"),
        "vocab_ship": ("whatever hull the GM named is a working ship flown hard and looked after "
                      "by its crew: painted plate in a livery they keep up, stencilled numbers, "
                      "clear panel lines and access hatches, thruster bells scorched from use; "
                      "everything fits and nothing is falling off"),
        "tags_ship": ("faded livery with hazard stripes", "scorched thruster bells",
                     "panel lines and access hatches"),
        "negative": "rust, scrap heaps, rotting metal, medieval, rustic timber",
    },
    "hightech": {
        "title": "хай-тек",
        "vocab_person": ("clothing here is cut precisely and kept immaculate: a long closed "
                         "garment fastening off to one side with the seam concealed, a standing "
                         "collar at the throat, shoulders shaped by the cut rather than by "
                         "padding, fabric heavy enough to hold its line, restrained geometric "
                         "marks at cuff and collar, thin gloves, and shoes that show no wear. Length is what carries "
                         "the cut: the garment falls to the calf or to the ankle, and a short jacket "
                         "worn over trousers is the two-piece of our own century, which this corner of "
                         "the world does not wear"),
        # Регистр — качества, а не гардероб: перечисленная здесь одежда уезжала в
        # слоты дословно, и любой персонаж хай-тека выходил техником в скафандре
        "vocab": ("things here are designed and machined rather than assembled and mended: "
                  "continuous curves and tapered masses, composite and light alloy in large "
                  "pieces with the joins hidden, seamless welds, surfaces finished so evenly that "
                  "the making leaves nothing to read. What the mechanism does is shown rather than exposed: recessed "
                  "readouts, hardlight planes standing in the air, edges that carry their own "
                  "light; nothing hangs loose and nothing is strung across anything. Lighting is "
                  "built into the structure, even and free of glare, and the floors give it back. "
                  "Whatever the GM named is cut precisely and kept immaculate: fabric that holds "
                  "its press, sealed seams, stand collars, restrained geometric marks, fine "
                  "materials worked without a flaw. Wear exists only where the powerful never look"),
        "tags": ("continuous composite curves", "hidden joins and seamless welds",
                 "even glare-free light"),
        "tags_person": ("precisely cut immaculate clothing", "sealed seams and stand collar",
                        "restrained geometric marks"),
        "vocab_ship": ("whatever hull the GM named is machined as one continuous form, not built "
                      "up from parts: sharp swept planes and tapered masses meeting at a hard "
                      "edge rather than a seam, composite skin with no rivet or plate line to "
                      "read, control surfaces and intakes cut clean into the hull rather than "
                      "bolted on, running lights set flush and edge-lit, thrusters recessed into "
                      "the airframe rather than hung off it. Nothing is patched and nothing "
                      "improvised — the hull looks machined to a tolerance a hand could never "
                      "hold, and its aggression is in the geometry, not in wear"),
        "tags_ship": ("continuous machined hull with hard sharp edges",
                     "flush recessed thrusters", "edge-lit running lights"),
        "negative": ("steampunk, brass and rivets, medieval, rustic timber, present day street, "
                     "roadside billboard, patched clothing"),
    },
    "hegemony": {
        # Власть Гегемонии и её домов: порядок, ранги, масштаб. Хай-тек — это
        # гильдии и корпорации, светлое и вылизанное; здесь тёмное и давящее
        "title": "гегемония",
        "vocab_person": ("clothing here is the dress of rank: a dark tailored long coat closed "
                         "high with a stiff standing collar, rank marks of worked metal at the "
                         "collar and shoulder, a sash or cord of house colour, polished boots and "
                         "black gloves; soldiers wear dark grey plated armour with a closed "
                         "helmet"),
        "vocab": ("this is the order of the Hegemony and its houses: halls, decks and plazas "
                  "built to make a person small, hard straight lines and identical elements "
                  "repeated in long ranks, dark grey and black alloy polished smooth, tall "
                  "narrow banners and heraldic house marks, personnel standing in formation, "
                  "everything aligned and symmetrical. Nothing is patched and nothing is "
                  "personal. Light is cold and directional: strips of white light along edges, "
                  "red accent lights, deep shadow between the ranks"),
        "tags": ("monumental symmetrical hall", "dark polished alloy",
                 "heraldic banners in long ranks"),
        "tags_person": ("dark tailored long coat with standing collar", "rank marks of worked metal",
                        "polished boots"),
        "vocab_ship": ("whatever hull the GM named is a warship of the order: a long angular "
                      "wedge of dark grey armour plate, regular rows of gun emplacements and "
                      "hangar mouths, house marks painted large, running lights cold white and "
                      "red; vast, symmetrical and menacing"),
        "tags_ship": ("angular dark grey armoured wedge", "rows of gun emplacements",
                     "large painted house mark"),
        "negative": "rust, patched clothing, clutter, warm cosy light",
    },
    "luxe": {
        # Богатая жизнь — не хай-тек: техники тут не больше, её просто прячут в
        # обстановку. Роскошь далёкого будущего — простор, свет и форма, которую не
        # сделать руками; тяжёлые ткани и золото давали ретро-салон
        "title": "богатая жизнь",
        "vocab": ("everything here was chosen rather than issued, and wealth shows as space, light "
                  "and making no ordinary hand could manage: vast quiet rooms of sweeping sculptural "
                  "curves, walls and floors of polished mineral and of stone that glows softly from "
                  "within, liquid-smooth metal in pale gold and rose, translucent and iridescent "
                  "surfaces, furniture shaped as one flowing piece standing apart from the walls. "
                  "Living gardens and still water are kept indoors at great expense, and a whole wall "
                  "opens in clear glass onto a spectacular view. The technology is everywhere and "
                  "hidden: light rising from within the structure and from under lifted edges, a "
                  "readout surfacing in a stone face and gone again, art and ornament that float or "
                  "turn slowly in the air. Wood, panelling, buttoned hide and turned legs belong to "
                  "another world and never appear here. Light is warm, soft and layered, and surfaces "
                  "give it back. Nothing is patched or worn, and nothing is sterile either — this is "
                  "serene comfort on the scale of a palace"),
        "vocab_person": ("clothing here is made for one body out of costly material: a long "
                         "garment falling in heavy folds, structured shoulders, a fitted "
                         "under-garment closed high, embroidery or inlaid thread following the "
                         "seams, fastenings worked as ornament in warm metal, rings and worked "
                         "pieces of unusual material at the hand and throat, fabric that catches "
                         "the light differently as it moves"),
        "tags": ("figured veneer and warm metal", "heavy draped fabric",
                 "many small warm light sources"),
        "tags_person": ("costly heavy fabric in deep folds", "ornament worked into the fastenings",
                        "worked metal at throat and hand"),
        "vocab_ship": ("whatever hull the GM named is finished like a piece of furniture, not a "
                      "working machine: deep lacquered panels or brushed precious metal laid over "
                      "the structural hull, a hand-painted or inlaid livery rather than a "
                      "stencilled registry, viewports framed in worked metal, running lights warm "
                      "rather than clinical, boarding stairs that fold out rather than a bare "
                      "ramp. The hull shows no working wear at all — this is a possession kept, "
                      "not a tool used"),
        "tags_ship": ("lacquered panels and inlaid livery", "worked metal viewport frames",
                     "warm framed running lights"),
        "negative": ("plastic furniture, office cubicle, fluorescent ceiling panel, "
                     "bare concrete, patched clothing"),
    },
    "precursor": {
        # Руины и то, что человек с ними делает, — один регистр: обжитая раскопка
        # и есть характерный кадр этого мира
        "title": "древние руины",
        # Не морды пришельцев: обсидиан, врезанный узор и геометрия, которая не
        # сходится. Вырезанное лицо чекпойнт рисует стереотипной башкой
        "vocab": ("these are ruins of a civilisation that vanished long before humans, and the frame "
                  "says so first of all: colossal masses of seamless black glassy stone, too large "
                  "to have been lifted, meeting at angles that refuse to resolve, broken, toppled "
                  "and half buried under the drifted sand, earth and rubble of ages. The material "
                  "itself has never weathered — its faces are still smooth, dense geometric "
                  "patterns incised deep into them run on without repeating, and a faint cold light "
                  "is held deep in the cuts — but everything around it has: spans fallen, gaps open "
                  "to the sky or to the dark, dust laid thick, growth creeping over the lower stones "
                  "where daylight reaches. Where people have got at it their own work clings to it "
                  "and does not belong — scaffolding and ladders lashed to the black faces, cable "
                  "and work lamps run across the incised patterns, instruments clamped where they "
                  "hold, the tents and crates of a dig, boot tracks in the dust. Light falls in "
                  "through breaks in the masses or comes from the work lamps, and the rest keeps "
                  "its dark"),
        "vocab_person": ("whoever the GM named is dressed for working in the dark against cold "
                         "stone: dark cloth wrapped and layered over a hard technical harness, "
                         "the shape of the body hidden under it, a hood or wrap at the head, "
                         "instruments and lamps clipped to the harness, hands wrapped; on those "
                         "the place has already changed, the glow of the material reaches the "
                         "body — marks lit under the skin, eyes lit from within"),
        "tags": ("obsidian black glass and dark iron", "deeply incised geometric pattern",
                 "human scaffolding lashed to seamless stone"),
        "tags_person": ("obsidian relic fragment", "dark cloth over technical harness",
                        "light held under the skin"),
        "vocab_ship": ("whatever hull the GM named, if it can be called a hull at all, is the "
                      "same obsidian-black seamless material as the rest of this register: masses "
                      "that meet at angles which refuse to resolve, no visible propulsion, no "
                      "seam, no plate line, and no marking a human hand could have made. A dense "
                      "incised geometric pattern runs across the surface without repeating. Where "
                      "people have got at it their own work clings and does not belong — "
                      "scaffolding lashed to a hull that never weathered, cable run across an "
                      "incised face, an access cut crudely torched through material that shows no "
                      "other damage"),
        "tags_ship": ("obsidian seamless hull with no visible propulsion",
                     "deeply incised geometric pattern",
                     "crude torched access cut into unweathered material"),
        "negative": ("alien face sculpture, humanoid alien head, grey alien, stereotypical alien, "
                     "totem mask, egyptian statue, mayan carving, gargoyle, gothic cathedral, "
                     "stained glass window, wizard robe, crystal ball, tarot imagery"),
    },
}
REGISTER_ORDER = ("derelict", "junk", "frontier", "hightech", "hegemony", "luxe", "precursor")
# подсказка ГМу у кнопки регистра в мастерской
REGISTER_HINTS = {
    "derelict": "брошено давно и не чинено: ржавчина и коррозия, облезшая краска, потёки, обломки, мёртвые пульты, свет только сквозь пролом",
    "junk": "лом и ржавчина: груды хлама, разобранные корпуса, лачуги и лотки из листа, старьёвщики",
    "frontier": "люди здесь живут: отделка далёкого будущего в нейтральных тонах с тёплыми акцентами, вещи в деле, свои мелочи и зелень, износ от рук, не грязь",
    "hightech": "гильдии и центр: спроектировано и вылизано, скрытые стыки, хардлайт, ровный свет",
    "hegemony": "власть и порядок: тёмный сплав, строй и ранги, гербы, холодный свет с красным",
    "luxe": "выбрано, а не выдано: простор и скульптурные изгибы, светящийся камень, сады и вода в доме, техника спрятана",
    "precursor": "руины древней нечеловеческой цивилизации: исполинский чёрный камень, врезанный узор, обвалы и занос, людские леса поверх",
}
if EN:
    for _key, _title in {"derelict": "derelict", "junk": "junkyard", "frontier": "lived-in space",
                         "hightech": "high-tech", "hegemony": "Hegemony", "luxe": "high life",
                         "precursor": "Precursor ruins"}.items():
        REGISTERS[_key]["title"] = _title
    REGISTER_HINTS = {
        "derelict": "long abandoned and never repaired: rust and corrosion, peeling paint, streaks, debris, "
                    "dead consoles, light only through a breach",
        "junk": "scrap and rust: heaps of junk, gutted hulls, shacks and stalls of sheet metal, scavengers",
        "frontier": "people live here: far future fittings in neutral tones with warm accents, things in use, "
                    "personal belongings and greenery, wear from hands, not grime",
        "hightech": "the Guilds and the Core: designed and immaculate, hidden joins, hardlight, even light",
        "hegemony": "power and order: dark alloy, ranks and formations, heraldry, cold light with red",
        "luxe": "chosen, not issued: space and sculpted curves, glowing stone, gardens and water indoors, "
                "hidden technology",
        "precursor": "ruins of an ancient non-human civilisation: colossal black stone, incised patterns, "
                     "collapse and drifted sand, human scaffolding on top",
    }
# снятые регистры: «хай-тек» слился с чистым будущим, «мистика» — с руинами.
# Старые снимки формы и киты кампаний присылают их до сих пор
# снятые ключи ведут к тем регистрам, что их вобрали: «обжитая техника» ушла
# во фронтир, «продвинутое будущее» — в хай-тек, «мистика» — в древние руины
REGISTER_LEGACY = {"future": "frontier", "advanced": "hightech",
                   "mystic": "precursor"}


def norm_register(register: str) -> str:
    """Привести регистр к живому набору: снятые ключи ведут к тем, что их вобрали."""
    key = (register or "").strip()
    return REGISTER_LEGACY.get(key, key)

# ── якоря архетипов ──────────────────────────────────────────────────────────
# Закрытые списки: модель выбирает ключ, код дописывает якорь перед субъектом.
# Якорь уводит чекпойнт от приора нашего мира — «офицер» без него выходил
# патрульным с бляхой, «солдат» — сегодняшней пехотой, «корабль» — сухогрузом.
# Ключ «прочее» оставляет кадр без якоря.
PERSON_ROLES = {
    "soldier": "armoured soldier in sealed fatigues",
    "officer": "trade guild officer in a sealed high-collared dark uniform",
    "pilot": "starship pilot",
    "ship crew": "starship crew hand",
    "mechanic": "starship mechanic",
    "scavenger": "frontier scavenger",
    "bounty hunter": "armed tracker in practical fieldwear",
    "criminal": "syndicate enforcer",
    "trader": "trade guild trader",
    "official": "trade guild functionary",
    "medic": "field medic",
    "scholar": "xenoarchaeologist at a dig",
    "cultist": "hooded cult devotee",
    "psyker": "relic-touched psyker, glow beneath the skin",
    "courier": "city courier",
    "civilian": "colony civilian",
    "xeno": "non-human sapient creature in worn spacer clothing",
    # машина среди ролей потому, что рамка персонажа требует читаемое лицо, и на
    # безлицем корпусе модель рисует человека за стеклом; выбор роли её снимает
    "machine": "worker machine on its own chassis, plated body, sensor housing on top",
    OTHER: "",
}
# якоря кадра — по подтипу, который выбрал ГМ; у планеты якорь постоянный и
# зашит в рамку, поэтому подтипа planet в словаре нет
FRAME_ANCHORS: dict[str, dict[str, str]] = {
    "ship": {
        # «boxy industrial» раньше сидело прямо в якоре и держало любой борт
        # промышленным — хай-тек-регистр (плавные обводы, бесшовные швы) стоит
        # в хвосте строки и не отбивал его. Якорь называет только класс вещи;
        # облик (промышленный / угловатый футуристичный) отдан регистру
        # «on landing struts» модель почти всегда читает как ноги животного —
        # тонкие гнутые конечности вместо механического шасси, на любом
        # регистре. «Grounded on its extended landing gear» этого не провоцирует
        # слово starship несёт свой силуэт — сигару с соплами, и он перебивает
        # форму, названную в слотах: три разных описания давали один корабль
        # (зонд probe_ship). Якорь называет класс словом spacecraft, а форму
        # корпуса — прямо, чтобы слоты формы имели с чем спорить
        "starship": "large boxy spacecraft hull, flat slab sides",
        "small craft": "small boxy spacecraft hull",
        # рабочий борт в деле: «on landing struts» тянет кадр в стоянку и
        # съедает буксируемый груз — якорь сам называет груз, а не полагается
        # на marks/surround, которые проигрывают ему конкуренцию за внимание
        "tug": "tug spacecraft hull with tow arm extended, towed container in frame",
        "ground vehicle": "ground vehicle with wheels or tracks",
        "walking machine": "walking machine on legs",
        OTHER: "",
    },
    "handheld": {
        "tool": "handheld tool",
        "weapon": "weapon",
        # не «alien»: это слово рисует зелёную голову и глушит собственный
        # анти-свод (условный негатив снимается словами позитива). Форму и
        # чуждость вещи несут слова ГМа, якорь только уводит от безделушки
        "relic artifact": "otherworldly artifact",
        "device": "utilitarian device",
        OTHER: "",
    },
    "structure": {
        "station": "orbital station of docked modules adrift in open space",
        "ring gate": "colossal seamless ring fixed in open space",
        "derelict": "drifting derelict hulk of a boxy spacecraft",
        OTHER: "",
    },
    "landscape": {
        "landing field": "open landing field",
        "street": "street between built up structures",
        "settlement": "settlement of many buildings",
        "wilderness": "open planetary surface under a strange coloured sky",
        "ruin site": "ruin of black seamless precursor material",
        OTHER: "",
    },
    "interior": {
        # «bulkhead ribs and pressure doors» рисовали любой борт изнутри гаражом
        # или станцией из рёбер и труб; облик отделки даёт регистр
        "ship interior": "starship interior of curved panelled walls with light set into them",
        "station interior": "orbital station interior",
        "colony interior": "habitation room",
        "drinking hall": "drinking hall with a long bar",
        "market": "covered market of many stalls",
        "workshop": "repair shop full of parts",
        "hangar": "landing bay with craft on struts",
        "ruin interior": "black seamless ruin interior",
        OTHER: "",
    },
}

# Возраст словами, не числом: «forty five years old» рисующая модель не читает,
# и сорокапятилетняя выходила девушкой. Ключи по-английски и с годами: по русским
# ярлыкам модель мазала — «лет пятидесяти» попадало в «молодой»
AGE_BANDS = {
    "child": "child",
    "teenager": "teenaged",
    "twenties": "young adult in their twenties",
    "thirties": "in their thirties, first lines at the eyes",
    "forties": "middle-aged in their forties, lined face, greying hair",
    "fifties or sixties": "in their fifties, deeply lined weathered face, grey hair",
    "seventy or older": "elderly, heavily lined face, thin white hair, stooped",
    # не названный ГМом возраст ничего не дописывает: прежнее «adult, years of the
    # trade on the face» уходило в строку и на безлицые корпуса, и на любого,
    # кому лет никто не назначал
    "unspecified": "",
}

# Слова, которые тянут в кадр наш собственный век или самолёт. Инструкция их
# запрещает, но небольшая модель запрет проигрывает привычке. Подмена идёт кодом
# по слотам и разнесена по направлениям: одёжный словарь — персонажу и экшну,
# авиационно-церковный — кадру. Иначе «weld patch» корпуса становится нашивкой,
# а «crooked nose» персонажа — плоским носом корабля
EARTH_WORDS_WEAR = {
    # «suit» — самое стойкое слово словаря: правило слота его запрещает, а Квен
    # всё равно пишет, и модель отвечает деловой двойкой нашего века
    "suit": "long heavy coat",
    "suits": "long heavy coats",
    "uniform": "sealed one piece garment",
    "uniforms": "sealed one piece garments",
    "jumpsuit": "sealed one piece garment",
    "coverall": "sealed work garment",
    "coveralls": "sealed work garment",
    "overalls": "sealed work garment",
    "badge": "etched plate",
    "badges": "etched plates",
    "printed rank insignia": "printed rank marks",
    "rank insignia": "printed rank marks",
    "insignia": "geometric marks",
    "tunic": "sealed jacket",
    "epaulettes": "shoulder straps",
    "epaulette": "shoulder strap",
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
    # «офис» тянет стеклянную башню нашего века с городом за окном
    "office": "machined work floor",
    "offices": "machined work floors",
}
EARTH_WORDS_FORM = {
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
# Абзац мира писан про его населённую часть, и для чистых регистров он неверен:
# «ничего нового, всё сварено и латано» перебивало и словарь регистра, и слова
# ГМа. Предложение подменяется, а не дополняется — спорить с ним дороже
SHABBY_LINE = ("Nothing here is new — metal welded, riveted, scavenged and repainted, cables "
               "where a wall should be, readouts glowing in rooms never designed for them.")
CLEAN_LINE = ("Most of it is patched and scavenged, but this frame is not in that part of the "
              "world: here things were made to a design and are kept that way, and the welded "
              "plate and strung cable of the shabby majority stay out of the frame unless the "
              "GM put them in it.")
# у каких регистров мир выглядит иначе, чем в абзаце выше
CLEAN_REGISTERS = ("hightech", "hegemony", "luxe")


def tune_world(text: str, register: str) -> str:
    """Подменить описание состояния мира под выбранный угол."""
    if register in CLEAN_REGISTERS and SHABBY_LINE in text:
        return text.replace(SHABBY_LINE, CLEAN_LINE, 1)
    return text


# Материалы нашего доиндустриального века: одно слово «wooden» на стойке
# превращает фронтирный кабак в земной паб с венскими стульями целиком, и
# держится оно и в месте персонажа, и в кадре — потому словарь общий
EARTH_WORDS_MATERIAL = {
    "wooden": "riveted sheet",
    "wood": "sheet metal",
    "wood-panelled": "sheet panelled",
    "wood-paneled": "sheet panelled",
    "timber": "sheet metal",
    "oak": "dark metal",
    "mahogany": "dark metal",
    "plank": "metal plate",
    "planks": "metal plates",
    "ceramic": "dented metal",
    "mug": "metal cup",
    "mugs": "metal cups",
    "brick": "cast slab",
    "bricks": "cast slabs",
    "wicker": "woven strap",
}

# «байк» модель дорисовывает колёсами и рулём, даже с приставкой hover и
# соплами под днищем: слово ГМа хаб переносит дословно, вопреки правилу
EARTH_WORDS_VEHICLE = {
    "hover-bike": "hovering jet-sled",
    "hover-bikes": "hovering jet-sleds",
    "hoverbike": "hovering jet-sled",
    "hoverbikes": "hovering jet-sleds",
    "speeder bike": "hovering jet-sled",
    "speeder bikes": "hovering jet-sleds",
    "bike": "hovering jet-sled",
    "bikes": "hovering jet-sleds",
    "motorbike": "hovering jet-sled",
    "motorbikes": "hovering jet-sleds",
    "speeder": "hovering jet-sled",
    "speeders": "hovering jet-sleds",
    "handlebars": "control grips",
}
# «alien» и родня рисуют одну голову из одной вселенной — серую, большеглазую
# или гигеровскую — и она перебивает всё остальное. Хаб их не пишет по правилу,
# эта подмена — страховка
EARTH_WORDS_XENO = {
    "alien": "xenos", "aliens": "xenos", "extraterrestrial": "xenos", "extraterrestrials": "xenos",
    "xenomorph": "xenos", "xenomorphs": "xenos", "biomechanical": "armoured",
}

EARTH_WORDS = {"person": {**EARTH_WORDS_WEAR, **EARTH_WORDS_MATERIAL, **EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO},
               "action": {**EARTH_WORDS_WEAR, **EARTH_WORDS_MATERIAL, **EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO},
               "frame": {**EARTH_WORDS_FORM, **EARTH_WORDS_MATERIAL, **EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO}}

# тег с отрицанием рисующая модель читает как просьбу нарисовать отрицаемое
NEGATION = re.compile(r"\b(no|not|without|lacking)\b", re.I)
# Модель просят писать по-английски, но в слот иногда уезжает русское слово прямо
# из описания ГМа. Рисующая модель кириллицу не понимает — тег выбрасываем на сборке
CYR_SLOT = re.compile(r"[а-яё]", re.I)
EARTH_RE = {
    kind: re.compile(r"\b(" + "|".join(sorted(words, key=len, reverse=True)) + r")\b", re.I)
    for kind, words in EARTH_WORDS.items()
}


def swap_earth_words(text: str, kind: str = "person", dedup: bool = True) -> str:
    """Заменить слова нашего века на описание покроя, материала или формы.

    Рисующая модель на «uniform» отвечает мундиром позапрошлого века, на «nose» —
    самолётом: эти слова несут земную вещь целиком. Словарь зависит от направления,
    замена идёт по целым словам и сохраняет регистр первой буквы."""
    words = EARTH_WORDS.get(kind)
    if not words:
        return text

    def repl(m: re.Match) -> str:
        word = m.group(0)
        swap = words[word.lower()]
        return swap[0].upper() + swap[1:] if word[0].isupper() else swap

    out = EARTH_RE[kind].sub(repl, text)
    # в прозе слова повторяются законно — задвоение чистится только во фразе-теге
    if out == text or not dedup:
        return out
    # подмена вносит свои слова в чужую фразу, и слово задваивается:
    # «patched work coveralls» выходило «patched work sealed work suit»
    seen, kept = set(), []
    for word in out.split():
        low = word.lower()
        if low in seen:
            continue
        seen.add(low)
        kept.append(word)
    return " ".join(kept)


# Регистр писан и для живого, и для вещи: у древних руин на предмете вылезали
# вены и кожа, у хай-тека — стоячий воротник. Что относится к телу, в кадре без
# людей не применяется.
# Регистр — справка, а не задание: заказ пишет ГМ, регистр только говорит, как в
# этом углу мира выглядит названное им. Формулировка важна в обе стороны — без
# приоритета над общим законом Квен на хай-теке продолжал писать ржавчину, а с
# приказным тоном начинал рисовать регистр вместо просьбы ГМа
REGISTER_LAW = (
    "The GM's text is the request; this register is reference, not a second request. You draw "
    "what they asked for, and the register tells you how the things they named look in this "
    "corner of the world. It never adds an object, a place or a person they did not name, and "
    "where their words and the register disagree, their words win. Where they left something "
    "open — a material, a finish, a state, the light — the register fills it in, and it fills it "
    "in ahead of the general description of the world above. A value that would fit any register "
    "equally well, such as welded metal walls or scuffed flooring, is the drawing model's habit "
    "rather than this frame: write it in the language of the register instead. Welded plate, "
    "riveted bulkhead and exposed conduit are not neutral either — they are one register among "
    "these, and they belong in the frame only when that is the one the GM chose.")
REGISTER_LAW_THING = (
    REGISTER_LAW
    + " Whatever in the register belongs to a person — clothing, fabric, flesh, skin, eyes, "
      "veins — is passed over here unless the GM put people in the place: a thing and a place "
      "take only the material, the structure, the surface, the wear and the light.")


def register_text(reg: dict, kind: str, view: str = "") -> str:
    vocab = reg["vocab"]
    if kind == "frame" and view == "ship" and reg.get("vocab_ship"):
        extra = reg["vocab_ship"]
    else:
        extra = reg.get("vocab_person") if kind != "frame" else ""
    if extra:
        vocab = f"{vocab}; {extra}"
    return ("\nVISUAL REGISTER — REFERENCE. The GM put this frame in one corner of the world. "
            f"This is what that corner looks like:\n{vocab}.\n"
            + (REGISTER_LAW_THING if kind == "frame" else REGISTER_LAW))

