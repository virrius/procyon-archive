"""The world for the drawing side: frame subtypes, registers, anchors and replacing Earth words.

Assembling the hub instruction and the prompt line lives in prose.py.
"""
from __future__ import annotations

import re

from ..i18n import twin_lang

# English instance: the instructions for the drawing side are in English anyway; only what the GM
# sees changes, plus the note about the Russian description
EN = twin_lang(__name__) == "en"

KINDS = ("person", "frame", "action")
# the GM picks the frame subtype: earlier the model classified shot type and scale itself
# and got confused — a station came out as a ship, work outside was drawn inside
VIEWS = ("ship", "handheld", "structure", "planet", "landscape", "interior")
# the "none of the above" item in the closed list of anchors: gives no anchor, but the GM sees it in the kit
OTHER = "other" if EN else "прочее"

# ── frame subtypes ───────────────────────────────────────────────────────────
# The subtype law is appended to the frame instruction: camera and distance are set by the GM's
# choice, the hub is left with the content
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

# ── visual registers ─────────────────────────────────────────────────────────
# vocab goes into the hub instruction; vocab_person — clothing of the corner's people, vocab_ship — hull look
REGISTERS: dict[str, dict] = {
    "derelict": {
        "title": "заброшка",
        # register clothing is only for a living subject: on things, "seams and gloves"
        # drifted into the object's features
        "vocab_person": ("whoever the GM named came into this place from outside and is dressed "
                         "for it: a sealed working garment closed to the throat, patched at the "
                         "knees and elbows where it goes down on them, a harness of straps over "
                         "it carrying what must stay to hand, a lamp clipped at the chest, "
                         "breathing gear hanging at the neck, heavy gloves and boots, and the "
                         "dust of the place worked into every fold"),
        # Not post-apocalypse and not Precursor ruins: this is human-made, abandoned
        # recently by the world's standards and never repaired since
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
        "vocab_ship": ("whatever hull the GM named has been picked over by everyone who passed "
                      "through it since it died: access panels missing where someone needed the "
                      "plate elsewhere, conduit runs cut and left dangling, thruster bells "
                      "scorched and cold, viewports starred or blown out, drive systems dark with "
                      "only battery light holding in a compartment or two. The structure that "
                      "remains is honest about how it was built — ribs and spars showing where "
                      "skin has been stripped away — and nothing has been kept level or square "
                      "since"),
    },
    "junk": {
        # The former frontier: patched metal, scrap and rust moved here so that
        # ordinary working space would stop being a junkyard by default
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
        # the model draws "stitched patches" as literal decorative crosses
        # on the fabric — a comic-book patch, not wear; "mended" does not do that
        "vocab_ship": ("whatever hull the GM named was built to be fixed by the people who fly "
                      "it, not by a yard: a manufactured frame under a skin of salvaged and "
                      "mismatched plate, patch welds and rivet rows where a hole was closed in a "
                      "hurry, hand-lettered hull numbers, thruster bells scorched and pitted from "
                      "use, conduit and cable run externally and clamped rather than concealed, a "
                      "boarding ramp or ladder welded on wherever it was needed. Nothing matches "
                      "anything else, and every mismatch marks a repair that kept it flying"),
    },
    "frontier": {
        # Lived-in space — people live here and made the corner their own. The vocabulary is
        # qualities, not an inventory: airlocks, lifts and stencils listed here were carried by the hub
        # to any place, and a cantina came out as a hangar
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
        "vocab_ship": ("whatever hull the GM named is a working ship flown hard and looked after "
                      "by its crew: painted plate in a livery they keep up, stencilled numbers, "
                      "clear panel lines and access hatches, thruster bells scorched from use; "
                      "everything fits and nothing is falling off"),
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
        # A register is qualities, not a wardrobe: clothing listed here went into
        # the slots word for word, and every high-tech character came out as a technician in a spacesuit
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
        "vocab_ship": ("whatever hull the GM named is machined as one continuous form, not built "
                      "up from parts: sharp swept planes and tapered masses meeting at a hard "
                      "edge rather than a seam, composite skin with no rivet or plate line to "
                      "read, control surfaces and intakes cut clean into the hull rather than "
                      "bolted on, running lights set flush and edge-lit, thrusters recessed into "
                      "the airframe rather than hung off it. Nothing is patched and nothing "
                      "improvised — the hull looks machined to a tolerance a hand could never "
                      "hold, and its aggression is in the geometry, not in wear"),
    },
    "hegemony": {
        # The power of the Hegemony and its houses: order, ranks, scale. High-tech is
        # the Guilds and corporations, bright and polished; this one is dark and oppressive
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
        "vocab_ship": ("whatever hull the GM named is a warship of the order: a long angular "
                      "wedge of dark grey armour plate, regular rows of gun emplacements and "
                      "hangar mouths, house marks painted large, running lights cold white and "
                      "red; vast, symmetrical and menacing"),
    },
    "luxe": {
        # High life is not high-tech: there is no more technology here, it is just hidden in
        # the furnishings. Far-future luxury is space, light and a form that cannot
        # be made by hand; heavy fabrics and gold gave a retro salon
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
        "vocab_ship": ("whatever hull the GM named is finished like a piece of furniture, not a "
                      "working machine: deep lacquered panels or brushed precious metal laid over "
                      "the structural hull, a hand-painted or inlaid livery rather than a "
                      "stencilled registry, viewports framed in worked metal, running lights warm "
                      "rather than clinical, boarding stairs that fold out rather than a bare "
                      "ramp. The hull shows no working wear at all — this is a possession kept, "
                      "not a tool used"),
    },
    "precursor": {
        # The ruins and what humans do with them are one register: a lived-in dig site
        # is the characteristic frame of this world
        "title": "древние руины",
        # Not alien faces: obsidian, incised patterns and geometry that does not
        # add up. The checkpoint draws a carved face as a stereotypical head
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
        "vocab_ship": ("whatever hull the GM named, if it can be called a hull at all, is the "
                      "same obsidian-black seamless material as the rest of this register: masses "
                      "that meet at angles which refuse to resolve, no visible propulsion, no "
                      "seam, no plate line, and no marking a human hand could have made. A dense "
                      "incised geometric pattern runs across the surface without repeating. Where "
                      "people have got at it their own work clings and does not belong — "
                      "scaffolding lashed to a hull that never weathered, cable run across an "
                      "incised face, an access cut crudely torched through material that shows no "
                      "other damage"),
    },
}
# hint for the GM at the register button in the studio
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
# retired registers: "high-tech" merged with the clean future, "mystic" with the ruins.
# Old form snapshots and campaign kits still send them
# retired keys lead to the registers that absorbed them: "lived-in tech" went
# to the frontier, "advanced future" to high-tech, "mystic" to ancient ruins
REGISTER_LEGACY = {"future": "frontier", "advanced": "hightech",
                   "mystic": "precursor"}


