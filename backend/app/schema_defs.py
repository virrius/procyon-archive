"""Fields by entity kind.

All kinds share one frame (photo, name, summary, Tier, factions/location, status, ownership,
visibility, links, notes), drawn by one shared EntityPage; only 1-3 kind-specific fields
remain here. All other knowledge lives in notes (ContentBlock) with their own visibility.

The GM can hide any entity field individually: the key goes into
``entities.hidden_fields``, the value is always kept, and it can be revealed
later with one toggle. ``secret=True`` in a field spec only means
"hidden on a new entity by default" — after that it is a regular toggle.
"""

from __future__ import annotations

from .book_defs import book
from .i18n import tr, twin_lang

# the module is loaded in both languages (see langpack): language comes from the module name
LANG = twin_lang(__name__)
PROCYON, SHIP_SIZES, SHIP_TYPES = book(LANG).PROCYON, book(LANG).SHIP_SIZES, book(LANG).SHIP_TYPES
PLAYBOOK_SHEETS, CHAR_SHEET = book(LANG).PLAYBOOK_SHEETS, book(LANG).CHAR_SHEET

T, TA, SEL, MULTI, REF = "text", "textarea", "select", "multi", "ref"
# for REF, kinds lists the entity kinds to pick from; the value is the entity id
# for MULTI, the field spec may set max — a cap on selected options

RANKS = ["0", "1", "2", "3", "4"]
SYS_LEVELS = ["0", "1", "2", "3"]
DMG_LEVELS = ["0", "1", "2", "3", "4"]
XP_LEVELS = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
STANCES = ["-3", "-2", "-1", "0", "+1", "+2", "+3"]
# shared Tier scale — strength/threat/value
RANK_SCALE = ["0", "1", "2", "3", "4", "5"]
ORG_CATEGORIES = ["hegemony", "criminal", "weird"]
LOC_TYPES = ["planet", "station", "port", "gate", "site"]
# a system is not an entity but a location attribute: the list comes from the book
SYSTEMS = [s["system"] for s in PROCYON if s.get("system")]

# character playbooks from the book — a fixed part of the sheet
PLAYBOOKS = [
    "Здоровяк", "Механик", "Мистик", "Переговорщик", "Пилот", "Пройдоха", "Умник",
]
HERITAGES = ["Империец", "Космит", "Колонист", "Рукотворный", "Скиталец", "Ксенос"]
VICES = [
    "Азартные игры", "Беспамятство", "Долг", "Наслаждения", "Потустороннее",
    "Религия", "Роскошь",
]
PASTS = [p["name"] for p in CHAR_SHEET["pasts"]]
# rumor and job are the same thing at different stages
JOB_TYPES = ["rumor", "job"]

TRAUMAS = [
    "Визионер", "Маньяк", "Параноик", "Псих",
    "Раздолбай", "Садист", "Социопат", "Тряпка",
]

# the English instance stores values from the English book; order is the same as above
if LANG == "en":
    PLAYBOOKS = ["Muscle", "Mechanic", "Mystic", "Speaker", "Pilot", "Scoundrel", "Stitch"]
    HERITAGES = ["Imperial", "Spacer", "Colonist", "Manufactured", "Wanderer", "Xeno"]
    VICES = ["Gambling", "Stupor", "Obligation", "Pleasure", "Weird", "Faith", "Luxury"]
    TRAUMAS = ["Haunted", "Obsessed", "Paranoid", "Unstable", "Reckless", "Vicious", "Cold", "Soft"]


def f(key, type_=T, **kw):
    return {"key": key, "type": type_, **kw}


