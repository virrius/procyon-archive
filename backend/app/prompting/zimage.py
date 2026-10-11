"""Рендерер Z-Image-Turbo: строка тегов без весов и без негатива.

Что тут — свойства рисующей модели, снятые на стенде, а не мир кампании:

- энкодер Qwen3-4B. Проза ему не нужна: теги читаются не хуже, а связная речь
  на этой модели давала мыльную подачу. Окно длинное — маркер, вставленный в
  тело из 78 тегов, доходил до кадра с любой позиции в 36 кадрах из 36;
- синтаксис веса `(тег:1.4)` и дублирование тега кадр не меняют. Весов здесь
  нет вовсе: порядок тегов и есть единственная расстановка сил;
- модель дистиллирована под cfg 1.0. Формула guidance вырождается в `cond`,
  безусловная ветка не считается — негатив физически не участвует в выводе;
- ярлык эпохи (`far future`, `space western`, `used future`) на этой модели
  инертен: десять ярлыков на шести архетипах дали почти неразличимые кадры.
  Тега сеттинга здесь нет;
- описывать мир нельзя вообще. Любое упоминание мира становится предметом в
  кадре: перечень одежды мира модель рисует как экипаж из пяти человек, фраза
  про потрёпанный фрахтовик въезжает в кадр грузовиком. Мир держится только
  одеждой, названной в слоте одежды, — и её пишет ГМ, а не сборка;
- манера держится словами. Обученный адаптер кадр портит, поэтому триггера в
  строке нет.

Кадр собирается в 832x1216 (персонаж), 1216x832 (предмет), 1344x768 (место).
"""
from __future__ import annotations

import re

from .lore import CYR_SLOT, NEGATION, swap_earth_words

# Голова стиля — единственное, что задаёт подачу, и она короткая: три понятия,
# каждое проверено зондом. Техника письма (не жанр и не палитра): по эталонам
# style_refs/ подача держится мазком. Слова фотостудии (`soft light`,
# `cinematic`) и `clean rendering` сняты — первое тянуло в фото, второе
# выбеливало кадр. `detailed environment background` заменил отдельный хвост
# про края кадра: фон, названный в голове, не даёт фигуре повиснуть на заливке.
# Состояние вещи (потрёпанная/новая) — слово в слоте, не рубильник головы
STYLE_HEAD = ("painterly sci-fi concept art, visible brush strokes, detailed environment background, "
              "far future exotic looking clothes and devices")

# Что верно только про эту сторону и потому не живёт в общей разметке слотов.
# Счёт пунктов и длина фразы уже сказаны там — здесь остаётся мера, снятая
# стендом: описанный мир рисуется буквально, поэтому мира в слотах нет
INSTRUCTION_ADDENDUM = """

NEVER NAME THE WORLD, ITS ERA OR ITS GENRE. Measured on this drawing model: a list of what people in this world wear is drawn as a crowd of five people wearing all of it, and the phrase "one worn freighter and the people who fly it" is drawn as a truck with a crew in the cab. An era named in words — far future, used future, space western — moves nothing at all. Every slot holds a thing visible inside this one frame, and nothing about the world around it: the world arrives through the cut of what is in the frame or it does not arrive."""


def instruction_addendum(_kind: str = "person") -> str:
    """Дописка к разметке слотов: мера, снятая стендом на этой модели."""
    return INSTRUCTION_ADDENDUM


# Рамка постоянна для направления: модели её не доверяем
FRAMING = {
    # `full body` один крупность не держит: без «head to feet» модель сама
    # сваливается в поясной план (зонд probe_refstyle)
    "person": ("single figure, full body", "head to feet", "face clearly visible"),
    # у машины лица нет, а рамка персонажа его требует — и модель послушно сажает
    # человека за смотровое стекло корпуса; снято живым прогоном на роботе-пылесосе
    "machine": ("single object, full body", "whole unit from top to floor",
                "three-quarter view"),
    "ship": ("three-quarter dynamic view", "whole craft in frame, banking or thrusting",
              "environment visible around the craft, not empty studio backdrop"),
    "handheld": ("close-up study of one object", "single object centred in frame",
                 "dim plain background"),
    "structure": ("wide shot in open space", "whole structure in frame",
                  "black airless space on every side"),
    "planet": ("view from orbit", "full globe against black airless space"),
    "landscape": ("wide establishing shot", "ground level", "scene fills all four edges"),
    "interior": ("wide establishing shot", "view from a doorway", "scene fills all four edges"),
    "action": ("dynamic action scene", "figures in motion", "wide shot",
               "scene fills all four edges"),
}

# Окно энкодера длинное, и потолок здесь — не токены, а внимание: тело из
# восьмидесяти тегов модель ещё держит целиком
MAX_TAGS = 90
MAX_SLOT_WORDS = 9

# сколько у тела рук, если их не две: счёт вынимается из описания тела и
# ставится в начало позы, где модель его единственно и слышит
LIMBS = re.compile(r"\b(three|four|five|six|eight)[- ]armed\b", re.I)
LIMBS_DONE = re.compile(r"\b(three|four|five|six|eight) arms\b", re.I)
# «гладкая кожа без морщин» — не описание лица, а его отсутствие
BLANK_FACE = re.compile(r"\b(smooth|unlined|flawless|poreless|youthful)\b[^,]*\bskin\b"
                        r"|\bskin\b[^,]*\b(smooth|unlined|flawless|poreless)\b", re.I)