def norm_register(register: str) -> str:
    """Bring a register to the live set: retired keys lead to the ones that absorbed them."""
    key = (register or "").strip()
    return REGISTER_LEGACY.get(key, key)

# ── frame anchors ────────────────────────────────────────────────────────────
# A closed list: the hub picks a key, code puts the class phrase first — it pulls
# the model away from the prior of our world. The OTHER key gives no anchor.
# Anchors are by the subtype the GM picked; a planet has a fixed anchor
# built into the frame, so there is no planet subtype in the dict
FRAME_ANCHORS: dict[str, dict[str, str]] = {
    "ship": {
        # "boxy industrial" used to sit right in the anchor and kept any hull
        # industrial — the high-tech register (smooth lines, seamless joins) sits
        # at the tail of the line and did not override it. The anchor names only the class of the thing;
        # the look (industrial / angular futuristic) is left to the register
        # the model almost always reads "on landing struts" as animal legs —
        # thin bent limbs instead of mechanical landing gear, on any
        # register. "Grounded on its extended landing gear" does not provoke this
        # the word starship carries its own silhouette — a cigar with nozzles, and it overrides
        # the shape named in the slots: three different descriptions gave one ship
        # (probe_ship). The anchor names the class with the word spacecraft, and the hull
        # shape directly, so the shape slots have something to argue with
        "starship": "large boxy spacecraft hull, flat slab sides",
        "small craft": "small boxy spacecraft hull",
        # a working hull in action: "on landing struts" pulls the frame toward a parked ship and
        # eats the towed cargo — the anchor names the cargo itself instead of relying
        # on marks/surround, which lose the competition for attention to it
        "tug": "tug spacecraft hull with tow arm extended, towed container in frame",
        "ground vehicle": "ground vehicle with wheels or tracks",
        "walking machine": "walking machine on legs",
        OTHER: "",
    },
    "handheld": {
        "tool": "handheld tool",
        "weapon": "weapon",
        # not "alien": the word draws a green head and drowns out its own
        # anti-clause (a negative phrased in the positive prompt is overridden by the positive words). The shape and
        # strangeness of the thing come from the GM's words, the anchor only steers away from a trinket
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
        # "bulkhead ribs and pressure doors" drew any hull interior as a garage
        # or a station of ribs and pipes; the finish look comes from the register
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

# ── replacing Earth words ───────────────────────────────────────────────────
# A word naming the purpose of a thing pulls in its whole Earth image: for "suit" Z-Image
# draws a business suit, for "bike" wheels and handlebars, for "alien" a gray big-eyed
# head. The instruction forbids them, but the hub sometimes carries the GM's word over verbatim —
# the replacement is a safety net. The rest is held by the instruction rule, not the dict
EARTH_WORDS_WEAR = {
    "space suit": "sealed pressure garment",
    "space suits": "sealed pressure garments",
    "spacesuit": "sealed pressure garment",
    "spacesuits": "sealed pressure garments",
    "vac suit": "sealed pressure garment",
    "vac suits": "sealed pressure garments",
    "pressure suit": "sealed pressure garment",
    "pressure suits": "sealed pressure garments",
    "suit": "long heavy coat",
    "suits": "long heavy coats",
    "uniform": "sealed one piece garment",
    "uniforms": "sealed one piece garments",
    "jumpsuit": "sealed one piece garment",
    "jumpsuits": "sealed one piece garments",
}
EARTH_WORDS_VEHICLE = {
    "hover-bike": "hovering jet-sled",
    "hover bike": "hovering jet-sled",
    "hover bikes": "hovering jet-sleds",
    "hover-cycle": "hovering jet-sled",
    "hover-cycles": "hovering jet-sleds",
    "hover cycle": "hovering jet-sled",
    "hover cycles": "hovering jet-sleds",
    "hovercycle": "hovering jet-sled",
    "hovercycles": "hovering jet-sleds",
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
EARTH_WORDS_XENO = {
    "alien": "xenos", "aliens": "xenos", "extraterrestrial": "xenos", "extraterrestrials": "xenos",
    "xenomorph": "xenos", "xenomorphs": "xenos", "biomechanical": "armoured",
}

EARTH_WORDS = {"person": {**EARTH_WORDS_WEAR, **EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO},
               "action": {**EARTH_WORDS_WEAR, **EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO},
               "frame": {**EARTH_WORDS_VEHICLE, **EARTH_WORDS_XENO}}
EARTH_RE = {
    kind: re.compile(r"\b(" + "|".join(sorted(words, key=len, reverse=True)) + r")\b", re.I)
    for kind, words in EARTH_WORDS.items()
}


def swap_earth_words(text: str, kind: str = "person") -> str:
    """Replace an Earth word with a description, matching whole words and keeping the capital letter."""
    words = EARTH_WORDS.get(kind)
    if not words:
        return text

    def repl(m: re.Match) -> str:
        word = m.group(0)
        swap = words[word.lower()]
        return swap[0].upper() + swap[1:] if word[0].isupper() else swap

    return EARTH_RE[kind].sub(repl, text)
