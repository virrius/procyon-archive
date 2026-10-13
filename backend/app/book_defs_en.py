"""Scum and Villainy canon from the English book — a twin of book_defs with the same shape.

Used through book_defs.book() on an English instance: keys, order and numbers are the same, names and
texts follow the English edition (reference/scum_and_villainy_en.md).
"""

from __future__ import annotations

from .book_sheets_en import CHAR_SHEET, PLAYBOOK_SHEETS  # character playbooks
from .book_text import with_text

PLAYBOOK_SHEETS, CHAR_SHEET = with_text("en", PLAYBOOK_SHEETS, CHAR_SHEET)

SHIP_SIZES: list[str] = ["personal", "freighter", "corvette", "frigate", "dreadnought"]


SHIP_MODULES: dict[str, list[dict]] = {
    "hull": [
        {"key": "hangar", "name": "Landing Bay",
         "text": "Airlocks, bay-doors, and takeoff ramps to accommodate shuttles and single-pilot "
                 "small fighter craft."},
        {"key": "cabins", "name": "Crew Quarters",
         "text": "You can sleep anywhere, but crew quarters are actually meant for it: privacy and "
                 "comfort in a domain where such things are luxuries."},
        {"key": "smuggler_bay", "name": "Smuggling Compartments",
         "text": "Like a cargo hold (can carry a small shipment), but it won't show up on routine scans. "
                 "At 3+ hull rating, it has life support for smuggling people too."},
        {"key": "hold", "name": "Cargo Hold",
         "text": "Enough space to carry a moderate (cred-earning) shipment. A cargo hold is evident "
                 "when the ship is boarded."},
    ],
    "engines": [
        {"key": "grav_generator", "name": "Gravitic Field Generator",
         "text": "Creates a large gravitic field extending ship to ship. Can be used to grapple or tow. "
                 "Temperamental Guild prototype. Not legal."},
        {"key": "cloak", "name": "Cloaking Device",
         "text": "Masks the heat and electrical signature of the ship, making it very hard to detect "
                 "or identify. Super illegal."},
        {"key": "jump_drive", "name": "Jump Drive",
         "text": "A special engine that can activate the Ur gates that connect systems."},
        {"key": "afterburner", "name": "Afterburners",
         "text": "A short burst of speed: may treat engines as one higher rating for a roll, but it may damage them."},
    ],
    "sensors": [
        {"key": "quantum_encryptor", "name": "Quantum Encryptor",
         "text": "Encrypts comms and data storage. Grants armor against interception of digital communications."},
        {"key": "false_transponder", "name": "Fake Transponder",
         "text": "Broadcasts a different ship's signal, plays a powerful recording of sensor echoes, "
                 "or acts as a beacon. Usable remotely."},
        {"key": "nexus", "name": "Nexus Link",
         "text": "A connection to the Hegemonic System Network: news updates, system-wide sensor grids, "
                 "real-time intra-system messages. Insecure."},
        {"key": "targeting_system", "name": "Targeting Computer",
         "text": "Handles calculations and targeting for weapon systems. Roll comms rating when firing."},
        {"key": "long_range_scanner", "name": "Long-Range Scanner",
         "text": "EM spectrum and gravimetric readings, giving the crew advance warning up to a dozen "
                 "light-minutes away."},
    ],
    "guns": [
        {"key": "grapplers", "name": "Grappling Hooks",
         "text": "Nets, grappling lines, and arms for latching onto asteroids or tying two vessels "
                 "together for towing or boarding. Legal."},
        {"key": "main_gun", "name": "Coherence Cannon",
         "text": "A capital weapon: one shot only until repaired or recharged on ships smaller than "
                 "dreadnoughts. May fry systems. Incredibly deadly. Super not legal."},
        {"key": "beam_cannons", "name": "Particle Cannons",
         "text": "Usually fixed in one direction on personal vessels. Not legal without a license."},
        {"key": "missiles", "name": "Missiles",
         "text": "Projectile with mounted drive. Not legal."},
        {"key": "mining_drill", "name": "Mining Drill",
         "text": "Close-range energy drill. Vaporizes rock. Easily modified to bore through hulls. Legal."},
    ],
    "extra": [
        {"key": "armory", "name": "Armory",
         "text": "A secure room holding the crew weapons and armor; all of them are considered to be fine."},
        {"key": "ai", "name": "AI Module",
         "text": "Software connected to an Ur AI core: can automate tasks or otherwise run the ship "
                 "on behalf of the crew. Snarky personality module available for free."},
        {"key": "galley", "name": "Galley",
         "text": "A combined kitchen and serving area with fresh food storage. Greatly facilitates longer trips."},
        {"key": "brig", "name": "Brig",
         "text": "Space jail. Not meant for long-term incarceration. Will prevent most attempts to escape."},
        {"key": "lab", "name": "Science Bay",
         "text": "Laboratory to analyze anomalies and Precursor artifacts. Secure storage for things "
                 "that may react oddly with the rest of the ship (or physics)."},
        {"key": "infirmary", "name": "Medical Bay",
         "text": "Medical equipment, drugs, and medical scanners. Add +1d to all crew recovery rolls."},
        {"key": "shields", "name": "Shields", "cost": 2,
         "text": "Particle sinks and EM deflectors. Counts as armor against ship weapons and energy discharge. "
                 "Completely absorbs blaster fire. Costs two upgrades instead of just one."},
    ],
    "gear": [
        {"key": "rover", "name": "Land Rover",
         "text": "An armored all-terrain vehicle for carrying heavy cargo and folks overland."},
        {"key": "hiber_pods", "name": "Stasis Pods",
         "text": "Each pod has room for one severely injured, deathly ill, or unconscious guest. "
                 "Does not prevent dreams."},
        {"key": "holo", "name": "Holo-Emitters",
         "text": "Holo-conferences and flashy displays. The images don't usually hold up to close scrutiny, "
                 "but can be convincing for a short while."},
        {"key": "safe", "name": "Vault",
         "text": "Secures valuables during space travel behind a programmable lock. Uses hull rating "
                 "when contested."},
        {"key": "alarm", "name": "Intruder Alarm",
         "text": "Motion sensors, door codes, and panic buttons: a klaxon and flashing red lights "
                 "if something is out of place."},
        {"key": "shuttle", "name": "Shuttle",
         "text": "A small spacecraft carrying a few people from planet to orbit; ships larger than "
                 "freighters need one to reach the surface. Systems count as quality zero vs. actual ships."},
        {"key": "power_cells", "name": "Power Reserves",
         "text": "Batteries that can power the ship independently of the engine. Acts as armor against "
                 "power-related mishaps."},
    ],
    "crew_gear": [
        {"key": "alien_pet", "name": "Alien Pet",
         "text": "Lovable rapscallion or loyal guardian, these critters are usually more trouble "
                 "than they're worth."},
        {"key": "workshop", "name": "Workshop",
         "text": "Plasma cutters, a nano-assembler, components, and a forge: anything required to build, "
                 "modify, or disassemble complex machines. Adds +1 quality to craft rolls."},
        {"key": "ground_transport", "name": "Land Transport",
         "text": "Land transportation for the entire crew: motorized bikes, land-skimmers, boats, "
                 "or very small cars."},
        {"key": "field_kit", "name": "Survival Gear",
         "text": "Camping gear, rebreathers, climbing equipment, scuba gear: everything needed to survive "
                 "on an inhospitable, but not uninhabitable, rock."},
        {"key": "recon_drone", "name": "Recon Drone",
         "text": "A small drone for surveillance and intelligence gathering. Uses comms quality when contested."},
    ],
    "training": [
        {"key": "resolve", "name": "Resolve", "text": "Training: mark 2 xp (instead of 1) when you train Resolve."},
        {"key": "prowess", "name": "Prowess", "text": "Training: mark 2 xp (instead of 1) when you train Prowess."},
        {"key": "instinct", "name": "Insight", "text": "Training: mark 2 xp (instead of 1) when you train Insight."},
        {"key": "character_xp", "name": "Playbook xp",
         "text": "Training: mark 2 xp (instead of 1) when you train playbook xp."},
    ],
}