KINDS: dict[str, dict] = {
    "character": {
        "statuses": ["active", "injured", "retired", "dead"],
        "fields": [
            f("playbook", SEL, options=PLAYBOOKS),
            f("heritage", SEL, options=HERITAGES),
            f("past", SEL, options=PASTS),
            f("system", SEL, options=SYSTEMS),
            f("vice", MULTI, options=VICES, max=2),
            f("trauma", MULTI, options=TRAUMAS),
            f("look"),
            f("background", TA),
        ],
    },
    # stress / harm / actions / xp / talents / items / contacts / custom live in the same fields,
    # drawn by the character sheet (components/charsheet), not the generic form
    "npc": {
        "statuses": ["active", "blocked", "dead", "unknown"],
        "fields": [
            f("rank", SEL, options=RANK_SCALE),
            f("system", SEL, options=SYSTEMS),
            f("gm_appearance", TA),
        ],
    },
    "faction": {
        # a faction either exists or not — its state reads from Tier and notes
        "statuses": [],
        "fields": [
            f("category", SEL, options=ORG_CATEGORIES),
            f("rank", SEL, options=RANK_SCALE),
            f("stance", SEL, options=STANCES),
            f("system", SEL, options=SYSTEMS),
        ],
    },
    # modules / upgrades / talents / contacts / custom live in the same fields JSONB,
    # but are drawn by the ship sheet, not the generic form.
    "ship": {
        "statuses": ["active", "impounded", "destroyed", "lost"],
        "fields": [
            f("ship_type", SEL, options=list(SHIP_TYPES)),
            f("ship_class"),
            f("blurb"),
            f("size", SEL, options=list(SHIP_SIZES)),
            f("crew_rank", SEL, options=RANKS),
            f("look", TA),
            f("reputation"),
            f("sys_hull", SEL, options=SYS_LEVELS),
            f("sys_engines", SEL, options=SYS_LEVELS),
            f("sys_sensors", SEL, options=SYS_LEVELS),
            f("sys_guns", SEL, options=SYS_LEVELS),
            f("dmg_hull", SEL, options=DMG_LEVELS),
            f("dmg_engines", SEL, options=DMG_LEVELS),
            f("dmg_sensors", SEL, options=DMG_LEVELS),
            f("dmg_guns", SEL, options=DMG_LEVELS),
            f("crew_xp", SEL, options=XP_LEVELS),
            f("creds"),
            f("debt"),
        ],
    },
    "location": {
        # a location has no states — what is known about it lives in notes
        "statuses": [],
        # a system is a location attribute and a gallery filter, not a separate entity
        "fields": [
            f("system", SEL, options=SYSTEMS),
            f("loc_type", SEL, options=LOC_TYPES),
            f("rank", SEL, options=RANK_SCALE),
        ],
    },
    "job": {
        "statuses": ["offered", "in progress", "done", "failed", "expired"],
        "fields": [
            # rumor and job are one entity: a rumor matures into a job by changing its type
            f("job_type", SEL, options=JOB_TYPES, badge=True),
            f("rank", SEL, options=RANK_SCALE),
            f("payout", note=True),
            f("employer", REF, kinds="npc,faction,character"),
            f("system", SEL, options=SYSTEMS),
        ],
    },
    "item": {
        "statuses": ["with crew", "lost", "sold", "hidden", "unknown"],
        "fields": [
            f("rank", SEL, options=RANK_SCALE),
            f("system", SEL, options=SYSTEMS),
        ],
    },
}


def kinds() -> dict[str, dict]:
    """KINDS with kind and field labels in the request language — for /api/meta."""
    return {
        kind: {
            "label": tr(f"schema.kinds.{kind}.label"),
            "plural": tr(f"schema.kinds.{kind}.plural"),
            **spec,
            "fields": [{"key": fd["key"], "label": tr(f"schema.fields.{fd['key']}"), **fd}
                       for fd in spec["fields"]],
        }
        for kind, spec in KINDS.items()
    }


def initial_status(kind: str) -> str:
    """Status of a new entity — the first status of its kind; factions and locations have no statuses."""
    return next(iter(KINDS.get(kind, {}).get("statuses") or []), "")


# clock color instead of a type: there is nothing to sort them by anyway, and color is easy to spot
CLOCK_COLORS = ["amber", "rust", "steel", "plum", "olive", "white"]

MESSAGE_TYPES = [
    "personal", "crew", "job offer", "bounty", "HNN news", "system alert",
    "intercepted", "faction", "anonymous", "ship warning", "document",
]