def _tags(value, kind: str, max_words: int = MAX_SLOT_WORDS) -> list[str]:
    vals = value if isinstance(value, (list, tuple)) else [value]
    out = []
    for raw in vals:
        tag = swap_earth_words(str(raw or "").strip().rstrip(" .,;"), kind)
        if (tag and not NEGATION.search(tag) and not CYR_SLOT.search(tag)
                and len(tag.split()) <= max_words):
            out.append(tag)
    return out


def _person(slots: dict, kit: dict) -> list[str]:
    parts: list[str] = []
    subject = _tags(slots.get("subject"), "person")
    age = str(kit.get("ages", {}).get(str(slots.get("age", "")).strip(), "") or "")
    # у машины нет возраста, а полоса по умолчанию дописывает «adult, years of the
    # trade on the face» — прожитое лицо корпусу, у которого лица нет
    if str(slots.get("role", "")).strip() == "machine":
        age = ""
    if subject:
        lead = f"{age.split(',')[0]} {subject[0]}".strip() if age else subject[0]
        seen, kept = set(), []
        for word in lead.split():
            if word.lower() in seen:
                continue
            seen.add(word.lower())
            kept.append(word)
        parts.append(" ".join(kept))
        rest = [t.strip() for t in age.split(",")[1:] if t.strip()]
        parts += rest
    # «гладкая кожа без морщин» — не описание, а его отсутствие: модель отвечает
    # неношеным лицом с обложки. Запрет словами Квен обходит, поэтому фраза
    # выбрасывается на сборке
    parts += [t for t in _tags(slots.get("face"), "person") if not BLANK_FACE.search(t)]
    parts += _tags(slots.get("build"), "person")[:1]
    # одежда — несущий слот этой модели: сеттинг держится только ею
    parts += _tags(slots.get("wear"), "person")
    parts += _tags(slots.get("tech_marker"), "person")[:1]
    parts += _tags(slots.get("gear"), "person")[:3]
    # место, предмет в нём и дальний план — три слоя, из которых собирается фон.
    # Одним слотом мест фон не строился: модель ставила фигуру на заливку
    parts += _tags(slots.get("location"), "person")[:3]
    parts += _tags(slots.get("place_object"), "person")[:1]
    parts += _tags(slots.get("depth"), "person")[:1]
    return parts


def _frame(slots: dict, kit: dict, view: str) -> list[str]:
    # якорь направления стоит перед словами ГМа: он один говорит модели, к
    # какому классу вещей относится кадр. Без него «boxy hull freighter» со
    # стойками выходил колёсным грузовиком, а станция в открытом космосе —
    # заводом на земле
    anchor = ((kit.get("anchors") or {}).get(f"frame:{view}") or {}).get(
        str(slots.get("anchor", "")).strip())
    parts = _tags(anchor, "frame")[:1] if anchor else []
    parts += _tags(slots.get("subject"), "frame")[:1]
    parts += _tags(slots.get("form"), "frame")
    parts += _tags(slots.get("tech_marker"), "frame")[:1]
    parts += _tags(slots.get("marks"), "frame")[:3]
    parts += _tags(slots.get("surround"), "frame")[:3]
    return parts


def _action(slots: dict) -> list[str]:
    parts = _tags(slots.get("action"), "action")[:1]
    parts += _tags(slots.get("actors"), "action")
    # одежда группы: без неё чекпойнт одевает всех в плитоноску нашего века
    parts += _tags(slots.get("crew"), "action")[:2]
    parts += _tags(slots.get("place"), "action")[:1]
    parts += _tags(slots.get("place_detail"), "action")[:2]
    parts += _tags(slots.get("effects"), "action")[:2]
    return parts


def build_prompt(kind: str, slots: dict, view: str = "interior",
                 kit: dict | None = None) -> str:
    """Голова стиля, рамка, поза, содержание слотами, свет.

    Регистра в строке нет: он доходит до кадра только словарём в инструкции хаба.
    """
    if kit is None:
        from .kit import default_kit

        kit = default_kit()
    parts = [STYLE_HEAD]
    frame_key = view if kind == "frame" else kind
    if kind == "person" and str(slots.get("role", "")).strip() == "machine":
        frame_key = "machine"
    parts += list(FRAMING.get(frame_key, FRAMING["person"]))
    # поза стоит сразу за рамкой: там модель и решает композицию. Без неё
    # персонаж выходит стойкой каталога — фронтально, руки по швам (зонд probe_pose)
    if kind == "person":
        # поза шире прочих слотов: нечеловеческому телу тут перечисляют все пары
        # конечностей, и в девять слов такая фраза не входит
        pose = _tags(slots.get("pose"), "person", 14)[:1]
        # счёт рук держится только первой фразой строки: «four-armed» в описании
        # тела модель уже не слышит и рисует две руки. Квен счёт в позе стабильно
        # опускает («upper pair holding crate»), поэтому он ставится кодом
        limbs = LIMBS.search(" ".join(_tags(slots.get("subject"), "person")))
        if pose and limbs and not LIMBS_DONE.search(pose[0]):
            pose[0] = f"{limbs.group(1).lower()} arms, {pose[0]}"
        parts += pose
    if kind == "person":
        parts += _person(slots, kit)
    elif kind == "frame":
        parts += _frame(slots, kit, view)
    else:
        parts += _action(slots)
    light = _tags(slots.get("light"), "frame" if kind == "frame" else kind)
    parts += light[:1]

    seen, out = set(), []
    for tag in parts:
        tag = re.sub(r"\s+", " ", tag).strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return ", ".join(out[:MAX_TAGS])