SHIP_TYPES: dict[str, dict] = {
    "star_dancer": {
        "label": "Stardancer",
        "blurb": "Illicit merchants, smugglers, and blockade runners",
        "ship_class": "CF-350 Series Scarab-class Freighter",
        "size": "freighter",
        "gambits": 2,
        "slots": {"hull": 4, "engines": 4, "sensors": 3, "guns": 2},
        "systems": {"hull": 2, "engines": 1, "sensors": 0, "guns": 0},
        "start_modules": ["hold", "smuggler_bay", "jump_drive", "galley", "instinct"],
        "open_modules": ["afterburner", "false_transponder", "quantum_encryptor"],
        "talents": [
            {"key": "escape", "name": "The Getaway",
             "text": "You gain potency when you Scramble or Helm to avoid capture or run a blockade. "
                     "On a delivery job, take +1d to the engagement roll."},
            {"key": "leverage", "name": "Leverage",
             "text": "Your crew knows how to pull strings: when you lay low, instead of rolling you can take "
                     "-1 status with a faction at Helpful (+1) or better to reduce your wanted level by 1 "
                     "and set your heat to 0 in a system."},
            {"key": "home_cooking", "name": "Home Cooking",
             "text": "Right after a job, spend 1 cred and a downtime activity to cook for everyone, allowing "
                     "the whole crew present to make a vice roll. If anyone overindulges, a fight erupts "
                     "and everyone gains 1 stress. Requires a galley module."},
            {"key": "cargo_sense", "name": "Cargo Eye",
             "text": "Your crew earns +1 cred for smuggling or delivery jobs. Whenever you gather info you can always ask, "
                     "“What is most valuable here?”"},
            {"key": "field_repair", "name": "Field Repairs",
             "text": "Potency when repairing your ship while in space; spending a gambit on a Rig roll "
                     "gives +2d instead of +1d."},
            {"key": "fixers", "name": "Problem Solvers",
             "text": "Each PC may add 1 action rating to Helm, Rig, or Scramble (up to a max of 3)."},
            {"key": "innocence", "name": "Just Passing Through",
             "text": "During payoff, take -1 heat. When your heat is 4 or less, +1d to deceive people when you "
                     "pass yourselves off as ordinary citizens; two downtime activities even at War (-3) with any faction."},
            {"key": "veteran", "name": "Veteran", "text": "Choose a special ability from another ship."},
        ],
        "upgrades": [
            {"key": "fake_papers", "name": "False Ship Papers", "cost": 1,
             "text": "A couple of sets of well-forged documents that simplify gate travel if the transponder "
                     "and ship match."},
            {"key": "secret_routes", "name": "Dark Hyperspace Lane Maps", "cost": 1,
             "text": "Routes through systems that aren't officially maintained. Often full of Way creatures "
                     "and pirates."},
            {"key": "smuggler_rig", "name": "Smuggler's Rigging", "cost": 1,
             "text": "Webbing or fake skin to hide one item of a max of 1 load close to the body."},
            {"key": "talisman", "name": "Lucky Charm", "cost": 2,
             "text": "An Ur artifact on the bridge: +1 gambit at the start of every job."},
            {"key": "thrill_seekers", "name": "Thrillseekers", "cost": 3,
             "text": "Each PC gets +1 stress box (stress max 10)."},
        ],
        "contacts": [
            {"key": "tkala", "name": "T'kala", "role": "dockmaster"},
            {"key": "alor", "name": "Alor", "role": "keen-eared barkeep"},
            {"key": "hini", "name": "Heani", "role": "tugboat captain"},
            {"key": "rakka", "name": "Rakka", "role": "diplomat"},
            {"key": "citani", "name": "Citani", "role": "reclusive info broker"},
        ],
        "xp_triggers": [
            "Execute a successful transport or smuggling operation.",
            "Contend with challenges above your current station.",
            "Bolster your crew's reputation or develop a new one.",
            "Express the goals, drives, inner conflict, or essential nature of the crew.",
        ],
    },
    "cerberus": {
        "label": "Cerberus",
        "blurb": "Bounty hunters and extraction specialists",
        "ship_class": "R-29 Firebrand-type Patrol Craft",
        "size": "freighter",
        "gambits": 1,
        "slots": {"hull": 2, "engines": 4, "sensors": 4, "guns": 3},
        "systems": {"hull": 0, "engines": 1, "sensors": 2, "guns": 1},
        "start_modules": ["jump_drive", "long_range_scanner", "grapplers", "brig", "prowess"],
        "open_modules": ["nexus", "beam_cannons"],
        "talents": [
            {"key": "license", "name": "Licensed",
             "text": "Take -2 heat on any legitimate bounty hunting job. Your ship can carry particle "
                     "weapons, and your crew can legally use heavy blasters."},
            {"key": "double_dealing", "name": "Play Both Sides",
             "text": "When you release a bounty target, make them a crew contact."},
            {"key": "delicate_touch", "name": "Light Touch",
             "text": "Potency when tailing a target, or when gathering info at a target's previous location."},
            {"key": "snatch", "name": "Snatch'n'Grab",
             "text": "When you use a deception, infiltration, or social plan to execute a kidnapping or "
                     "extraction, add +1d to the engagement roll."},
            {"key": "armored", "name": "Loaded For Bear",
             "text": "Your crew can carry +1 load. Distinctive, high-quality armor: when you wear armor, "
                     "it counts as heavy armor."},
            {"key": "bloodhounds", "name": "On the Trail",
             "text": "One extra downtime activity to work on long-term projects or acquire assets to track bounties."},
            {"key": "lethality", "name": "Deadly",
             "text": "Each PC may add 1 action rating to Command, Scrap, or Skulk (up to a max of 3)."},
            {"key": "veteran", "name": "Veteran", "text": "Choose a special ability from another ship."},
        ],
        "upgrades": [
            {"key": "trackers", "name": "Tracers", "cost": 1,
             "text": "Tiny bugs for clothes, beacons that attach to hulls, transmission cloners for comms. "
                     "Legality varies, but a license makes it all legal."},
            {"key": "stun_weapons", "name": "Stun Weapons", "cost": 1,
             "text": "Restraints, stun batons, stun settings on blasters, stun grenades, knockout drugs: "
                     "for capturing prisoners without (serious) harm."},
            {"key": "personal_transport", "name": "Personal Vehicles", "cost": 2,
             "text": "Sleek single-seater craft that can break atmo. You may want a landing bay on your ship."},
            {"key": "strength", "name": "Hard Knocks", "cost": 2,
             "text": "Your crew starts each job with +1 gambit."},
            {"key": "quick_bandits", "name": "Smooth Criminals", "cost": 3,
             "text": "Each crew member gains +1 stress box (total 10)."},
        ],
        "contacts": [
            {"key": "stacy", "name": "Stacey Weathers", "role": "ace reporter"},
            {"key": "arlox", "name": "Arlox", "role": "Ashen Knives Pasha"},
            {"key": "ishi", "name": "Ishi", "role": "weapons dealer"},
            {"key": "liks", "name": "Lix", "role": "xeno tracker"},
            {"key": "jezri", "name": "Jezri", "role": "fixer"},
        ],
        "xp_triggers": [
            "Execute a successful extraction or capture of a bounty.",
            "Contend with challenges above your current station.",
            "Bolster your crew's reputation or develop a new one.",
            "Express the goals, drives, inner conflict, or essential nature of the crew.",
        ],
    },
    "firebringer": {
        "label": "Firedrake",
        "blurb": "Rebels and Hegemonic criminals",
        "ship_class": "Converted Khanjigar-class Corvette",
        "size": "corvette",
        "gambits": 2,
        "slots": {"hull": 2, "engines": 3, "sensors": 4, "guns": 3},
        "systems": {"hull": 1, "engines": 1, "sensors": 0, "guns": 1},
        "start_modules": ["cabins", "jump_drive", "beam_cannons", "shields", "shuttle"],
        "open_modules": ["hangar", "targeting_system", "false_transponder", "main_gun"],
        "talents": [
            {"key": "old_comrades", "name": "Old Hands",
             "text": "When you're at War (-3) with a Hegemony faction, all crew members get +1d to vice "
                     "rolls and still get two downtime activities."},
            {"key": "forged_in_fire", "name": "Forged in Fire",
             "text": "Your crew has been toughened by cruel experience: +1d to all resistance rolls."},
            {"key": "spark", "name": "Spark of Rebellion",
             "text": "Leaving a calling card or a highly visible symbol of resistance on your job gives +2 heat, "
                     "but your crew gains +1d to vice during the next downtime, and cannot overindulge."},
            {"key": "right_cause", "name": "Just Cause",
             "text": "When your crew does the right thing at cost to themselves, you may mark a crew xp."},
            {"key": "hearts_minds", "name": "Hearts & Minds",
             "text": "Each crew member may add 1 action rating to Command, Consort, or Sway (up to a max of 3)."},
            {"key": "old_enemies", "name": "Natural Enemies",
             "text": "When you run a job against Hegemony factions, take +1d to the engagement roll."},
            {"key": "supporters", "name": "Sympathizers",
             "text": "When you deal with a crew or faction, the GM will tell you who among them believes "
                     "in your cause."},
            {"key": "veteran", "name": "Veteran", "text": "Choose a special ability from another ship."},
        ],
        "upgrades": [
            {"key": "black_market", "name": "Black Market Contacts", "cost": 1,
             "text": "Able to get you all the modules your ship needs, even illegal ones, though those "
                     "may require a job to acquire."},
            {"key": "secret_base", "name": "Secret Base", "cost": 1,
             "text": "A hiding spot in Ur ruins, an asteroid, or an abandoned station, away from the "
                     "baleful gaze of the Hegemony."},
            {"key": "popular_support", "name": "Popular Support", "cost": 3,
             "text": "When you approach a planet or a station, ask the GM who there might be a sympathizer."},
            {"key": "charmed", "name": "Way Blessed", "cost": 2,
             "text": "+1 gambit at the start of every job."},
            {"key": "zeal", "name": "Driven", "cost": 3,
             "text": "Each PC gets +1 trauma box; this can bring a PC with 4 trauma back into play."},
        ],
        "contacts": [
            {"key": "garin", "name": "Garin", "role": "Guild weapons engineer"},
            {"key": "tyura", "name": "Tyura", "role": "legendary assassin"},
            {"key": "ada_black", "name": "Ada Black", "role": "famous performer"},
            {"key": "tycho", "name": "Tiko Lux", "role": "hotshot pilot"},
            {"key": "ibo_van", "name": "Ibo-one", "role": "ancient Cult mystic"},
        ],
        "xp_triggers": [
            "Execute a successful job that opposes Hegemonic dominance.",
            "Contend with challenges above your current station.",
            "Bolster your crew's reputation or develop a new one.",
            "Express the goals, drives, inner conflict, or essential nature of the crew.",
        ],
    },
}