VISIBILITY_SCOPES = ["crew", "selected", "owner", "gm"]
BLOCK_TYPES = ["text", "image", "attachment", "quote", "rumor", "secret", "warning", "map note"]


# visibility scale — labels exactly as in the picker
def vis_labels() -> dict[str, str]:
    return {scope: tr(f"schema.labels.vis_{scope}") for scope in ("gm", "owner", "selected", "crew")}


# --- ru labels for internal keys (values stay English in the DB) --------------

LABEL_KEYS: tuple[str, ...] = (
    # entity statuses
    "active", "blocked", "dead", "unknown",
    "dormant", "destroyed", "frozen",
    "finished", "impounded", "lost",
    "rumored", "visited", "compromised",
    "with crew", "sold", "hidden",
    "injured", "retired",
    "offered", "done", "failed",
    "expired", "accepted", "in progress",
    # legacy statuses of old rows
    "captured", "left crew", "missing",
    "handed over", "stolen", "inaccessible",
    "abandoned", "completed", "replaced",
    "Offered", "Accepted", "Active",
    "Completed", "Failed", "Abandoned",
    "Expired", "Rumor", "Lead",
    # knowledge
    "rumor", "suspected", "confirmed",
    "disproved",
    # visibility scale
    "gm", "owner", "selected",
    "vis_gm", "vis_owner",
    "vis_selected", "vis_crew",
    # clocks
    "faction", "long-term project",
    "mission deadline", "danger",
    "reprisal", "investigation",
    "trust", "wanted reduction", "racing",
    "tug-of-war", "linked", "custom",
    # messages
    "personal", "job offer", "bounty",
    "crew", "HNN news", "system alert",
    "intercepted", "anonymous",
    "ship warning", "document",
    "draft", "delivered", "archived",
    # markers / location types
    "location", "npc",
    "artifact", "threat", "clock",
    "message", "route", "secret",
    "system", "planet", "station",
    "port", "gate", "jumpgate", "region",
    "site", "sector", "local",
    # blocks
    "text", "image", "attachment",
    "quote", "warning", "map note",
    # link labels
    "работает на", "где искать",
    # questions / notes
    "open", "partially answered", "answered",
    "obsolete", "resolved",
    # roles
    "player", "observer",
    # entity kinds
    "character", "item", "ship",
    "job",
    # edge styles
    "jump", "trade", "secret route",
    # organisation categories
    "hegemony", "criminal",
    "weird", "other",
    # ship sheet keys
    "sys_hull", "sys_engines", "sys_sensors",
    "sys_guns", "crew_rank", "creds",
    "debt", "reputation", "modules",
    "upgrades", "talents", "contacts",
    "friend", "rival", "neutral",
    "dmg_hull", "dmg_engines",
    "dmg_sensors", "dmg_guns",
    "crew_xp", "xp_triggers",
    # character sheet keys
    "heritage", "background", "trauma",
    "playbook",
    "look", "vice", "goal",
    "stance",
    # "custom" (own clock) and "secret" (marker, dossier block) are labeled above:
    # the dictionary is flat, one label per key — the one the table sees wins
)

# a link label is stored as text in the DB — the dictionary uses a semantic key
LINK_LABEL_KEYS = {"работает на": "works_for", "где искать": "where_to_find"}
if LANG == "en":
    LINK_LABEL_KEYS = {"works for": "works_for", "where to find": "where_to_find"}
    LABEL_KEYS = tuple({"работает на": "works for", "где искать": "where to find"}.get(k, k) for k in LABEL_KEYS)


def labels() -> dict[str, str]:
    """Labels of internal keys in the request language."""
    out = {k: tr(f"schema.labels.{LINK_LABEL_KEYS.get(k, k)}") for k in LABEL_KEYS}
    # ship type labels come from the book so they stay in sync
    for _key, _type in (SHIP_TYPES or {}).items():
        if isinstance(_type, dict):
            out.setdefault(_key, _type.get("label", _key))
    return out
