"""Поля по типам сущностей.

Каркас у всех типов одинаковый (фото, имя, краткое описание, ранг,
фракции/место, статус, права владения, видимость, связи, записи) и рисуется
одним общим кодом в EntityPage — здесь остаются только 1-3 своих поля типа.
Всё остальное знание живёт в записях (ContentBlock) со своей видимостью.

Любое поле карточки ГМ закрывает поштучно: ключ лежит в
``entities.hidden_fields``, значение живёт всегда, а раскрыть его можно
позже одним переключателем. ``secret=True`` в описании поля значит только
«закрыто у новой карточки по умолчанию» — потом это обычный переключатель.
"""

from __future__ import annotations

from .book_defs import book
from .i18n import tr, twin_lang

# модуль загружен на обоих языках (см. langpack): язык — из имени модуля
LANG = twin_lang(__name__)
PROCYON, SHIP_SIZES, SHIP_TYPES = book(LANG).PROCYON, book(LANG).SHIP_SIZES, book(LANG).SHIP_TYPES

T, TA, SEL, MULTI, REF = "text", "textarea", "select", "multi", "ref"
# у REF в kinds — виды карточек, из которых выбирают; значение — id карточки
# у MULTI в описании поля может стоять max — потолок выбранных вариантов

RANKS = ["0", "1", "2", "3", "4"]
SYS_LEVELS = ["0", "1", "2", "3"]
DMG_LEVELS = ["0", "1", "2", "3", "4"]
XP_LEVELS = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
STANCES = ["-3", "-2", "-1", "0", "+1", "+2", "+3"]
# общая шкала «ранга» — сила/угроза/ценность
RANK_SCALE = ["0", "1", "2", "3", "4", "5"]
ORG_CATEGORIES = ["hegemony", "criminal", "weird"]
LOC_TYPES = ["planet", "station", "port", "gate", "site"]
# система — не карточка, а атрибут места: список берём из книги
SYSTEMS = [s["system"] for s in PROCYON if s.get("system")]

# бланки персонажа из книги — постоянная часть листа
PLAYBOOKS = [
    "Здоровяк", "Механик", "Мистик", "Переговорщик", "Пилот", "Пройдоха", "Умник",
]
HERITAGES = ["Империец", "Космит", "Колонист", "Рукотворный", "Скиталец", "Ксенос"]
VICES = [
    "Азартные игры", "Беспамятство", "Долг", "Наслаждения", "Потустороннее",
    "Религия", "Роскошь",
]
# слух и работа — одно и то же дело на разных стадиях зрелости
JOB_TYPES = ["rumor", "job"]

TRAUMAS = [
    "Визионер", "Маньяк", "Параноик", "Псих",
    "Раздолбай", "Садист", "Социопат", "Тряпка",
]

# английский экземпляр хранит значения по английской книге; порядок тот же, что выше
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
            f("system", SEL, options=SYSTEMS),
            f("vice", MULTI, options=VICES, max=2),
            f("trauma", MULTI, options=TRAUMAS),
            f("gm_appearance", TA),
            f("background", TA),
        ],
    },
    "npc": {
        "statuses": ["active", "blocked", "dead", "unknown"],
        "fields": [
            f("rank", SEL, options=RANK_SCALE),
            f("system", SEL, options=SYSTEMS),
            f("gm_appearance", TA),
        ],
    },
    "faction": {
        # организация либо есть, либо её нет — состояние читается из ранга и записей
        "statuses": [],
        "fields": [
            f("category", SEL, options=ORG_CATEGORIES),
            f("rank", SEL, options=RANK_SCALE),
            f("stance", SEL, options=STANCES),
            f("system", SEL, options=SYSTEMS),
        ],
    },
    # modules / upgrades / talents / contacts / custom лежат в том же fields JSONB,
    # но их рисует бланк корабля, а не generic-форма.
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
        # место не меняет состояний — что о нём известно, живёт в записях
        "statuses": [],
        # система — атрибут места и фильтр галереи, отдельной карточкой не заводится
        "fields": [
            f("system", SEL, options=SYSTEMS),
            f("loc_type", SEL, options=LOC_TYPES),
            f("rank", SEL, options=RANK_SCALE),
        ],
    },
    "job": {
        "statuses": ["offered", "in progress", "done", "failed", "expired"],
        "fields": [
            # слух и работа — одна карточка: слух дозревает до дела сменой типа
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
    """KINDS с подписями видов и полей на языке запроса — для /api/meta."""
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
    """Статус новой карточки — первый из статусов вида; у фракций и мест статусов нет."""
    return next(iter(KINDS.get(kind, {}).get("statuses") or []), "")


# цвет счётчика вместо типа: сортировать их всё равно нечем, а глазом видно
CLOCK_COLORS = ["amber", "rust", "steel", "plum", "olive", "white"]

MESSAGE_TYPES = [
    "personal", "crew", "job offer", "bounty", "HNN news", "system alert",
    "intercepted", "faction", "anonymous", "ship warning", "document",
]

VISIBILITY_SCOPES = ["crew", "selected", "owner", "gm"]
BLOCK_TYPES = ["text", "image", "attachment", "quote", "rumor", "secret", "warning", "map note"]


# шкала видимости — подписи ровно как в пикере
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
    # legacy statuses старых строк
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
    # «custom» (свой счётчик) и «secret» (маркер, блок досье) подписаны выше:
    # словарь плоский, на ключ одна подпись — выигрывает та, что видна столу
)

# подпись связи живёт в БД текстом — в словаре у неё смысловой ключ
LINK_LABEL_KEYS = {"работает на": "works_for", "где искать": "where_to_find"}
if LANG == "en":
    LINK_LABEL_KEYS = {"works for": "works_for", "where to find": "where_to_find"}
    LABEL_KEYS = tuple({"работает на": "works for", "где искать": "where to find"}.get(k, k) for k in LABEL_KEYS)


def labels() -> dict[str, str]:
    """Подписи внутренних ключей на языке запроса."""
    out = {k: tr(f"schema.labels.{LINK_LABEL_KEYS.get(k, k)}") for k in LABEL_KEYS}
    # подписи типов кораблей берём из книги, чтобы не разъезжались
    for _key, _type in (SHIP_TYPES or {}).items():
        if isinstance(_type, dict):
            out.setdefault(_key, _type.get("label", _key))
    return out