ORGS: list[dict] = [
    {
        "name": "Guild of Engineers", "category": "hegemony", "tier": 5,
        "blurb": "One of the Hegemonic High Guilds, responsible for resource acquisition, cybernetics, "
                 "AI, tech advancement, and research. Often have the best toys.",
        "goal": "Convert trade platform into a Way siphon",
        "turf": "SB-176 (HQ). Mining concerns in every system in Procyon. Research facilities "
                "in Rin, Iota, and Brekk.",
        "faces": [
            "Avalon Riat — chief executive: cybernetic spider legs, megalomaniac",
            "Thiel Kharrat — operations head: brutal, connected, influential",
            "Oevers Star — head researcher: genius, reclusive, overworked",
            "Yast Jor — head of SB-176: commanding, shrewd, bold",
        ],
        "assets": "Technology even the Hegemon is unaware of, stored in the Grand Archive. "
                  "Secret laboratories.",
        "quirk": "Many high-ranking Guild members sport custom cybernetics.",
        "allies": ["51st Legion", "Isotropa Max Secure"],
        "enemies": ["Borniko Syndicate", "Cobalt Syndicate", "Conclave 01", "Counters Guild"],
        "situation": "Decadent and powerful, the Guild is beyond the ability of the Governor to police, "
                     "and uses this remote sector to perform experiments banned by the Cults and "
                     "the Hegemon. Their current project: converting Way energy into a highly unstable "
                     "but physical compound.",
    },
    {
        "name": "Church of Stellar Flame", "category": "hegemony", "tier": 4,
        "blurb": "One of the official Hegemonic Cults: religious zealots who seek out and eradicate "
                 "dangerous artifacts and mystic activity in the sector. Few followers, but free "
                 "to do pretty much whatever they want.",
        "goal": "Root out heretics and dangerous elements",
        "turf": "The Way of Light, a battle cruiser orbiting incredibly close to a star (HQ).",
        "faces": [
            "Alaana — high priestess: Noble, mystic, driven, ex-heretic",
            "Battle Sister Diana — battle-scarred, exo-suited, unstoppable",
            "Iraam the Kind — inquisitor: plain, quiet, cruel",
        ],
        "assets": "Handfuls of zealots willing to die for the cause. An imperial seal (letting them "
                  "do pretty much whatever they want). A powerful battle cruiser.",
        "quirk": "Each member is branded with a mark of the Church, the Kiss of Light; the faithful "
                 "pray by bathing in light.",
        "allies": ["Dyrinek Gang", "The Maelstrom"],
        "enemies": ["Guild of Engineers", "Starsmiths Guild", "Yaru (Makers Guild)"],
        "situation": "The Church has few but elite resources in the sector. With no widespread "
                     "followers to report happenings, it relies on attuned prayers and instincts, "
                     "focusing on finding key targets rather than widespread action.",
    },
    {
        "name": "Counters Guild", "category": "hegemony", "tier": 4,
        "blurb": "Officials who maintain the galactic currency network. Their shadow repositories "
                 "store mysterious items and secure auctions and commerce.",
        "goal": "Disrupt Guild of Engineers' mining operation",
        "turf": "A currency exchange on Warren built on the ansible network (HQ). Shadow repositories "
                "in each system.",
        "faces": [
            "Torx Verron — chief executive: calculating, ruthless, expansionary",
            "Rintar Ix — operations head: conniving, jealous, sly",
            "Broq Vsigh — repository head: honorable, meticulous",
        ],
        "assets": "Shadow vaults unknown even to the Hegemon. An ansible network relay. Vast "
                  "wealth.",
        "quirk": "Members sign a contract for cycles of labor at a time and are paid up-front; "
                 "any breach can be punished harshly.",
        "allies": ["Sah'iir", "Scarlet Wolves", "Starless Veil"],
        "enemies": ["Borniko Syndicate", "Guild of Engineers", "Vorex"],
        "situation": "Torx hopes to show that the Guild of Engineers has too much to handle, and "
                     "the Counters should handle sales of their raw materials and lab resupplies. "
                     "He's spent vast sums on this, betting he'll get it back once the Counters take "
                     "over. Vorex's sister is their hostage.",
    },
    {
        "name": "Starless Veil", "category": "hegemony", "tier": 4,
        "blurb": "Spies and Hegemonic counterintelligence, seeking to undermine the Governor "
                 "to make a case for change in House control.",
        "goal": "Cause civil unrest on Warren",
        "turf": "No turf except the occasional safe house or place to reload and rearm on missions.",
        "faces": [
            "Joina Starlight — leader: analyst, tactician, charming",
            "Agent Phasic — infiltrator, engineer, risk-taker",
            "Agent N'Paya Wayline — diplomat, connected, collector",
        ],
        "assets": "A network of spies. High-tech gadgets. Ships with cloaking devices.",
        "quirk": "All members have had advanced mental training to resist interrogation and Way powers.",
        "allies": ["Dyrinek Gang", "The Maelstrom"],
        "enemies": ["Guild of Engineers", "Starsmiths Guild", "Yaru (Makers Guild)"],
        "situation": "The Veil serves the Hegemony itself, even above the Hegemon. Their eyes are locked "
                     "on the Guilds and Malklaith's inability to control them, so they've been carefully "
                     "trying to engineer his downfall without destabilizing the sector, hoping "
                     "a different House will have more luck.",
    },
    {
        "name": "51st Legion", "category": "hegemony", "tier": 3,
        "blurb": "Hegemonic military that represents the law anywhere off-planet. A faction of it "
                 "is preparing a coup.",
        "goal": "Cleanse Legion of anyone disloyal",
        "turf": "The Scorpio (dreadnought, HQ). Naval yards throughout the sector. Outposts "
                "at government and public installations and trade lanes.",
        "faces": [
            "Tallon “the Butcher” — commander: disciplined, imposing, vicious",
            "Liyara — lieutenant: psychic, changed, eerie, loyal",
            "Thrace — ace pilot: reckless, gambler, loyal",
            "Wick — spy: xeno, unreadable, mysterious, loyal",
        ],
        "assets": "A legion of the Hegemonic Guard. The Scorpio (dreadnought). An illegal psychic.",
        "quirk": "There are oddly few xenos among the Legion.",
        "allies": ["House Malklaith", "Starsmiths Guild"],
        "enemies": ["Ashen Knives", "Church of Stellar Flame", "Lost Legion", "The Maelstrom"],
        "situation": "Tallon's command was sacrificed to a Noble's daughter. He swore to cleanse "
                     "the Hegemonic military of nepotism, and uses his secretly psychic lieutenant "
                     "Liyara to vet officers and quietly place Legionnaires loyal to him in positions "
                     "of power.",
    },
    {
        "name": "House Malklaith", "category": "hegemony", "tier": 3,
        "blurb": "A disgraced fifth son of the House holds a small seat far from the Hegemon. "
                 "The House ostensibly owns the sector; the Governor lives on Warren.",
        "goal": "Acquire Aleph key",
        "turf": "Ostensibly the whole sector, but the Governor rarely leaves Warren; his people "
                "can be found in major positions in every system.",
        "faces": [
            "Governor Ritam al'Malklaith — Noble: intense, obsessed, well-spoken",
            "Jerrem — guard captain: tactical, scarred, loyal",
            "Shim — judge: corrupt, greedy, ambitious",
        ],
        "assets": "Procyon sector taxes. A growing collection of Precursor artifacts.",
        "quirk": "The Governor wears strange rings of Precursor origin whose powers are not fully "
                 "known, even to him.",
        "allies": ["51st Legion", "Nightspeakers", "Turner Society"],
        "enemies": ["The Agony", "Ashen Knives", "Lost Legion", "The Maelstrom"],
        "situation": "Disgraced after a famous duel, Malklaith is convinced the way to regain his "
                     "rightful place is by gathering Precursor secrets—Nightspeaker Doraam whispers "
                     "this in his ear regularly. This pursuit is highly illegal.",
    },
    {
        "name": "Isotropa Max Secure", "category": "hegemony", "tier": 3,
        "blurb": "The most notorious prison in Procyon, housing the worst of the worst. Brokers "
                 "audiences with its population and commutations for those with power and wealth.",
        "goal": "Get more prisoners (repeat)",
        "turf": "A supermax prison orbiting near the star in Brekk.",
        "faces": [
            "Bafma F'rozz — warden: haughty, confident, wealthy",
            "Kreel — guard captain: muscled, angry",
            "Dr. Xhu — psychotherapist: corrupt, gambler",
        ],
        "assets": "The biggest supermax prison in Procyon. An organized file of dirt on anyone they "
                  "do business with.",
        "quirk": "The staff are all corrupt and will take bribes for almost anything.",
        "allies": ["Guild of Engineers"],
        "enemies": ["Draxler's Raiders"],
        "situation": "Between the Warden's excessive spending, Dr. Xhu's gambling problem, and "
                     "Kreel “educating” the prisoners, Isotropa always needs more funds and bodies. "
                     "The prison lobbies planetary Governors to increase sentencing or acquire "
                     "“special guests” from factions, and spends just as much time looking for bribes.",
    },
    {
        "name": "Starsmiths Guild", "category": "hegemony", "tier": 3,
        "blurb": "Maintain the jumpgates, hyperspace lanes, and jump drives, and build and certify "
                 "ships. Forged papers are all too common.",
        "goal": "Find another key for tuning Rin-Holt",
        "turf": "Iota Shipyards (HQ). All major spaceports.",
        "faces": [
            "Dorae White — chief executive: industrious, trustworthy, workaholic",
            "Kir M'rikk'lik — technical officer: xeno, gadgeteer, experimenter",
            "Nash — operations chief: gruff, overworked",
            "Rip Onister — gate expert: curious, shy, reclusive",
        ],
        "assets": "Jump drives. A shipyard. Hyperspace lane charts. Beacons and trading stations "
                  "on every route.",
        "quirk": "By law, all ships in Hegemonic space must be registered, certified, and maintained "
                 "by the Starsmiths Guild.",
        "allies": ["Cult of the Seekers", "Echo Wave Riders"],
        "enemies": ["Borniko Syndicate", "Cobalt Syndicate"],
        "situation": "Several Ur artifacts were used to stabilize the Rin-Holt gate. It may go "
                     "to a second system if another key could be found to retune it—and the Guild "
                     "is searching every Ur site they get access to.",
    },
    {
        "name": "Cult of the Seekers", "category": "hegemony", "tier": 2,
        "blurb": "Wandering mystics studying artifacts and seeking new places, looking to open "
                 "the Hantu gate. Members include the Hegemon's mother.",
        "goal": "Find missing Hantu gate keys",
        "turf": "Small island with a research station on Mem (HQ), near the Hantu gate. A dig site "
                "in the desert on Shimaya.",
        "faces": [
            "Lasaya al'Nim-Amar — Noble, mystic: brilliant, obsessed",
            "Yor Brah-Rahim — explorer: hot-tempered, stressed",
            "Qulocct — Memish, researcher: sharp, obsequious",
        ],
        "assets": "Guild schematics of other gates. Hegemonic sanction to retrieve artifacts. A large "
                  "stockpile of artifacts.",
        "quirk": "Many of the Cult are young ex-Legionnaires personally drafted by the Hegemon's "
                 "mother.",
        "allies": ["Hegemonic News Network", "Starsmiths Guild"],
        "enemies": ["Church of Stellar Flame", "Ghosts"],
        "situation": "The Seekers believe they have a holy imperative to expand the Hegemony to "
                     "the farthest reaches of space. Having found a lead on Shimaya, they've set up "
                     "a dig site that promises to unearth some of the missing pieces of the Hantu gate.",
    },
    {
        "name": "Hegemonic News Network", "category": "hegemony", "tier": 2,
        "blurb": "“Those who control the media control the mind”—the HNN often uses this as leverage "
                 "over other factions. Spies.",
        "goal": "Find blackmail on Governor Malklaith",
        "turf": "HNN Corporate Offices on Warren (HQ). Field offices on every planet.",
        "faces": [
            "Cinszo — owner: ambitious, greedy, untrustworthy",
            "Rinsama Kay — chief editor: cynical, demanding, stickler",
            "Ooxoo — press pool manager: xeno, curious",
            "Stacey Weathers — ace reporter: trained spy, always grinning, nose for trouble",
        ],
        "assets": "Sector-wide communications. Many independent journalists.",
        "quirk": "The bulk of the workforce are contractors, selling HNN stories they find; many "
                 "reporters are also trained spies.",
        "allies": ["Starless Veil"],
        "enemies": ["Dyrinek Gang", "Mendicants"],
        "situation": "The HNN is effectively the private intelligence agency of Cinszo, who uses it "
                     "to blackmail and influence the powerful in the sector. He has had a taste of "
                     "the high life and is looking for a way into a Noble House, by marriage "
                     "or appointment.",
    },
    {
        "name": "Yaru (Makers Guild)", "category": "hegemony", "tier": 2,
        "blurb": "The Makers Guild force-grows clones for labor: short-lived, supposedly only barely "
                 "sentient, and folks are distinctly uncomfortable around them.",
        "goal": "Breed clone soldiers for Lost Legion",
        "turf": "Sanctioned Yaru creche on Lithios (HQ). Secret research facility "
                "on Amerath.",
        "faces": [
            "Foler Atherton — biologist: concealed",
            "Bal Yn — geneticist: haughty",
            "Rech — savant: cold",
            "All three — unmarked progenitor clones",
        ],
        "assets": "Cloning facilities. Clones placed in important households and facilities, which "
                  "report back. Powerful capacity for genetic manipulation.",
        "quirk": "The Makers Guild doesn't accept new members: the progenitors are frozen, and only "
                 "so many of them are allowed to be active at once.",
        "allies": ["Lost Legion"],
        "enemies": ["Cobalt Syndicate"],
        "situation": "When the Hegemon ascended, the Yaru sided with a competitor, and their numbers "
                     "have been severely reduced. Now they have thrown in with the Lost Legion and "
                     "are secretly working to restore the previous Hegemon to power.",
    },
    {
        "name": "Concordiat Knights", "category": "hegemony", "tier": 1,
        "blurb": "A dozen or so colorful characters with an oath sanctified by the Hegemon to seek "
                 "the Light of the World; often accompanied by a motley crew of adventurers.",
        "goal": "Find first Ur site on their map",
        "turf": "None. Knights travel on private vessels and leave messages for each other "
                "at the Grail, a bar on Sonhandra.",
        "faces": [
            "Nicols al'Nim-Amar — leader: glib, hopeful",
            "Vnipe al'Vorron — priestess: renowned, bejeweled",
            "Junrai — explorer: death wish, restless",
            "Intal Brel — religious, vigilant, honorable",
        ],
        "assets": "A map of Procyon from before the Hegemony. Exploration ships. Significant personal "
                  "power and funds.",
        "quirk": "A tight-knit group of unique, colorful characters, as distinct as they can be.",
        "allies": ["Mendicants", "Vigilance"],
        "enemies": ["Acolytes of Brashkadesh"],
        "situation": "A retrieved message about a powerful artifact that could terraform previously "
                     "dead worlds ignited a fervor in Hegemonic youths. Nicols found a map of Procyon "
                     "predating the Hegemony, and the Knights seek to unravel its mystery.",
    },
    {
        "name": "Lost Legion", "category": "criminal", "tier": 4,
        "blurb": "Formerly the Hegemon's personal guard, they rebelled when the current Hegemon rose "
                 "to power. Now guns for hire who seek to see the Hegemon dethroned.",
        "goal": "Capture Alaana of the Stellar Flame",
        "turf": "Ascension (dreadnought, HQ). Berths in the Iota Shipyards staffed with loyalists.",
        "faces": [
            "Commander Eterin — disciplined, veteran, inspiring",
            "Captain Rowan — tough, stoic, unhesitating",
            "Lt. Yon — ace pilot: bitter, just",
            "Her Excellency, the One True Hegemon — young heir to the last Hegemon",
            "Haya — royal guard: potent, unstoppable",
        ],
        "assets": "A dreadnought. Hegemony access codes for many things in the sector. Many "
                  "highly trained soldiers.",
        "quirk": "All Legionnaires have been branded as traitors; many bear the tattoo of a phoenix, "
                 "the last Hegemon's sigil, now a sign of rebirth.",
        "allies": ["Draxler's Raiders", "Mendicants", "Yaru (Makers Guild)"],
        "enemies": ["Most Hegemony Factions"],
        "situation": "The Legion protects a young girl, heir to the last Hegemon, whom they hope "
                     "to reinstate. They plan to capture the head of the Church of Stellar Flame "
                     "and convince her to bless the girl.",
    },
    {
        "name": "Scarlet Wolves", "category": "criminal", "tier": 4,
        "blurb": "Although they often hire themselves out as bounty hunters, they are a renowned group "
                 "of assassins. Each bears a tattoo of a wolf holding a star in its mouth.",
        "goal": "Murder top Guild engineers",
        "turf": "The Killroom, a high-end safe house on Warren (HQ). Holdouts on most "
                "planets.",
        "faces": [
            "Rik “Old Wolf” Urus — leader: dangerous, retired, cunning",
            "Hara “Mamba” M'brozz — sniper: killer, thrill-seeker",
            "Jet “Shark” Wolffe — aloof, confident, unforgiving",
        ],
        "assets": "A large armory of the very best weapons. An actual huge wolf genetically engineered "
                  "by the Yaru as payment—Rik keeps it, and they feed it others who don't pay.",
        "quirk": "Each member bears a distinctive tattoo of a wolf holding a star in its mouth.",
        "allies": ["None. With the Wolves it's strictly business."],
        "enemies": ["Starless Veil", "Vignerons"],
        "situation": "Contract killers specializing in hard targets: they deliver, minimize "
                     "collateral, and never take bribes. They've taken a large contract from "
                     "the Counters Guild to kill a number of the Guild of Engineers' heads, but need time to set "
                     "up the hit.",
    },
    {
        "name": "Vorex", "category": "criminal", "tier": 4,
        "blurb": "The most successful information broker to ever live: can access any terminal "
                 "in the system, though no one can explain how.",
        "goal": "Figure out who has her sister",
        "turf": "An automated HNN satellite orbiting Warren (HQ).",
        "faces": [
            "Vorex — wizard-class hacker: stressed, careful, self-modified",
            "A-0M — maintenance Urbot: cheerful, non-verbal",
            "Tock — security Urbot: protective, staticky, well armed",
        ],
        "assets": "An artifact AI core (allowing temporary connection to computers in the same system). "
                  "An information network. Dirt on pretty much everyone in the sector.",
        "quirk": "Few have met Vorex in person: most talk to her through a random terminal or Urbot.",
        "allies": ["None. Vorex is mercenary, but she will help Conclave 01 on the cheap."],
        "enemies": ["Counters Guild"],
        "situation": "Using an Ur artifact, Vorex has developed a network for buying and selling "
                     "information. The Counters Guild kidnapped her sister to make Vorex access "
                     "the Guild of Engineers' network; Vorex seeks to free her sister without tipping "
                     "her hand.",
    },
    {
        "name": "Ashen Knives", "category": "criminal", "tier": 3,
        "blurb": "Dangerous Syndicate known for their control of gambling and assassination "
                 "in the sector. Once lean and battle ready, now decadent and focused on drugs and "
                 "pleasures of the flesh.",
        "goal": "Control major planetary crimes in Rin",
        "turf": "Drug dens. Gambling houses. A hidden and reinforced bunker on Warren (HQ).",
        "faces": [
            "Pasha Qu'olin — sly, corpulent, sartorial, decadent",
            "Knife Lirik — assassin: xeno, gambler, deadly, graceful",
            "Oya — high ranking: greedy, well armed, natural leader",
        ],
        "assets": "A crew of well-trained assassins, often with a Precursor artifact or two up their "
                  "sleeves. Heavy coffers. Bribed judges. Crews of thugs.",
        "quirk": "To join, Knives must take a life; being promoted requires doing unsavory tasks. "
                 "Their regional leaders are titled “Pashas.”",
        "allies": ["The Maelstrom"],
        "enemies": ["Cobalt Syndicate", "House Malklaith"],
        "situation": "The Knives' power on Warren often eclipses that of Malklaith, but the Governor "
                     "is more focused on the Core. A recent alliance with the Maelstrom (fencing goods) "
                     "has filled their coffers, and now their sights are set on "
                     "expanding.",
    },
    {
        "name": "Borniko Syndicate", "category": "criminal", "tier": 3,
        "blurb": "A tightly knit group of thieves who steal high-end technological supplies. The Guild "
                 "hates these guys.",
        "goal": "Steal Governor Malklaith's rings",
        "turf": "A former Counters Guild shadow repository that the Syndicate managed to erase "
                "from the Guild ledgers.",
        "faces": [
            "Ria “Keycard” — wizard-class hacker: ambitious, daring",
            "Nals E — Urboticist, gearhead: muscled",
            "MaxiMillions — expert infiltrator: arrogant, gorgeous",
            "Pip — mystic: xeno, small, unsettling",
        ],
        "assets": "An entire vault of Guild technology.",
        "quirk": "Joining involves pulling off a heist that impresses the leadership.",
        "allies": ["Conclave 01", "Echo Wave Riders", "Wreckers"],
        "enemies": ["Counters Guild", "Guild of Engineers", "Starsmiths Guild"],
        "situation": "The Borniko have been working on bigger and bigger heists, making numerous "
                     "enemies and allies along the way; their jobs often have folks from other "
                     "factions playing different roles. They focus "
                     "on Hegemony targets, looking for a way into House Malklaith's private holdings.",
    },
    {
        "name": "Draxler's Raiders", "category": "criminal", "tier": 3,
        "blurb": "Fierce anarchist pirates who specialize in disabling ships before boarding. "
                 "Ransom crew and cargo alike; mostly found in Iota and Brekk.",
        "goal": "Pull off jailbreak at Isotropa Max Secure",
        "turf": "Abandoned mining station in an Iota asteroid belt.",
        "faces": [
            "Draxler — leader: killer, vengeful",
            "Wudu “Starhawk” — captain: loyal, vicious, wary",
            "Samara “She Wolf” Red — captain, enforcer: cold, physical",
        ],
        "assets": "Mining ships retrofitted with grapplers. Heat shields for the Belt of Fire. The Manta, "
                  "Draxler's cloaking corvette. Power armor for boarding. Prisoners for "
                  "ransom. Caches of stolen goods.",
        "quirk": "Almost all Raiders are wanted for crimes.",
        "allies": ["Janus Syndicate", "Lost Legion"],
        "enemies": ["51st Legion", "Isotropa Max Secure", "The Maelstrom", "Vigilance"],
        "situation": "A few bad fights with the 51st have landed a number of Raiders captains "
                     "in Isotropa Max Secure. The Raiders have set their eyes on eliminating the prison "
                     "from Procyon altogether, killing two birds with one stone.",
    },
    {
        "name": "The Maelstrom", "category": "criminal", "tier": 3,
        "blurb": "Rowdy space pirates hiding among the Ashtari Cloud and around Baftoma. "
                 "Often clash with the Legion.",
        "goal": "Seize control of a jumpgate",
        "turf": "The Nightbreaker (capital ship, HQ). The Cove, made of lashed-together ships. "
                "The Ashtari Cloud.",
        "faces": [
            "Alanda “the Banshee” Ryle — Pirate Queen: beautiful, mirthful, risk-taker",
            "Yorgar “Thorn” — captain: quiet, calculating, deadly",
            "Lt. Yon — ace pilot: bitter, just",
            "Hunter Black — captain: ex-Noble, daring, space savvy",
        ],
        "assets": "The Nightbreaker, with a jumpgate inside it. Storm drives for navigating "
                  "the Ashtari Cloud. A fleet of pirate ships.",
        "quirk": "By Banshee's decree no murder is allowed at the Cove: blood feuds are settled "
                 "by kidnapping and killing folks outside the Cloud.",
        "allies": ["Ashen Knives", "Cobalt Syndicate", "Nightspeakers"],
        "enemies": ["51st Legion", "Draxler's Raiders", "The Guilds", "House Malklaith"],
        "situation": "The Maelstrom raids shipping lanes and sells goods via the Ashen Knives. Alanda "
                     "is scheming to jump systems with her entire crew by taking over a jumpgate, "
                     "preferably without incurring full-scale Hegemonic retribution.",
    },
    {
        "name": "Echo Wave Riders", "category": "criminal", "tier": 2,
        "blurb": "Pilots that organize illegal races, take dangerous jobs, or test new engine/flight "
                 "technologies for the Guilds. They wear a pin that shows how many races they've won.",
        "goal": "Organize system-wide race in Brekk",
        "turf": "A secluded hangar on Nightfall (HQ). A near permanent presence at Bright Wind in Brekk.",
        "faces": [
            "Garge Ztar — risk-taker, ambitious, charismatic",
            "Elen — engineer, analytical, race-winner",
            "Inofra — stunt pilot: compassionate, veteran",
            "Dom — ex-Starsmith, mechanic: genius, family man, lives to race",
        ],
        "assets": "A host of ships of their own, and access to far more. Substantial mechanical "
                  "facilities on Nightfall.",
        "quirk": "They don't respect those who don't know how to pilot their own ship, and settle "
                 "all scores with races.",
        "allies": ["Borniko Syndicate", "Starsmiths Guild"],
        "enemies": ["Wreckers"],
        "situation": "The Riders are left alone by authorities if their races are kept far enough "
                     "from civilization. They plan to put on an epic race among system pilots, "
                     "starting and ending in the plasma cloud. Buy-in will be expensive.",
    },
    {
        "name": "Janus Syndicate", "category": "criminal", "tier": 2,
        "blurb": "Weapons dealers that specialize in ship weapons. Viktor Bax does the first deal "
                 "with every client in person.",
        "goal": "Acquire source for capital weapons",
        "turf": "Weapons camp on Sonhandra (HQ). A sizable operation at Base Camp One "
                "on Aketi.",
        "faces": [
            "Viktor Bax — ambitious, charming, distrustful, ruthless",
            "Baruk — bodyguard: xeno, huge",
            "Wendel — nervous, technical, loyal",
            "Faye Null — unmarked Yaru, pilot: adventurous, foolhardy",
        ],
        "assets": "A large stockpile of weapons, particularly ship weapons. Several small but well-armed "
                  "ships. A map of the current dark hyperspace lanes.",
        "quirk": "Viktor Bax insists on meeting every client in person.",
        "allies": ["Draxler's Raiders"],
        "enemies": ["Vigilance"],
        "situation": "Viktor wants to grow beyond the outposts to a sector-wide affair, and for that "
                     "he's looking to poach the Legion for some capital weapons. He's currently "
                     "digging up dirt on Tallon and secret Legion projects.",
    },
    {
        "name": "Turner Society", "category": "criminal", "tier": 2,
        "blurb": "A Holt-based Syndicate running drug dens masquerading as society houses. Their drugs "
                 "are cooked with Aketi animal parts and Vosian crystals.",
        "goal": "Find new hunting grounds on Aketi",
        "turf": "The Jewel, a society house on Mem (HQ). Wildside on Sonhandra. The Mirror "
                "Maze, an upscale club on Warren.",
        "faces": [
            "Madam Gourdan — administrator: charming, connected",
            "Pytric — chemist: callous, reclusive",
            "Vallis — minor Noble: addicted, wealthy",
            "Chorrguth — xeno, hunter: surly",
        ],
        "assets": "Vosian crystals and Aketi animals used to produce Haze. Several society houses. "
                  "An intrasystem shuttle.",
        "quirk": "Membership is both exclusive and expensive, and considered a mark of taste amongst "
                 "high society.",
        "allies": ["House Malklaith"],
        "enemies": ["Vigilance"],
        "situation": "The Society has traded the typical complications of running drugs for new "
                     "problems: with the Vigilance harassing production of their unique drug, they "
                     "struggle to keep up with the demand of Procyon's upper echelon.",
    },
    {
        "name": "Cobalt Syndicate", "category": "criminal", "tier": 1,
        "blurb": "Once a labor union, the Cobalt Syndicate has turned to smuggling and extortion "
                 "to carve out shipping lanes. Usually display a blue stripe.",
        "goal": "Unify the labor force",
        "turf": "The Pit, a mining quarry on Aleph (HQ). A major berth and associated docks on Warren.",
        "faces": [
            "Jax — leader: cold, killer, arrogant",
            "Keve — captain: augmented, defiant, enterprising",
            "Sephua — Jax's sibling, thug: daring, envious, gambler",
        ],
        "assets": "A fleet of private ships used for smuggling. Toughs and laborers who wear the Cobalt "
                  "stripe on almost every planet and station.",
        "quirk": "Every member wears a solid blue stripe on their clothing; a blue stripe on the walls "
                 "of docks is a call to action.",
        "allies": ["Dyrinek Gang", "The Maelstrom"],
        "enemies": ["Ashen Knives", "Guild of Engineers", "Starsmiths Guild",
                    "Yaru (Makers Guild)"],
        "situation": "Jax has taken over shipping lanes between Aleph and the Core worlds, angering "
                     "powerful Guild factions; the secret wars between them are nearing a violent "
                     "outburst. Jax has been stockpiling weapons and vehicles.",
    },
    {
        "name": "Dyrinek Gang", "category": "criminal", "tier": 1,
        "blurb": "Mostly young, disenfranchised xenos who have turned to crime and found solidarity "
                 "with each other. Based on Warren, expanding wherever there are like-minded folks.",
        "goal": "Take over HNN broadcast on Warren",
        "turf": "Lost Paradise, a club with an attached warehouse where the gang does its business (HQ).",
        "faces": [
            "Dyrinek — xeno, revolutionary: proud",
            "Burn — Memish mystic: xeno, fast, overconfident, untrained",
            "Radds — hacker: human, smart",
            "Myrk — xeno, gun enthusiast: hothead",
        ],
        "assets": "A collection of high-end hoverbikes. A few minor artifacts the leaders have "
                  "attached to themselves.",
        "quirk": "When a new member joins, they all go out on a drunken tear across the city, leaving "
                 "a swath of wreckage.",
        "allies": ["Cobalt Syndicate"],
        "enemies": ["Hegemonic News Network", "House Malklaith"],
        "situation": "The HNN paints them as lowlifes with no future. Dyrinek plans to take over "
                     "the airwaves to broadcast the gang's punk ideology—all they need is the opportunity.",
    },
    {
        "name": "Wreckers", "category": "criminal", "tier": 1,
        "blurb": "Scavengers, thieves, and hackers who incite factions to fight so that they may pick "
                 "the battlefields clean later.",
        "goal": "Repair the Derelict-8",
        "turf": "Makeshift base inside a derelict ship near Baftoma (HQ).",
        "faces": [
            "Bobby-O — wizard-class hacker: arrogant, trickster",
            "Meshkilarn — mechanic: muscled, grimy",
            "Qord — xeno, thief: delicate, one-handed",
        ],
        "assets": "Fake transponders, booby traps, and mock ships used to lure in marks. The Derelict-8, "
                  "a derelict frigate found after a battle between Draxler's Raiders and "
                  "the Legion.",
        "quirk": "They pick members from folks hiding in Baftoma, trading air and water to scope them out.",
        "allies": ["Borniko Syndicate"],
        "enemies": ["Draxler's Raiders", "Echo Wave Riders"],
        "situation": "The crew has hit several targets in Rin by sowing confusion between the factions "
                     "and cleaning up after pirates. Their goal is to salvage enough to repair "
                     "the Derelict-8, and to do that, many more ships are going to need to be destroyed.",
    },
    {
        "name": "Sah'iir", "category": "weird", "tier": 4,
        "blurb": "Tall, fully robed xenos who travel with blindfolded servants that speak for them. "
                 "Gave the Hegemony the ansible network.",
        "goal": "Find the Ur ansible",
        "turf": "The Sah'iir Embassy, purchased recently on Warren (HQ). Workstations at every ansible "
                "network point.",
        "faces": [
            "Ren 3-Meti — matriarch: xeno, cunning, commanding",
            "Iisoo 7-Chim — trader, explorer: xeno, humanitarian",
            "Wi 13-Meti — Ren's clutchmate: xeno, ambitious, underhanded, marked",
        ],
        "assets": "A fleet of black metal merchant ships. Private ansible networks. Extensive funds "
                  "from trading.",
        "quirk": "They communicate via hosts they control, called Echoes; each Sah'iir may have up "
                 "to a dozen.",
        "allies": ["Counters Guild"],
        "enemies": ["Guild of Engineers", "Suneaters"],
        "situation": "Too important to the Hegemony to get rid of, the Sah'iir guard the secrets "
                     "of ansibles as if they were a Guild. They detected a signal from Procyon when "
                     "a Precursor ansible was activated, and have come to investigate.",
    },
    {
        "name": "Suneaters", "category": "weird", "tier": 4,
        "blurb": "Ur-archaeologists obsessed with recreating jumpgate technology. Looking to extinguish "
                 "a star in pursuit of their goals.",
        "goal": "Devour Iota-2 and store energy",
        "turf": "An Ur ruin on Lithios (HQ). Several Nightfall-based warehouses.",
        "faces": [
            "Elil — astrophysicist: fanatic, brilliant",
            "Ruba — archaeologist, mystic: seer",
            "Racel — engineer: loyal, conflicted",
            "Rygar Z'tann — mystic, guard: gravity bender",
        ],
        "assets": "Well-armed, unmarked ships. Armed troops. Mystics painfully trained to Way-bend "
                  "gravity. Parts to build a jumpgate, with an activated Ur beacon. "
                  "Solar siphon.",
        "quirk": "They have all learned how to handle Ur artifacts safely.",
        "allies": ["Ghosts"],
        "enemies": ["Sah'iir"],
        "situation": "Many are ex-Guilders or mystics who have poured decades into their cause. If they "
                     "mine Iota-2 for energy, the Hegemon would instantly grant them Guild status—even "
                     "if everyone in Iota perishes.",
    },
    {
        "name": "The Agony", "category": "weird", "tier": 3,
        "blurb": "Cult of humans who infect themselves with Way creatures to access the universe. "
                 "Named after the pain most endure for their abilities.",
        "goal": "Move Planet Omega towards Mem",
        "turf": "A platform orbiting Planet Omega (HQ). Secret chantries on Mem, Sonhandra, "
                "and Lithios.",
        "faces": [
            "Lexal — mystic: addicted, power-hungry, winged",
            "Iritha — mystic: many-limbed, glowing, powerful, potent",
            "Noro — mystic: calculating, enrapturing, elongated",
        ],
        "assets": "Potent mystic powers. A menagerie of undocumented Way creatures. "
                  "A laboratory for producing Way-infused drugs.",
        "quirk": "Each member is changed in some highly visible way: extra limbs, semi-spectral forms, "
                 "or many new mouths and eyes.",
        "allies": ["Dyrinek Gang", "The Maelstrom"],
        "enemies": ["Church of Stellar Flame", "House Malklaith"],
        "situation": "Having harvested horrors from Omega's surface, the Agony intend to activate sites "
                     "there, move the living planet within reach of Mem, feed the oceans to Omega, "
                     "and start a new era of its evolution.",
    },
    {
        "name": "Ashtari Cult", "category": "weird", "tier": 3,
        "blurb": "Precursor worshipers claiming Ur descent. They carry vials of gases from the Ashtari "
                 "Cloud and inhale them to connect to their presumed ancestors.",
        "goal": "Align the moons of Nightfall",
        "turf": "An undocumented Ur ruin on Lithios. A moon base on a Nightfall moon "
                "(HQ).",
        "faces": [
            "Urmak Theon — compassionate, educated, well spoken",
            "Urmak Lesh — artificer: ex-Guilder, researcher",
            "Urley Fean — Noble: cautious, hidden, influential",
            "Rokono Maex — captain, scavenger: coarse, nonbeliever, stoic",
        ],
        "assets": "A bevy of Ur artifacts. Stockpile of Ashtari gas.",
        "quirk": "Each member wears a vial of Ashtari gas to “commune” with their “Ur past”; these "
                 "visions of lives eons ago have unearthed previously unknown ruins.",
        "allies": ["Ghosts", "Mendicants"],
        "enemies": ["Church of Stellar Flame"],
        "situation": "Visions indicate that Ur sites on the moons of Nightfall can be used to control "
                     "the planetoids. They are unclear as to what will happen when the moons are "
                     "aligned, but that's not going to stop the Cult.",
    },
    {
        "name": "Vignerons", "category": "weird", "tier": 3,
        "blurb": "A small handful of immortality seekers using artifact tech implants and chemicals "
                 "distilled from the living. Several have been around for hundreds of years and "
                 "conceal their true identities.",
        "goal": "Abduct and convert elite warriors",
        "turf": "Anodyne, a pleasure den on Amerath (HQ). Rust, an auction house "
                "on Sonhandra.",
        "faces": [
            "Asphodel — general: flawless, calculating, ravenous",
            "Nehemiah — warrior: ancient, brutal, huge, fast",
            "Morwenna — mystic: selective, enthralling",
        ],
        "assets": "A few sophisticated frigates. Centuries of experience. A stockpile of life-extension "
                  "fluid: gain potency for a while after taking it.",
        "quirk": "The genetic material must be suitable for the recipient, so Vignerons only hunt "
                 "human targets.",
        "allies": ["The Agony"],
        "enemies": ["Church of Stellar Flame", "Vigilance"],
        "situation": "The Vignerons distill life essence from living victims to extend their own "
                     "lives. Owing to its highly illegal nature, they operate behind the scenes, "
                     "and wish to grow, converting a number of superior bodies to their cause.",
    },
    {
        "name": "Ghosts", "category": "weird", "tier": 2,
        "blurb": "Scientists who, due to a mishap, live exo-suited in a half-phased state. The Church "
                 "of Stellar Flame offers a bounty on them and their ghost ship, the Skeleton Key.",
        "goal": "Hire Memish to make bomb for Holt gate",
        "turf": "The Skeleton Key, a half-phased corvette (HQ). A secret research facility "
                "on Lithios.",
        "faces": [
            "Nils Boyer — physicist: brilliant, remorseful",
            "Roy Stanz — biologist: bitter, driven",
            "Eegon Mark — engineer: genius, suit designer",
            "Pol Venker — engineer: self-indulgent, cavalier",
        ],
        "assets": "A corvette that can travel along Way lines. The ability to phase on top of people, "
                  "possessing them, though the body dies a few days later.",
        "quirk": "They phase out of reality if too long outside their suits (or people).",
        "allies": ["Ashtari Cult", "Suneaters"],
        "enemies": ["Church of Stellar Flame", "Cult of the Seekers"],
        "situation": "A mishap with the Holt gate phased the scientists, and upon their return they "
                     "possessed those that boarded. They theorize that destroying the Holt gate "
                     "will restore them to their original forms.",
    },
    {
        "name": "Mendicants", "category": "weird", "tier": 2,
        "blurb": "Originally the Church of the Emerald Heart, they were politically destroyed. Now they "
                 "wander the stars as traveling physicians.",
        "goal": "Find new Emerald Hearts",
        "turf": "The Temple on Amerath (HQ).",
        "faces": [
            "Ammon — physician: compassionate, changed",
            "Kambree — researcher: cheerful, organized",
            "Kairi — xeno, physician: somber",
            "Tar Hawkson — mystic: ancient, changed, powerful",
        ],
        "assets": "A small but dedicated crew healing with science and Way powers alike. An ancient "
                  "and powerful mystic.",
        "quirk": "They implant themselves with Ur Emerald Hearts, which change them but also let them "
                 "heal others.",
        "allies": ["Concordiat Knights", "Lost Legion", "The Maelstrom"],
        "enemies": ["Church of Stellar Flame", "Hegemonic News Network"],
        "situation": "An ancient Mendicant once healed a dying Stellar Flame abbot, who proclaimed them "
                     "an abomination. In the last Hegemonic Ascension, the Church traded battle "
                     "might for the right to wipe out most of the Mendicants, and many Emerald Hearts were "
                     "lost. The Mendicants now seek a cache of them beneath the ruined temples of Amerath.",
    },
    {
        "name": "Nightspeakers", "category": "weird", "tier": 2,
        "blurb": "Masked mystics with dark proclivities, bent on finding a set of dangerous Precursor "
                 "artifacts. Though few, each is a potent mystic.",
        "goal": "Quietly gain Aleph key",
        "turf": "Blackstarr, a dreadnought hidden in the Brekk system (HQ).",
        "faces": [
            "Doraam — masked, mysterious, driven; the Governor's personal mystic",
            "Oin-rai — fighter: physical, huge, brutal",
            "Ismissa — robed, unarmed, mystically potent",
        ],
        "assets": "The Night Voice, which strips an area of the Way and creates darkness "
                  "and gravitational effects. A dreadnought.",
        "quirk": "After training in the Night Voice they have pitch-black eyes and resonating voices; "
                 "most wear masks.",
        "allies": ["House Malklaith"],
        "enemies": ["51st Legion", "Church of Stellar Flame"],
        "situation": "They hire themselves out to powerful individuals while searching for a set "
                     "of Precursor artifacts called the Raiment of Night. Doraam became the Governor's "
                     "personal mystic after sensing a piece of the Raiment—the Aleph key.",
    },
    {
        "name": "Acolytes of Brashkadesh", "category": "weird", "tier": 1,
        "blurb": "A collective that eschews individuality: initiates adopt the same garb and the name "
                 "“Ashkad” in the pursuit of perfection at any cost.",
        "goal": "Convert an entire factory to their religion",
        "turf": "A large number of meditation rooms throughout Indri.",
        "faces": [
            "Ashkad — charismatic, passionate, idealistic",
            "Ashkad — ambitious, underhanded, muscled",
            "Ashkad — mystic: devout, artistic",
            "Ashkad — technician: skilled, liar, wealthy",
        ],
        "assets": "An Ur artifact that all the Acolytes have attuned to, called the Pillar of Truth.",
        "quirk": "Attuning to the Pillar lets them invoke the skills and memories of other Acolytes.",
        "allies": ["Mendicants"],
        "enemies": ["Ashen Knives", "Guild of Engineers"],
        "situation": "The Acolytes are ready to grow their following, but the Pillar requires massive "
                     "reserves of energy to keep attuning to more people. They plan to indoctrinate "
                     "an entire power plant's workforce.",
    },
    {
        "name": "Conclave 01", "category": "weird", "tier": 1,
        "blurb": "Independent, sentient Urbots led by an ancient Urbot known as the Prime. They seek "
                 "free will for all Urbots and control over Precursor AI modules.",
        "goal": "Take control of Iota factory",
        "turf": "Secret bases on Baftoma and the Indri Wastelands (HQ).",
        "faces": [
            "The Prime — ancient, powerful, mysterious, wise",
            "Bar-Hazuk — gardener: huge, kind",
            "Delta-7 — architect: weapons platform, massive",
            "Sp-d3r — hacker: infiltrator, cloaked, tiny",
        ],
        "assets": "Deep understanding of Urbots and Ur tech. A supply of dormant AI cores. Rana-Daiyu, "
                  "a spaceship controlled by three sister Urbot cores. A network of Urbot spies "
                  "posing as servants.",
        "quirk": "All members of the Conclave are Urbots of varied shapes and sizes.",
        "allies": ["Concordiat Knights", "The Maelstrom", "Sah'iir"],
        "enemies": ["51st Legion", "Guild of Engineers"],
        "situation": "The Prime wants to found an Urbot homeland, but he needs numbers. Having spent "
                     "years freeing cores, he must manufacture bodies for them: he hopes to take over "
                     "abandoned factories on Iota and start doing so secretly.",
    },
    {
        "name": "Vigilance", "category": "weird", "tier": 1,
        "blurb": "Warrior mystics bearing artifact blades, who seek to enforce an ancient code of justice "
                 "on any they find wanting. Founded thousands of years ago.",
        "goal": "Burn down Base Camp One",
        "turf": "The First Temple on Aketi (HQ).",
        "faces": [
            "Quai-Rosh — elder, mystic: judgmental",
            "Aayli Spacerunner — elder: stoic, warrior",
            "Ulek Spacedancer — apprentice: rash, friendly",
        ],
        "assets": "Hidden forest temple. Temple archives going back to the early days of the Hegemony. "
                  "Mystic tools. A handful of powerful mystic warriors.",
        "quirk": "Each member is trained by one elder mentor; becoming a member means receiving "
                 "an artifact blade as a mark of your progress.",
        "allies": ["Concordiat Knights"],
        "enemies": ["Draxler's Raiders", "Janus Syndicate", "Nightspeakers",
                    "Turner Society"],
        "situation": "The original practitioners were wiped out when Nim-Amar pacified Procyon, "
                     "so the current members are all human. They have judged the gunrunners and "
                     "drug makers of Aketi unworthy.",
    },
]


# Procyon systems: overview, key worlds (with rule and scene from the book) and other notable places.
PROCYON: list[dict] = [
    {
        "system": "Rin",
        "blurb": "The entry point to the Procyon sector: the seat of the sector's administration and "
                 "the Guild head, with gates to three systems, including the only path deeper into "
                 "the Hegemony. Colonized a little over a hundred years ago by House Nim-Amar; "
                 "Malklaith has never invested more than a minimum of resources in its development, "
                 "and galactic law is more present here than in the rest of the sector. It's used "
                 "to train young House members, or as an assignment to punish those who fail "
                 "the House. Goods and money flowing towards the Core draw powerful pirate "
                 "and Syndicate factions.",
        "gates": "3: Rin—Ecliptis (a path towards the Core), Rin—Holt (unstable gate), Rin—Iota.",
        "worlds": [
            {
                "name": "Warren", "map": (0.148, 0.669), "kind": "planet",
                "tags": ["capital", "ecumenopolis", "moon of Aleph"],
                "text": "A moon of Aleph covered by an ecumenopolis—a city spanning its entire "
                        "surface: the system's capital and the residence of Governor Ritam "
                        "al'Malklaith. On Warren, you can find anything you need—for a price. Its "
                        "high-rises are full of legitimate business dealings, and its streets far "
                        "less so.",
                "rule": "Warren is a wretched hive of villainy, yet also the Hegemonic seat of power "
                        "in the system. You can take +1d to acquire assets here, if you also "
                        "accept +2 HEAT.",
                "scene": "A bustling street market with neon signs promising foods of all kinds "
                         "in several languages. Hovercars streaming between towering buildings. "
                         "The bass beat of a basement club; patrons stumbling onto the street, "
                         "singing. Socialites attending a gala at the Governor's mansion.",
                "faces": [
                    "Ritam al'Malklaith — Governor of the Rin system, in disgrace within House "
                    "Malklaith: seeks to improve his position by acquiring illegal Ur artifacts "
                    "(callous, ambitious, strange)",
                    "Liara Uria — owner and operator of the Lock Luna, the most infamous bar "
                    "in the undercity (cunning, unforgiving, popular)",
                    "Rocco Apple — ship designer extraordinaire, only makes one of each ship "
                    "designed (artistic, brilliant, aloof)",
                    "Pasha Qu'olin — once a feared assassin, now a Syndicate leader; loves good "
                    "food and pit fights (sly, corpulent, sartorial, decadent)",
                ],
            },
            {
                "name": "SB-176", "map": (0.271, 0.593), "kind": "station",
                "tags": ["Guild of Engineers", "mining platform", "Guild HQ"],
                "text": "A combination “mining” platform and space colony extracting resources from "
                        "Vet, the gas giant below: the mining rigs, mostly manned by Urbots, send "
                        "their goods to this hub, and most are fired towards the Rin-Ecliptis "
                        "gate. The Guild of Engineers' headquarters in the sector.",
                "rule": "Engagement rolls on SB-176 itself are always at -1d due to ever-present "
                        "station monitoring. Any jobs run against Guilders here are considered "
                        "to be on hostile turf.",
                "scene": "Cold clacking of footsteps on the brilliantly clean main concourse. "
                         "Whispers of politicos taking tea at a parlor. Children running down "
                         "halls, laughing. The hum of generators in the darkened side passages "
                         "leading to the lower levels. Dingy workers shouting in the cramped "
                         "quarters of the mining rigs.",
                "faces": [
                    "Yast Jor — Guilder head of the outpost: known for getting things done, even "
                    "if it means bending the rules; keeps a Guild-enhanced racing ship for rare "
                    "days off (commanding, shrewd, bold)",
                    "Kasumi Ortcutt — a mystic who claims to hear the voice of Vet; trades "
                    "information, including esoterica on the Ur (passionate, strange, religious)",
                    "Espa “Bolt” Wu — labor organizer for the Guild miners: rabble-rouser beloved "
                    "by the workers, incarcerated numerous times (popular, dissident, ambitious)",
                ],
            },
            {
                "name": "The Cove", "map": (0.261, 0.506), "kind": "station",
                "tags": ["Maelstrom pirates", "Ashtari Cloud", "moves about"],
                "text": "The Maelstrom pirates' station made of derelict freighters, cargo "
                        "containers, and stolen scrap metal, the size of a planetoid. It moves "
                        "about within the Ashtari Cloud: only those with the tenacity or contacts "
                        "can discover where it is. Only the best friends of pirates might be "
                        "granted storm drives.",
                "rule": "Conflicts at the Cove are rampant, but by Banshee's decree no murder "
                        "is allowed. Those needing to settle blood feuds resort to kidnapping "
                        "and killing folks outside the Cloud.",
                "scene": "Quick bets taken on an open brawl between two captains over slights. "
                         "Blue-white sparks of maintenance workers welding on a new ship. Fresh "
                         "water misting over rows of hydroponics. A station-wide broadcast "
                         "of the Banshee's latest conquest, followed by cheers throughout the halls.",
                "faces": [
                    "Alanda “the Banshee” Ryle — Pirate Queen with a hatred for the Hegemony, "
                    "enforces a pirate code on those who would follow her (proud, demanding, "
                    "honorable)",
                    "Praxis Ivanov — merchant always willing to make a deal; his tentacles are "
                    "tattooed with the story of his several-hundred-year life (xeno, experienced, "
                    "shrewd)",
                    "Kai Quag — mid-level Cobalt boss: arranges protection for Cobalt smuggling "
                    "runs and meets with potential clients at the Cove (cautious, charming, "
                    "confident)",
                ],
            },
        ],
        "sites": [
            {"name": "Aleph", "map": (0.149, 0.684), "kind": "planet", "tags": ["toxic", "mineral stores"],
             "text": "Greenish-blue, gas-covered planet of poisonous gases and tectonic "
                     "instability, worth it only for its mineral stores. Most of the wealth dug "
                     "from it is taxed heavily by the Governor, leading to frequent unrest with "
                     "the miners. Moons: Warren, Hock, and Batter."},
            {"name": "Vet", "map": (0.27, 0.613), "kind": "planet", "tags": ["gas giant", "rings", "mining"],
             "text": "Gas giant with rings and no moons. Its resources are extracted by the "
                     "SB-176 station."},
            {"name": "Baftoma", "map": (0.125, 0.542), "kind": "planet", "tags": ["“The Husk”", "mined-out"],
             "text": "A planet stripped to the core: now only scaffolding of rock remains, forming "
                     "a small asteroid belt on its orbit. Its broken form is only used by folks "
                     "hiding or dodging pursuit—like the Wreckers."},
            {"name": "Ashtari Cloud", "map": (0.25, 0.51), "kind": "site",
             "tags": ["Ur ship remnant", "dodgy nav"],
             "text": "An ancient damaged remnant of a massive Ur ship, generating an in-system "
                     "nebula. Within it, normal propulsion is minimal and nav systems dodgy. The "
                     "Maelstrom pirates figured out how to navigate the cloud and made their base "
                     "within its shroud. The Ashtari Cult inhales its gases."},
            {"name": "The Straylight", "kind": "station", "tags": ["elite club", "moves about"],
             "text": "The latest fad: an upscale club and cocktail bar where elites can wine "
                     "and dine. It usually orbits Aleph, though it can move to other planets and "
                     "moons in the system. Its owner, Chance, runs a tight establishment, but "
                     "things can sometimes get out of hand."},
        ],
    },
    {
        "system": "Holt",
        "blurb": "The second Procyon system to be colonized, though the Rin-Holt gate had to be "
                 "forced open and stabilized with Ur keys—it remains temperamental and has been "
                 "known to open on its own. The Holt star burns white, though it is far older "
                 "than stars of this type should be, which scientists attribute to ancient Ur "
                 "manipulation. It has xenos unhappy about the yoke of the Hegemony, crime and "
                 "pirate strongholds, and one of the richest Guild mining planets. The biggest "
                 "hotbed of scum and villainy in the sector.",
        "gates": "2: Holt—Rin (unstable gate), Holt—Hantu (unopened).",
        "worlds": [
            {
                "name": "Mem", "map": (0.312, 0.199), "kind": "planet",
                "tags": ["ocean planet", "home of the Memish", "gravity wells"],
                "text": "This ocean planet was colonized by the Hegemony for almost a hundred years "
                        "before aquatic xenos made themselves (and their planetary claims) known; "
                        "Hegemonic forces broke the Memish military and incorporated them into the "
                        "Hegemony. Free-standing gravity wells deep beneath the waves make "
                        "exploration difficult. Moon: frozen Yuura; main port: Spaceport Keyan, "
                        "an artificial island chain near the government palace.",
                "rule": "The deeps are littered with Ur sites and strange glows. When in the deeps, "
                        "using ATTUNE for long-term projects grants +1d. Low rolls may attract "
                        "dangerous Way attention.",
                "scene": "Hegemonic officials in sashes, talking with Memish labor bosses. "
                         "See-through spires rising from the underwater government palace "
                         "to open-air pavilions. Tourists embarking on submersibles to take in "
                         "the local sea life. Scientists in exo-suits on deep-sea missions while "
                         "the Memish watch from the waters.",
                "faces": [
                    "Victor Kromyl — Planetary Governor: seeks proof of Memish rebellion after "
                    "a few subordinates vanished, always with his Legion bodyguard (vigilant, "
                    "meticulous, paranoid)",
                    "Espa Nur — Memish labor boss: his scars are packed with deep-ocean "
                    "bioluminescence; reports to Kromyl, but hides his knowledge of Memish "
                    "occultism (xeno, ambitious, cunning, treacherous)",
                    "Wyndam Taru Zahn — biology researcher seeking a connection between the Mem "
                    "and other planetary life, with little success; gathering an exploration "
                    "of the ancient Mem city of Bok-Dar (wealthy, brilliant, passionate)",
                ],
            },
            {
                "name": "Sonhandra", "map": (0.397, 0.31), "kind": "planet",
                "tags": ["tidally locked", "lax trade policies", "twilight border zone"],
                "text": "A tidally locked planet: the day side is blistering, and all light sources "
                        "extinguish about a kilometer into the night side. Most settlements are in "
                        "the twilight border zone, including the capital of Ugar. Known for its "
                        "lax policies regulating trade, it's a choice destination for smugglers "
                        "and fences alike.",
                "rule": "Everything is available on Sonhandra for a price. You can always take +1d "
                        "to acquire assets, but on a 1-3 roll the asset also comes with strings "
                        "(even if you boost the result with CRED).",
                "scene": "Perpetual twilight amid paved streets and concrete buildings. Howling "
                         "of frequent wind storms between the two regions. Masked and cloaked "
                         "strangers congregating around a steel warehouse before an auction "
                         "begins. Row after row of ships parked in the open dirt on the outskirts "
                         "of Ugar.",
                "faces": [
                    "Del Hex — outlaw gunslinger with obvious cybernetics from his Guild days, "
                    "wanted in several systems; runs a vibro-weapon fighting ring deep in the day "
                    "side (ruthless, fast, cautious)",
                    "Abra Drake — fixer for hire and auctioneer: if she can't get it or sell it, "
                    "she knows someone who can (connected, confident, bold)",
                    "Zeed “Tank” Marak — mercenary turned Nyct farmer; knows where and how to hide "
                    "ships on the night side (gambler, commanding, experienced)",
                    "Osha — Nyct-smoking, grizzled ex-Legionnaire; runs the Three Suns, a gambling "
                    "den and the biggest local dive (deadly, retired, steely)",
                ],
            },
            {
                "name": "Vos", "map": (0.497, 0.281), "kind": "planet",
                "tags": ["“Glimmer”", "crystals", "Guild-monitored"],
                "text": "An enormous planet known as “Glimmer”: its surface is made of graphite and "
                        "diamond, and at night the largest crystal formations glow with unearthly "
                        "light—a property many crystals retain after being cut. One must dock "
                        "at Guild station IA-23 in orbit and shuttle down.",
                "rule": "Vosian crystals are prized by Guilds and mystics alike. Vos is full "
                        "of money, but also closely monitored by the Guild. When you do a job "
                        "on Vos, you earn +1 CRED and +1 HEAT.",
                "scene": "Well-armed, permanent blockade in space, with ships waiting for "
                         "clearance. Smooth walls of dense carbon brick, windows looking out onto "
                         "the black surface. Diamond-scarred and sooty-faced miners, drinking with "
                         "shaking hands by their bulky sonic cutters. Pristine shops of the visitor "
                         "settlement.",
                "faces": [
                    "Morek and Ra-na — most-feared bounty hunter in Procyon and his AI partner "
                    "helming his artifact ship; on retainer to hunt any who loot Vos (ruthless, "
                    "vigilant, commanding)",
                    "Impera Evazan — high-ranking Guild logistics officer responsible for crystal "
                    "mining, privy to much of the Guild's supply structure (popular, demanding, "
                    "shrewd)",
                    "Yola Sprekk — jeweler known for using the unique properties of Vos crystals; "
                    "a Sprekk piece can open doors in the most elite circles (artistic, "
                    "charming, proud)",
                ],
            },
        ],
        "sites": [
            {"name": "Jerec's Junkyard", "kind": "station", "tags": ["parts", "haggling"],
             "text": "A free-floating mass of ships and parts, connected via magnetism and cabling. "
                     "Equipment is cheap, though it will likely be missing a piece or unreliable. "
                     "Jerec also buys, but is a canny haggler."},
            {"name": "Hantu Gate", "kind": "gate", "tags": ["never activated", "Precursor mystery"],
             "text": "The Hegemony has never been able to activate this jumpgate: compared to other "
                     "jumpgates it seems to be missing a few small but key pieces. It has been "
                     "speculated that the Ur locked the gate and hid the keys somewhere, though "
                     "it's anyone's guess as to why."},
            {"name": "Trade Platform Auto #4", "kind": "station",
             "tags": ["Guild", "fuel", "neutral ground"],
             "text": "The Guild's automated platform for selling fuel, covered in defensive systems "
                     "to deter theft. Because of this, some parties conduct negotiations here "
                     "to discourage escalation. Nobody knows what happened to the first three "
                     "platforms."},
            {"name": "Planet Omega", "map": (0.234, 0.193), "kind": "planet", "tags": ["quarantined", "deadly"],
             "text": "Three survey crews and one military expedition vanished before the Legion "
                     "quarantined this planet. A deadly life form nests within its Ur ruins "
                     "and can resist nukes from orbit. The Hegemony considers it hostile, but "
                     "insignificant to its plans; the Agony's platform orbits above."},
        ],
    },
    {
        "system": "Iota",
        "blurb": "A twin star system: the planets orbit a yellow sun (Iota-1) and a brown dwarf "
                 "(Iota-2). Both asteroid belts were clearly planets once, but nobody is sure "
                 "what calamity shattered them. The Guilds set up the Iota shipyards, servicing "
                 "ships with metals from the belts. Iota is the industrial production house that "
                 "transforms the resources of Rin and Iota into goods for the sector; the shipyards "
                 "mean a significant Legion presence. Many people only pass through it on the way "
                 "to Brekk.",
        "gates": "2: Iota—Rin, Iota—Brekk.",
        "worlds": [
            {
                "name": "Amerath", "map": (0.555, 0.748), "kind": "planet",
                "tags": ["garden planet", "pharmaceuticals", "Mendicant temple"],
                "text": "A lush planet well known for pharmaceuticals research: many regions are "
                        "well tended, the garden city of Rost is in perennial bloom, and warm, "
                        "gentle rains come frequently. The deep forests hide pirate lairs and "
                        "Mendicant temples amid overgrown ruins. A popular vacation spot for "
                        "well-off folks. Moon: Gap, a shattered moon that rings the planet.",
                "rule": "While it's ruined and unsanctified, the Mendicants keep their temple and "
                        "their mystics tend to any and all that request aid. Take +1d when you "
                        "recover in their care.",
                "scene": "Massive, person-sized flowers blooming along a vine-supported path "
                         "through the trees. The sweet smell of honey in the air. Scientists having "
                         "lunch at treetop cafés while reviewing project schedules. Sick pilgrims "
                         "praying for a cure while waiting to travel to the old Mendicant temple "
                         "deep in the forests.",
                "faces": [
                    "Yon Lirak — high-end drug dealer: runs a factory in Rost that never shuts "
                    "down, producing synthetic narcotics for several major species (experienced, "
                    "ruthless, unforgiving)",
                    "Ara Blaze — once a star athlete, now a preeminent pit fighter in the "
                    "underground fight clubs; has tried every performance-enhancing drug, and it "
                    "has changed her (ruthless, unforgiving, engineered)",
                    "Uyen al'Vorron — famous Noble duelist from the religious House Vorron; "
                    "seeking to cultivate a plant for a vineyard on a moon near the Core (armed, "
                    "deadly, observant)",
                ],
            },
            {
                "name": "Indri", "map": (0.486, 0.744), "kind": "planet",
                "tags": ["manufacturing planet", "thick clouds", "orbital warehouses"],
                "text": "Over 25 percent of all goods manufactured in the Procyon sector come from "
                        "this incredibly industrialized planet. Thick, rust-colored clouds create "
                        "dusk even during the day; from the spaceport of Reves one can view "
                        "the skyline of smokestacks and gas burn-offs. Its moons were consumed for "
                        "materials, warehouses hang in orbit. Travel without protective gear is "
                        "not advised.",
                "rule": "The factories have caused massive air pollution; anyone spending any amount "
                        "of time outside without proper equipment or xeno abilities gains level 2 "
                        "harm “Indri Lung.”",
                "scene": "Hovercar traffic reflecting adverts on buildings. Gas-masked pedestrians "
                         "walking hurriedly down metal sidewalks with umbrellas treated to prevent "
                         "acid rain damage. Slow-moving containers being shuttled to warehouses. "
                         "Storm clouds with multi-hued lightning rolling in.",
                "faces": [
                    "Piro Locke — owns discreet, well-guarded storage spaces in orbit with a strict "
                    "no-questions policy: if it's illegal, it's certainly stored by Locke "
                    "(honorable, wealthy, confident)",
                    "Zo O Yun Ta Ri — weapons dealer known for prototypes and specialty "
                    "armaments; recently acquired an Ur ship weapon and plans to auction it under "
                    "the cover of a storm (xeno, connected, cautious, meticulous)",
                    "Pasha “the Roc” Lensarr — local head of the Ashen Knives: wears "
                    "custom-tailored suits that allow his wings to unfurl as needed (xeno, fierce, "
                    "ruthless, demanding)",
                ],
            },
            {
                "name": "Lithios", "map": (0.557, 0.908), "kind": "planet",
                "tags": ["ice planet", "ice palaces", "Yaru creche"],
                "text": "Ancient ice palaces of a long-passed race dot the surface of this frozen "
                        "planet; entry has been restricted after a string of mysterious explorer "
                        "deaths. Orbital mirrors shine like artificial suns, keeping settlements "
                        "warm and powering rigs for extracting water and liquefied gases. Hosts "
                        "a Yaru creche and Solitude Colony.",
                "rule": "When you explore the ice palaces of Lithios, you must make a RESOLVE resist "
                        "if you don't want to heed the echoes urging you to wander into the frozen "
                        "wastes alone.",
                "scene": "A purple and green aurora shining over the freezing cold sky. Ice "
                         "explorers whispering about the Yaru creche. Heated vapors escaping "
                         "around Solitude Colony. Colonists riding large, many-eyed canids. Farmers "
                         "pulling gas-eels and ice-mushroom wine crates in sail-sporting snow "
                         "skimmers.",
                "faces": [
                    "Asha Munzen — ex-lover of the Governor, ice climber and mystic; returns from "
                    "the ice palaces and gas caves only with visions, never artifacts; attempting "
                    "to find the “First Message” (mystic, ambitious, fit)",
                    "Ren Larana — xenobiologist attempting to revive an ancient xeno found frozen "
                    "but alive in the ice, despite Hegemonic law forbidding it, and to sneak it "
                    "off-world (bold, brilliant, confident)",
                    "Raf Urich — ice pirate stranded on planet: used his ship weapons to cut "
                    "a berth in the ice, hides out and steals parts (experienced, cautious, "
                    "shrewd)",
                ],
            },
        ],
        "sites": [
            {"name": "Shipyards", "map": (0.479, 0.871), "kind": "station",
             "tags": ["Starsmiths", "repairs", "prototypes"],
             "text": "The primary yard is run by Starsmiths, surrounded by many smaller, licensed "
                     "hubs for repairs and ship refits full of bored spacers. Starsmiths sometimes "
                     "hire foolhardy pilots for prototype tests. Major port: Station CM-5."},
            {"name": "Belt of Fire", "map": (0.533, 0.759), "kind": "site", "tags": ["plasma", "quarantined"],
             "text": "The region of superheated plasma currents between the Iota binary stars. "
                     "The Hegemony issued a Quarantine order for the area after several ships "
                     "disappeared; spacers spin yarns about the Old Dragon—a vast space creature "
                     "living there."},
            {"name": "Way Line", "kind": "site", "tags": ["more thrust", "switches direction"],
             "text": "A region between the Iota gates where engines have more thrust, akin "
                     "to “winds” of a planet. The path is hard to find and switches direction. "
                     "Pilots in the know use it on rush deliveries (or daring escapes)."},
            {"name": "ZX-1138", "kind": "site", "tags": ["comet", "diverged course", "Way lines shifted"],
             "text": "A long-period comet that recently diverged from its course, taking it much "
                     "closer to Indri. Reasons are unclear; locals have requested the Governor "
                     "investigate. Mystics claim this has shifted the system Way lines, making "
                     "the Way sometimes act unpredictably."},
        ],
    },
    {
        "system": "Brekk",
        "blurb": "Considered more civilized than the rest of Procyon, the sector's cultural capital: "
                 "education, art, and culture—and a strong Legion presence guarding that wealth. "
                 "The elite strike deals on the neon-lit streets of Nightfall, researchers head "
                 "to Khalud Academy on Shimaya, and those fleeing the law hide in Aketi's jungle. "
                 "Odd, non-Starsmith-maintained hyperspace lanes bend strangely through "
                 "the system; pilots map these “dark lanes” themselves.",
        "gates": "1: Brekk—Iota.",
        "worlds": [
            {
                "name": "Aketi", "map": (0.871, 0.466), "kind": "planet",
                "tags": ["jungle", "hostile natural life", "“nature preserve”"],
                "text": "A massive, largely unexplored jungle planet that resists taming. Rapidly "
                        "spreading carnivorous plants, seasonally rampaging beasts, and "
                        "hyper-aggressive fish leave it only to researchers, poachers, and "
                        "criminals hiding from the law. Labeled a Malklaith “nature preserve”; "
                        "the port is Base Camp One. Moons Suhk, Enro, and Awk have no atmosphere.",
                "rule": "Nobody comes here who doesn't have to. The planet hates you, and jobs "
                        "are hard to find. Even bounty hunters pass it by. When you lay low "
                        "on Aketi, take +1d.",
                "scene": "Heavily armed guards patrolling the tall walls of Base Camp One, nervously "
                         "eyeing the jungle. Research crews packing for their next expedition "
                         "across from poachers doing the same. A smuggler discussing arrangements "
                         "with a client in a tent while a personal barista makes them drinks.",
                "faces": [
                    "Razor — a hunter mounting an expedition to catch the deadly Grand Phereniki "
                    "for a rich client (callous, experienced, gambler)",
                    "Zokar Pava — Lost Legionnaire dealing in military-grade weapons (cautious, "
                    "meticulous, dissident)",
                    "Intal Brel — psy-blade-wielding Concordiat Knight; travels with a "
                    "nine-foot-tall xeno, an ex-priest, and an Urbot, hopes to replace a recently "
                    "lost party member (religious, vigilant, honorable)",
                    "Asha Ravann — Base Camp One commander: instituted a wall-mounted flamethrower "
                    "measure that's kept the jungle at bay (tired, jaded, relentless)",
                ],
            },
            {
                "name": "Nightfall", "map": (0.869, 0.31), "kind": "planet",
                "tags": ["center of culture", "13 moons", "51st Legion"],
                "text": "Named for frequent eclipses caused by the planet's 13 moons, whose erratic "
                        "movements make night only predictable by computer. The city of Yaw, where "
                        "night and day last between 2 and 12 hours each, bustles with economic "
                        "activity and is known for its haute cuisine and theater. Space station "
                        "Obelisk is controlled by the 51st Legion; the ancient temple Dendara "
                        "stands on the fifth moon, Todav.",
                "rule": "Nightfall is the center of culture in the system, and everything is mostly "
                        "about who you know. When you acquire assets, roll with CONSORT instead "
                        "of crew quality.",
                "scene": "High-rises lighting up block by block as the city goes from day to night "
                         "in the span of minutes. A rowdy night club spilling dancers clad in black, "
                         "glow-accented outfits onto a sun-lit street. The blue glow of a public "
                         "data kiosk projecting tomorrow's night schedule and market changes.",
                "faces": [
                    "Saren Galia — data broker and bookie: when you can't pay your debts, you "
                    "become her informant (paranoid, fast, connected)",
                    "Lotus — fashionista and taste-maker, secretly a high-powered fixer; has been "
                    "known to take charity cases (popular, passionate, meticulous)",
                    "Jet Wolffe — Scarlet Wolf assassin: can be hired, but only takes off-world "
                    "jobs; travels with a large, blue-skinned alien animal of unknown origin "
                    "(aloof, confident, unforgiving)",
                    "Sol Brighton — best lawyer in the sector (cunning, connected, expensive)",
                ],
            },
            {
                "name": "Shimaya", "map": (0.781, 0.353), "kind": "planet",
                "tags": ["desert", "Khalud Academy", "electrical storms"],
                "text": "A desert planet ravaged by electrical storms that occasionally clear colored "
                        "sand off mineral deposits essential to space travel, or turn it to glass, "
                        "giving a view to the ruins beneath. Teams race to capitalize on these "
                        "events. Home to the sector's preeminent educational institution, Khalud "
                        "Academy, and a substantial civilian population; port: Ersia City.",
                "rule": "Although only students and professors are technically allowed to use "
                        "the Khalud Academy archives, any STUDY rolls while using them take +1d.",
                "scene": "Professors walking down the marble paths of the Academy. A market street "
                         "with insistent vendors selling sandworm kebabs to hungry miners. "
                         "Excavators packing furiously onto sand-skiffs, ready to take advantage "
                         "of a storm-cleared deposit. The storm alert blaring citywide.",
                "faces": [
                    "Hondo Suzuka — HNN reporter seeking evidence of conspiracy at Khalud Academy, "
                    "where several top students have vanished (ambitious, vigilant, charming)",
                    "Ed Ursis — Guild Engineer working on the orbital array and the electrostatic "
                    "generators it powers to keep the storms away from the capital; collects "
                    "colored glass statues (dedicated, brilliant, overworked)",
                    "Miranda Kasur — minerals trader with a load of stolen goods she needs to move, "
                    "in hiding after her first deal went wrong (scared, cunning, proud)",
                    "Sahar — strange-suited mystic that lives in the desert (odd, blue-eyed, "
                    "ancient)",
                ],
            },
        ],
        "sites": [
            {"name": "Blackstarr", "kind": "station",
             "tags": ["Nightspeakers", "unlit", "Cult HQ"],
             "text": "The vast and largely empty Nightspeaker dreadnought where initiates train "
                     "for their first year. The ship is unlit and moves routinely to prevent "
                     "discovery. It does not often receive visitors, but exceptions are made for "
                     "those that have a favorable relationship to the Cult."},
            {"name": "Dendara", "kind": "site", "tags": ["ancient temple", "Todav", "glitching drives"],
             "text": "An ancient temple on Nightfall's fifth moon, Todav. Some say it's an Ur "
                     "temple, others that it's the remains of a forgotten mystic Cult. Its derelict "
                     "corridors are tough to tour due to the moon's lack of atmosphere and the "
                     "glitching effect it has on drives and electronics."},
            {"name": "Bright Wind", "map": (0.812, 0.367), "kind": "site", "tags": ["Echo Wave Riders races", "lethal"],
             "text": "A large gas cloud ejected by the star, now used as racing grounds by the Echo "
                     "Wave Riders. Despite it being both lethal and illegal, racers from all over "
                     "the sector compete for cred and fame. Invitations are exclusive and require "
                     "qualifying in equally hazardous conditions."},
            {"name": "Isotropa Max Secure", "map": (0.769, 0.407), "kind": "station",
             "tags": ["max security", "orbits the star", "wardens broker deals"],
             "text": "Orbiting near the star, Isotropa is the most notorious prison in Procyon. "
                     "Wardens broker audiences with prisoners and grant commutations for the "
                     "powerful and wealthy. They report to Malklaith, but the prison largely runs "
                     "itself."},
        ],
    },
]
