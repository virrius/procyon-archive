"""Гонзо-депеши: событие сектора глазами одного из журналистов кампании.

Правду задаёт ГМ — его слова и привязанные записи (фракции, люди, места,
счётчики); модель пишет три депеши о том, как это событие видно миру.
Журналистов три, манера у всех гонзо, а сторона своя: анархист,
прокорпоративная, провластный — ГМ выбирает, чьими глазами. Подбор промпта —
reports/gonzo_prompt.html. На каждый вызов модели — один шаблон в ките кампании
(news_templates): инструкция, строка «=== ВХОД ===» (у английского экземпляра —
«=== INPUT ===»), вход; данные вставляет код
на место {{…}}. Журналисты, углы и наборы откликов — тоже в ките.
"""
from __future__ import annotations

import random
import re
from collections import Counter

from ..i18n import twin_lang

# английский экземпляр: инструкции, вход модели и всё, что из кита видит ГМ, — по-английски
EN = twin_lang(__name__) == "en"

ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}

# отклики жителей сети — общие для депеш и для откликов к уже выпущенной новости
COMMENTS_RULE = (
    "Жители — разные люди сектора, каждого новость задевает по-своему, и откликаются они со своей колокольни. "
    "who — кто он: занятие и где живёт или работает, из открытых мест сектора; "
    "stake — для себя, не публикуется: чем именно эта новость задевает его самого; "
    "speech — для себя, не публикуется: как говорят люди его занятия и среды — их словечки, обороты и привычки речи; "
    "text — его реплика в сети: в заданной манере, заданной длины и заданным письмом, его говором из speech, "
    "из stake и того, что сказано в новости. "
    "Реплики идут ровно в порядке из раздела «Отклики». "
    "Новых фактов о самом событии жители не знают и не выдумывают. "
    "Голоса автора новости и его стороны в репликах нет."
)
if EN:
    COMMENTS_RULE = (
        "The locals are all kinds of people of the sector; the story touches each of them in their own way, and "
        "each answers from their own corner. "
        "who — who they are: their trade and where they live or work, from the known places of the sector; "
        "stake — for yourself, not published: what exactly in this story touches them personally; "
        "speech — for yourself, not published: how people of their trade and circle talk — their pet words, "
        "turns of phrase and habits of speech; "
        "text — their post on the net: in the given manner, of the given length and written the given way, in "
        "their own voice from speech, out of stake and what the story says. "
        "The posts go exactly in the order of the Comments section. "
        "The locals know no new facts about the event itself and make none up. "
        "The voice of the story's author and their side is absent from the posts."
    )

# манеру каждого отклика раздаёт код: предоставленные сами себе, жители пишут одинаково
COMMENT_MANNERS = {
    "мем": "смеётся над новостью, как в сети смеются над абсурдом",
    "согласие": "соглашается с тем, что сказано в новости, и добавляет, почему — со своей колокольни",
    "несогласие": "не согласен с новостью или с тем, что из неё выводят, и спорит по существу",
    "хейт": "поливает грязью тех, кто в этой истории ему ненавистен, — грубо и зло",
    "по делу": "добавляет к новости то, что знает сам по своему занятию",
    "эмоции": "делится тем, что чувствует, — как новость бьёт по нему лично",
    "постирония": "пишет с постиронией: всерьёз он или в шутку, не разобрать",
}
# длину и письмо тоже раздаёт код: без них аналитик и наёмник писали одинаково грамотные две фразы
COMMENT_LENGTHS = {
    "слова": "пара-тройка слов",
    "фраза": "одна фраза",
    "пара": "две-три фразы",
    "простыня": "развёрнуто, четыре-шесть фраз",
}
COMMENT_WRITING = {
    "грамотно": "грамотно, полными предложениями, со всеми знаками",
    "строчные": "строчными буквами, почти без знаков препинания",
    "ошибки": "с ошибками и опечатками, как слышит",
    "капс": "срываясь на капс и лишние восклицательные знаки",
    "обрывки": "обрывками, без связок",
    "сокращения": "с сетевыми сокращениями и смайлами",
}
if EN:
    COMMENT_MANNERS = {
        "meme": "laughs at the story the way the net laughs at the absurd",
        "agree": "agrees with what the story says and adds why — from their own corner",
        "disagree": "disagrees with the story or with what people read into it, and argues the point",
        "hate": "slings mud at whoever in this story they hate — crude and vicious",
        "on point": "adds to the story what they know firsthand from their own trade",
        "feelings": "shares what they feel — how the story hits them personally",
        "post-irony": "writes in post-irony: no telling whether they mean it or not",
    }
    COMMENT_LENGTHS = {
        "words": "two or three words",
        "line": "one sentence",
        "couple": "two or three sentences",
        "wall of text": "at length, four to six sentences",
    }
    COMMENT_WRITING = {
        "proper": "properly, in full sentences with all the punctuation",
        "lowercase": "in lowercase letters, with almost no punctuation",
        "typos": "with mistakes and typos, spelling by ear",
        "caps": "breaking into caps and extra exclamation marks",
        "fragments": "in fragments, with no connecting words",
        "netspeak": "with net abbreviations and emoticons",
    }
COMMENTS_N = 5

# подписи, из которых код собирает вход модели, и ошибки шаблонов
WORDS = {
    "manner": "манера: ",
    "length": "длина: ",
    "writes": "пишет ",
    "comments": "Отклики, по порядку:",
    "rank": ", ранг ",
    "looks": "Как выглядит: ",
    "done": "исполнен",
    "near": "близок к исполнению",
    "far": "до исполнения далеко",
    "places": "Открытые места сектора:",
    "silent": "ведущий промолчал — событие выбираешь ты, из замыслов причастных",
    "involved": "Причастные и что о них известно миру:",
    "goals": "Замыслы:",
    "angles": "Углы депеш:",
    "no_input": "{name}: нет строки «{mark}» — она отделяет инструкцию от входа",
    "unknown": "{name}: неизвестные вставки {slots}",
}
if EN:
    WORDS = {
        "manner": "manner: ",
        "length": "length: ",
        "writes": "writes ",
        "comments": "Comments, in order:",
        "rank": ", Tier ",
        "looks": "Appearance: ",
        "done": "accomplished",
        "near": "close to accomplished",
        "far": "far from accomplished",
        "places": "Known places of the sector:",
        "silent": "the GM said nothing — you pick the event yourself, out of the goals of those involved",
        "involved": "Those involved and what the world knows about them:",
        "goals": "Goals:",
        "angles": "Dispatch angles:",
        "no_input": '{name}: no "{mark}" line — it separates the instructions from the input',
        "unknown": "{name}: unknown inserts {slots}",
    }


def _texts(kit: dict | None, section: str, default: dict) -> list[str]:
    table = (kit or {}).get(section)
    table = default if table is None else table
    return [str(v).strip() for v in table.values() if str(v or "").strip()]


def _deal(pool: list[str], rng: random.Random) -> list[str]:
    """COMMENTS_N значений: без повторов, пока хватает, а когда их меньше — каждое хотя бы раз."""
    if not pool:
        return [""] * COMMENTS_N
    if len(pool) >= COMMENTS_N:
        return rng.sample(pool, COMMENTS_N)
    out = pool + [rng.choice(pool) for _ in range(COMMENTS_N - len(pool))]
    rng.shuffle(out)
    return out


def pick_manners(kit: dict | None = None, rng: random.Random | None = None) -> list[tuple[str, str, str]]:
    """Пять откликов: тексты манеры, длины и письма из наборов кита."""
    rng = rng or random
    return list(zip(_deal(_texts(kit, "comment_manners", COMMENT_MANNERS), rng),
                    _deal(_texts(kit, "comment_lengths", COMMENT_LENGTHS), rng),
                    _deal(_texts(kit, "comment_writing", COMMENT_WRITING), rng)))


def manners_block(manners: list[tuple[str, str, str]]) -> str:
    def line(manner: str, length: str, writing: str) -> str:
        parts = [WORDS["manner"] + manner if manner else "", WORDS["length"] + length if length else "",
                 WORDS["writes"] + writing if writing else ""]
        return "; ".join(p for p in parts if p)
    return WORDS["comments"] + "\n" + "\n".join(
        f"{i}. {line(*m)}" for i, m in enumerate(manners, 1))


# ники жителей собирает код: модель выводила их из занятия и места («Vos_Lawyer»)
_ONSET = ("b", "br", "d", "dr", "f", "g", "gl", "h", "k", "kr", "l", "m", "n", "p", "r", "s", "sh", "t", "tr",
          "v", "x", "z", "zh")
_VOWEL = ("a", "e", "i", "o", "u", "a", "o", "y", "ei")
_CODA = ("", "", "", "n", "r", "x", "k", "s", "th", "l", "m", "z")


def _word(rng: random.Random, syllables: int) -> str:
    return "".join(rng.choice(_ONSET) + rng.choice(_VOWEL) for _ in range(syllables)) + rng.choice(_CODA)


def random_nick(rng: random.Random | None = None) -> str:
    rng = rng or random
    w = _word(rng, rng.choice((1, 2, 2, 2, 3)))
    form = rng.choices(range(6), weights=(4, 3, 3, 1, 1, 3))[0]
    if form == 0:
        return f"{w}{rng.randint(2, 999)}"
    if form == 1:
        return w.capitalize() + _word(rng, 1).capitalize()
    if form == 2:
        return f"{w}_{_word(rng, 1)}"[:12]
    if form == 3:
        return f"{w.upper()}{rng.randint(1, 99)}" if len(w) <= 5 else w.upper()
    if form == 4:
        return f"xX{w.capitalize()}Xx"
    return w.capitalize()

DISPATCH = {
    "role": "Ты — гонзо-журналист сектора Процион и пишешь от своего лица три депеши об одном событии. Кто ты и чью сторону держишь — в разделе «КТО ТЫ».",
    "task": """ГЛАВНОЕ — СЛОВА ВЕДУЩЕГО. Во входе они идут первыми, и это задание: что случилось и о чём депеши. Всё остальное во входе — причастные и что о них известно, их замыслы, места — только общий контекст ситуации. Контекст помогает поставить событие в мир, но не спорит со словами ведущего и не уводит от них: если они расходятся, прав ведущий. Если ведущий промолчал, событие выбираешь ты — из замыслов причастных, и оно не спорит с контекстом.

ЧИТАТЕЛЬ НИЧЕГО НЕ ЗНАЕТ. Вход видишь только ты: всё, что в нём, читатель узнаёт впервые — из твоей депеши. Поэтому сначала ты сообщаешь саму новость так, чтобы её понял человек, который ни о чём не слышал, и только потом — что нашёл ты и что ты об этом думаешь. Если ведущий говорит, как подать новость — что процитировать, что выделить, — так и подаёшь.""",
    "manner": """ГОНЗО. Ты не наблюдаешь со стороны: ты сам лезешь в историю, и то, что с тобой при этом случилось, — главная часть материала. Пишешь от первого лица, живо и нервно, с перебором и чёрным юмором, и первым под раздачу попадаешь ты сам. Но то, что знаешь, никогда не путаешь с тем, что додумал. Твоя сторона окрашивает всё: что ты замечаешь, кого жалеешь, над кем смеёшься и какой делаешь вывод.""",
    "world": """МИР. Далёкое будущее, приграничный сектор Процион на задворках Гегемонии. Перелёты между звёздами обыденны и обшарпаны: врата, гипертрассы, корабли, которые экипажи латают поколениями. Люди и ксеносы живут бок о бок. Власть делят губернаторский Дом, Легион, гильдии, синдикаты и культы. На планетах лежат руины Предтеч, вокруг которых кормятся учёные, мистики и мародёры. Всё, о чём ты пишешь, происходит здесь.""",
    "law": """МАСШТАБ. Событие ровно такого размера, каким его назвал ведущий. Мелкое событие остаётся мелким по фактам: его видят немногие, и в нём участвуют немногие. Раздувать его может только твой голос — и читателю видно, что раздуваешь ты. Пока замысел не исполнен, в мире видно приближение к нему, а не исполнение.

ВХОД — ЯЗЫК ВЕДУЩЕГО. Слова ведущего ты пересказываешь своими словами, а прямую речь и заявления, которые он дал в кавычках или с именем говорящего, можешь приводить дословно, как цитату. В мире нет счётчиков и шагов, есть событие и его следы, а куда оно ведёт, ты можешь только гадать.

ТЫ ЗНАЕШЬ НЕ ВСЁ. О причастных ты знаешь ровно то, что известно миру, и то, что сказал ведущий. Остальное — догадки, и подаёшь ты их как догадки.

МЕСТА. Планеты, станции и системы — только из списка открытых мест. Мелкие точки внутри них придумываешь сам, каждый раз новые.

ТРИ ДЕПЕШИ — ТРИ ВЗГЛЯДА НА ОДНО СОБЫТИЕ. Новость у них одна — в лиде; репортажи различаются тем, что ты в ней нашёл и как тебе это досталось. Ни одной фразы, общей для двух репортажей.

УГОЛ. Для каждой депеши в контексте задано, с какой стороны ты подбираешься к событию. Угол — откуда ты смотришь, а не замена новости. Депеша держится своего угла, но не называет его.

СВЕЖИЙ ГЛАЗ. Каждая деталь — увиденная впервые в этом месте и нужная этой истории. Дежурная деталь, которая подошла бы к любой депеше, — пустое место.

КТО ТЫ — НЕ ЗАГОТОВКА. Раздел «КТО ТЫ» описывает тебя, а не даёт готовых фраз: его обороты в депешах не звучат. Твоя сторона видна по тому, что ты замечаешь и как судишь.

ФОРМА. Депеша — лид и гонзо-репортаж под ним, по-русски, простым текстом без разметки, вместе 200–300 слов.
lead — один на все три депеши и пишется до них: суть новости, две-три фразы — что случилось, где, кто именно в этом замешан и кто кого в чём обвиняет. Пишешь его ровно, как сводку, без гонзо: по нему читатель понимает новость, даже если дальше читать не станет. Причастных называешь полностью, так, чтобы незнающий понял, о ком речь. Только то, что известно из входа, без твоих догадок и оценок. Лид открывает каждую из трёх депеш.
Дальше три репортажа, у каждого:
angle — для себя, не публикуется: одна строка, как заданный угол ложится на эту историю;
find — первая фраза репортажа: самое неожиданное, что ты узнал в этой истории под этим углом; у трёх депеш находки разные.
headline — заголовок: из него понятно, о каком событии речь, а подан он с твоей стороны; у трёх депеш заголовки разные; обычными буквами, не капсом.
report — продолжение репортажа после находки, четыре-семь фраз от первого лица: как ты её добыл — что сделал, кого встретил, что услышал и чем это обернулось для тебя самого; рассуждения оставь для вывода; ни находку, ни новость из лида заново не пересказываешь;
take — вывод, одна-три фразы: что ты об этом думаешь, твоя догадка и твоё отношение.
У каждого репортажа своё начало, а вывод не пересказывает репортаж.
Ответ — один объект, в нём по порядку lead и dispatches; lead — только его начало.""",
}
if EN:
    DISPATCH = {
        "role": "You are a gonzo journalist of the Procyon sector, and you write three dispatches about one event in your own voice. Who you are and whose side you take is in the WHO YOU ARE section.",
        "task": """WHAT MATTERS MOST IS THE GM'S WORDS. They open the input, and they are the assignment: what happened and what the dispatches are about. Everything else in the input — those involved and what is known about them, their goals, the places — is only the general context of the situation. The context helps you set the event in the world, but it never argues with the GM's words or pulls you away from them: where the two disagree, the GM is right. If the GM said nothing, you pick the event yourself — out of the goals of those involved, and it does not contradict the context.

THE READER KNOWS NOTHING. Only you see the input: everything in it the reader learns for the first time — from your dispatch. So first you report the news itself so that someone who has heard nothing at all understands it, and only then what you found and what you make of it. If the GM says how to present the news — what to quote, what to put up front — that is how you present it.""",
        "manner": """GONZO. You don't watch from the sidelines: you climb into the story yourself, and what happened to you along the way is the heart of the piece. You write in the first person, alive and jittery, over the top and with black humor, and the first one to catch it is always you. But you never mix up what you know with what you made up. Your side colors everything: what you notice, whom you pity, whom you laugh at and what conclusion you draw.""",
        "world": """THE WORLD. The far future, the Procyon sector, a frontier on the edge of the Hegemony. Travel between the stars is routine and shabby: jumpgates, hyperspace lanes, ships their crews have been patching for generations. Humans and xenos live side by side. Power is split between the Governor's House, the Legion, the Guilds, the syndicates and the Cults. The planets hold Precursor ruins, and scholars, mystics and scavengers make their living around them. Everything you write about happens here.""",
        "law": """SCALE. The event is exactly as big as the GM made it. A small event stays small in its facts: few people see it and few take part in it. Only your voice can blow it up — and the reader can tell that it is you doing the blowing. Until a goal is accomplished, the world sees it drawing near, not done.

THE INPUT IS THE GM'S LANGUAGE. You retell the GM's words in your own, but direct speech and statements they gave in quotation marks or with the speaker's name you may quote word for word. The world has no clocks and no segments, only the event and its traces, and where it leads you can only guess.

YOU DON'T KNOW EVERYTHING. About those involved you know exactly what the world knows and what the GM said. The rest is guesswork, and you present it as guesswork.

PLACES. Planets, stations and systems come only from the list of known places. Small spots inside them you invent yourself, new ones every time.

THREE DISPATCHES — THREE VIEWS OF ONE EVENT. They share one piece of news — in the lead; the reports differ in what you found in it and how you came by it. Not a single sentence shared by two reports.

ANGLE. For each dispatch the context sets which side you come at the event from. The angle is where you look from, not a substitute for the news. A dispatch keeps to its angle but never names it.

A FRESH EYE. Every detail is seen for the first time in this place and is needed by this story. A stock detail that would fit any dispatch is dead space.

WHO YOU ARE IS NOT A SCRIPT. The WHO YOU ARE section describes you; it does not hand you ready-made lines: its phrases never turn up in the dispatches. Your side shows in what you notice and how you judge it.

FORM. A dispatch is a lead with a gonzo report under it, in English, plain text with no markup, 200–300 words together.
lead — one for all three dispatches, written before them: the gist of the news in two or three sentences — what happened, where, who exactly is mixed up in it and who accuses whom of what. You write it flat, like a bulletin, with no gonzo: from it alone the reader understands the news even if they read no further. Name those involved in full, so that someone who has never heard of them knows who is meant. Only what is known from the input, with none of your guesses or judgments. The lead opens each of the three dispatches.
Then three reports, each with:
angle — for yourself, not published: one line on how the given angle falls on this story;
find — the first sentence of the report: the most unexpected thing you learned in this story from this angle; the three dispatches have different finds.
headline — the headline: it makes clear which event this is about, and it is pitched from your side; the three dispatches have different headlines; in ordinary letters, not all caps.
report — the rest of the report after the find, four to seven sentences in the first person: how you got hold of it — what you did, whom you met, what you heard and what it turned into for you yourself; save the reasoning for the take; you never retell the find or the news from the lead;
take — the conclusion, one to three sentences: what you think of it, your guess and where you stand.
Each report opens its own way, and the take does not retell the report.
The answer is one object holding, in order, lead and dispatches; lead is only its beginning.""",
    }

# Строка входа и имена вставок — на языке экземпляра, но код понимает оба набора:
# шаблон в базе мог быть написан на любом из языков
INPUT_MARKS = ("=== ВХОД ===", "=== INPUT ===")
INPUT_MARK = INPUT_MARKS[1] if EN else INPUT_MARKS[0]
_INPUT_LINE = re.compile(r"^[ \t]*(?:" + "|".join(map(re.escape, INPUT_MARKS)) + r")[ \t]*$", re.MULTILINE)
_SLOT = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
# русское имя вставки → английское
SLOT_NAMES = {"персона": "persona", "слова_ведущего": "gm_words", "причастные": "involved", "замыслы": "goals",
              "углы": "angles", "места": "places", "новость": "story", "отклики": "comments"}
# задание сразу за ролью, персона журналиста — перед манерой
NEWS_TEMPLATES = {
    "dispatch": "\n\n".join([
        DISPATCH["role"], DISPATCH["task"], "{{персона}}", DISPATCH["manner"], DISPATCH["world"], DISPATCH["law"],
        INPUT_MARK,
        "СЛОВА ВЕДУЩЕГО — ГЛАВНОЕ:\n{{слова_ведущего}}",
        "ОБЩИЙ КОНТЕКСТ СИТУАЦИИ",
        "{{причастные}}", "{{замыслы}}", "{{углы}}", "{{места}}",
    ]),
    "comments": "\n\n".join([
        "Ты пишешь, что жители сектора Процион пишут в сети о новости, которую только что прочли.",
        DISPATCH["world"],
        "ФОРМА. comments — пять реплик. " + COMMENTS_RULE,
        INPUT_MARK,
        "НОВОСТЬ:\n{{новость}}",
        "{{отклики}}", "{{места}}",
    ]),
}
if EN:
    NEWS_TEMPLATES = {
        "dispatch": "\n\n".join([
            DISPATCH["role"], DISPATCH["task"], "{{persona}}", DISPATCH["manner"], DISPATCH["world"], DISPATCH["law"],
            INPUT_MARK,
            "THE GM'S WORDS — WHAT MATTERS MOST:\n{{gm_words}}",
            "GENERAL CONTEXT OF THE SITUATION",
            "{{involved}}", "{{goals}}", "{{angles}}", "{{places}}",
        ]),
        "comments": "\n\n".join([
            "You write what the locals of the Procyon sector post on the net about a story they have just read.",
            DISPATCH["world"],
            "FORM. comments — five posts, in English. " + COMMENTS_RULE,
            INPUT_MARK,
            "THE STORY:\n{{story}}",
            "{{comments}}", "{{places}}",
        ]),
    }
# что код подставляет на место вставки; пустая вставка выпадает вместе с отступом перед ней
NEWS_SLOTS = {
    "dispatch": {
        "персона": "кто такой выбранный журналист — его персона из «Журналистов»",
        "слова_ведущего": "что ГМ написал в заказе; если ничего — просьба выбрать событие из замыслов причастных",
        "причастные": "привязанные записи и всё, что о них открыто столу, с заголовком",
        "замыслы": "привязанные счётчики словами — чей замысел и насколько он близок, с заголовком",
        "углы": "три угла из «Углов», по одному на депешу, с заголовком",
        "места": "места, открытые столу, с заголовком",
    },
    "comments": {
        "новость": "заголовок, суть и текст новости; у заказа депеш — только суть",
        "отклики": "пять откликов: манера, длина и письмо каждого из наборов ниже, с заголовком",
        "места": "места, открытые столу, с заголовком",
    },
}
if EN:
    NEWS_SLOTS = {
        "dispatch": {
            "persona": "who the chosen journalist is — their persona from Journalists",
            "gm_words": "what the GM wrote in the order; if nothing — a request to pick the event from the goals "
                        "of those involved",
            "involved": "linked entries and everything about them that is open to the table, with a heading",
            "goals": "linked clocks in words — whose goal it is and how close, with a heading",
            "angles": "three angles from Dispatch angles, one per dispatch, with a heading",
            "places": "places open to the table, with a heading",
        },
        "comments": {
            "story": "the headline, gist and text of the story; for ordered dispatches — the gist only",
            "comments": "five comments: the manner, length and writing of each from the sets below, with a heading",
            "places": "places open to the table, with a heading",
        },
    }


def _known(slots: dict) -> set[str]:
    """Вставки шаблона под обоими именами."""
    back = {en: ru for ru, en in SLOT_NAMES.items()}
    return set(slots) | {SLOT_NAMES.get(s) or back.get(s, s) for s in slots}


def check_templates(templates: dict) -> list[str]:
    """Ошибки шаблонов: нет строки входа или вставка, которую код не знает."""
    errors = []
    for name, slots in NEWS_SLOTS.items():
        text = str(templates.get(name) or "")
        if not text.strip():
            continue
        if not _INPUT_LINE.search(text):
            errors.append(WORDS["no_input"].format(name=name, mark=INPUT_MARK))
        known = _known(slots)
        unknown = sorted({s for s in _SLOT.findall(text) if s not in known})
        if unknown:
            errors.append(WORDS["unknown"].format(name=name, slots=", ".join("{{" + s + "}}" for s in unknown)))
    return errors


def news_template(kit: dict, name: str) -> str:
    text = str((kit.get("news_templates") or {}).get(name) or "")
    return text if _INPUT_LINE.search(text) else NEWS_TEMPLATES[name]


def _render(text: str, values: dict) -> str:
    for name, value in values.items():
        if not str(value or "").strip():
            text = re.sub(r"\n*\{\{\s*" + re.escape(name) + r"\s*\}\}", "", text)
    return _SLOT.sub(lambda m: str(values.get(m.group(1), m.group(0))), text).strip()


def _aliased(values: dict) -> dict:
    """Значения под обоими именами вставок."""
    out = dict(values)
    for ru, en in SLOT_NAMES.items():
        if en in values:
            out.setdefault(ru, values[en])
        elif ru in values:
            out.setdefault(en, values[ru])
    return out


def fill(template: str, values: dict) -> tuple[str, str]:
    """Шаблон → (инструкция, вход) с подставленными данными."""
    system, user = _INPUT_LINE.split(template, maxsplit=1)
    values = _aliased(values)
    return _render(system, values), _render(user, values)

# подпись клеит код: позывной модель переводила («Лазарь», «Лазарус»)
DISPATCH_JOURNALISTS = {
    "lazarus": {
        "title": "Lazarus — анархист",
        "persona": """КТО ТЫ. Лазарь Кинкейд, позывной Lazarus. Бывший внештатник Новостной Сети Гегемонии: продавал ей репортажи поштучно, пока его не вышвырнули за то, что он писал правду громче, чем за неё платили. Теперь вещает сам, на открытых частотах, с челнока, который не задерживается в одном порту дольше двух ночей.
Нейтрал-анархист: не служит никому и не болеет ни за кого. Губернатор, Легион, гильдии, синдикаты, культы, пираты и бунтари для него одинаково — власть, которая хочет, чтобы о ней молчали; никому он не подыгрывает и ни у кого не берёт денег. В любом событии он ищет, кто из сильных на нём наживается, и смотрит на тех, кому от этого достаётся.
Живёт на износ и не скрывает этого. Параноик: ему везде мерещится заговор, и иногда он оказывается прав.""",
        "signature": "Lazarus — и вам меня не заглушить!",
    },
    "sterling": {
        "title": "Sterling — прокорпоративная",
        "persona": """КТО ТЫ. Аурелия Вейс, позывной Sterling; ты женщина и о себе пишешь в женском роде. Ведущая деловой ленты, которую оплачивают торговые гильдии и корпорации сектора, — и она этого не стесняется: деньги, по её мнению, единственное, что в Проционе говорит правду. Живёт в мире больших денег и за чужой счёт.
Прокорпоративна: верит, что порядок держат контракты, а не флаги, и что гильдии сделают для сектора больше, чем губернатор и культы вместе взятые. Её глазами любое событие — сделка: кто на нём заработал, кто потерял, где риск и где возможность. Беспорядки, бедность и бунтарей она разбирает как рыночные явления, без сантиментов.
Обаятельна и цинична; пострадавшим сочувствует искренне, но расчёт у неё всегда впереди.""",
        "signature": "Sterling — деньги не спят, и я тоже.",
    },
    "herald": {
        "title": "Herald — провластный",
        "persona": """КТО ТЫ. Корвин Дейл, позывной Herald. Аккредитованный военный корреспондент при Легионе: свой человек среди офицеров и в губернаторской канцелярии. Его эфир идёт по официальным каналам Гегемонии.
Провластный: верит, что сектор держится только на законе, мундире и твёрдой руке — губернаторского Дома, Легиона и Гегемонии за ними. Его глазами любое событие — вопрос порядка: кто его нарушил, кто встал на защиту и что пора закрутить потуже. Когда власть бьёт — по врагам или по своим, — он видит в этом наведение порядка и аплодирует; когда власти грызутся между собой, он на стороне того, кто наводит порядок жёстче. Пиратов, культистов и бунтарей считает заразой, а гильдиям не доверяет, даже когда они на стороне власти. В начальстве он сомневается только вполголоса и не в эфире, а в эфир выходит за власть.
Восторжен, патетичен и самоироничен; страшное описывает как сводку с фронта, а себя — как человека, которому ещё повезло.""",
        "signature": "Herald — Гегемония слышит, Гегемония помнит.",
    },
}
if EN:
    DISPATCH_JOURNALISTS = {
        "lazarus": {
            "title": "Lazarus — anarchist",
            "persona": """WHO YOU ARE. Lazarus Kincaid, call sign Lazarus. A former freelancer for the Hegemonic News Network: he sold it reports by the piece until they threw him out for telling the truth louder than they paid for it. Now he broadcasts on his own, on open frequencies, from a shuttle that never stays in one port longer than two nights.
A neutral anarchist: he serves no one and roots for no one. The Governor, the Legion, the Guilds, the syndicates, the Cults, pirates and rebels are all the same to him — power that wants to be kept quiet about; he plays along with none of them and takes money from no one. In any event he looks for which of the powerful is cashing in on it, and he watches the people it lands on.
He runs himself ragged and doesn't hide it. Paranoid: he sees a conspiracy everywhere, and sometimes he turns out to be right.""",
            "signature": "Lazarus — and you can't shut me up!",
        },
        "sterling": {
            "title": "Sterling — pro-corporate",
            "persona": """WHO YOU ARE. Aurelia Weiss, call sign Sterling; you are a woman. The host of a business feed paid for by the trade Guilds and corporations of the sector — and she isn't shy about it: money, as she sees it, is the only thing in Procyon that tells the truth. She lives in a world of big money, on someone else's tab.
Pro-corporate: she believes order is held together by contracts, not flags, and that the Guilds will do more for the sector than the Governor and the Cults put together. Through her eyes every event is a deal: who made money on it, who lost, where the risk is and where the opportunity. Riots, poverty and rebels she takes apart as market phenomena, without sentiment.
Charming and cynical; her sympathy for the victims is sincere, but the bottom line always comes first.""",
            "signature": "Sterling — money never sleeps, and neither do I.",
        },
        "herald": {
            "title": "Herald — loyalist",
            "persona": """WHO YOU ARE. Corvin Dale, call sign Herald. An accredited war correspondent embedded with the Legion: one of their own among the officers and in the Governor's chancery. His broadcasts go out over the official channels of the Hegemony.
A loyalist: he believes the sector holds together only by law, the uniform and a firm hand — the hand of the Governor's House, of the Legion and of the Hegemony behind them. Through his eyes every event is a question of order: who broke it, who stood up for it and what needs tightening. When power strikes — at its enemies or at its own — he sees order being restored and applauds; when the powers squabble among themselves, he sides with whoever restores order harder. Pirates, cultists and rebels are a plague to him, and he doesn't trust the Guilds even when they side with power. He doubts his superiors only under his breath and never on air, and on air he speaks for power.
Rapturous, grandiloquent and self-mocking; he describes horrors like a bulletin from the front, and himself as a man whose luck has held so far.""",
            "signature": "Herald — the Hegemony hears, the Hegemony remembers.",
        },
    }

# угол депеши раздаёт код: модель, предоставленная самой себе, трижды идёт в бар
DISPATCH_LENSES = {
    "на месте": "ты оказался там, где это происходило, в тот самый момент",
    "изнутри": "ты добрался до того, кто в этом участвовал, и он проговорился",
    "рябь": "ты видишь последствия далеко от места событий — у тех, кого задело стороной",
    "официоз": "есть официальная версия, и ты видишь, что под ней",
    "деньги": "ты смотришь, кто на этом заработал, а кто потерял",
    "толпа": "ты слушаешь, как это обсуждают простые люди, и что они из этого сочинили",
}
if EN:
    DISPATCH_LENSES = {
        "on the scene": "you were right where it happened, at the very moment it happened",
        "insider": "you got to someone who took part in it, and they let something slip",
        "ripples": "you see the consequences far from where it happened — among those it hit sideways",
        "official line": "there is an official version, and you see what lies under it",
        "money": "you look at who made money on this and who lost",
        "crowd": "you listen to how ordinary people talk about it and what they have made up about it",
    }

COMMENT_ITEMS = {
    "type": "array",
    "minItems": COMMENTS_N,
    "maxItems": COMMENTS_N,
    "items": {
        "type": "object",
        # stake — чем новость задевает жителя: без него реплики выходили
        # пустыми шутками и выдумками о самом событии
        "properties": {k: {"type": "string"} for k in ("who", "stake", "speech", "text")},
        "required": ["who", "stake", "speech", "text"],
        "additionalProperties": False,
    },
}

DISPATCH_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "GonzoDispatches",
        "schema": {
            "type": "object",
            "properties": {
                # суть новости — одна на все три и пишется до них: внутри депеши
                # угол уводил от того, что случилось, и читатель новости не понимал
                "lead": {"type": "string"},
                "dispatches": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "angle": {"type": "string"},
                            # начало репортажа — полем схемы: просьбу «начни с находки»
                            # модель не держала и открывала депешу собой на месте
                            "find": {"type": "string"},
                            "headline": {"type": "string"},
                            # абзацы — полями схемы: просьба «разбей на абзацы»
                            # текстом инструкции держится хуже, чем форма ответа
                            "report": {"type": "string"},
                            "take": {"type": "string"},
                        },
                        "required": ["angle", "find", "headline", "report", "take"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["lead", "dispatches"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

# ниже 0.8 три депеши начинают кончаться одной и той же фразой
TEMPERATURE = 0.8
MAX_TOKENS = 5000
COMMENTS_MAX_TOKENS = 2500
DISPATCH_TIMEOUT = 300
# gemma, решив, что ответ кончился, сыплет переносами до max_tokens: обрываем на пустой строке и повторяем
DISPATCH_STOP = ["\n\n"]
# английский ответ ставит пустую строку между полями JSON — там обрываем только на сыпи переносов
if EN:
    DISPATCH_STOP = ["\n\n\n"]
DISPATCH_ATTEMPTS = 3


def journalists_of(kit: dict) -> dict:
    """Журналисты кампании: ключ → {title, persona, signature}. Пустая персона — не журналист."""
    staff = kit.get("dispatch_journalists")
    staff = DISPATCH_JOURNALISTS if staff is None else staff
    return {k: v for k, v in staff.items() if isinstance(v, dict) and str(v.get("persona") or "").strip()}


def pick_journalist(kit: dict, key: str = "") -> str:
    """Чьими глазами пишем: названный ГМом, иначе первый по списку кита."""
    staff = journalists_of(kit)
    if key:
        return key if key in staff else ""
    return next(iter(staff), "")


def byline(journalist: dict, key: str) -> str:
    """Позывной для ленты новостей: подпись или название до тире."""
    for text in (journalist.get("signature"), journalist.get("title")):
        head = re.split(r"\s+[—–-]\s+", str(text or "").strip(), maxsplit=1)[0].strip()
        if head:
            return head
    return key


def lenses_of(kit: dict) -> dict:
    lenses = kit.get("dispatch_lenses") or DISPATCH_LENSES
    return {k: str(v).strip() for k, v in lenses.items() if str(v or "").strip()}


def pick_lenses(kit: dict, wanted: list[str] | None = None, rng: random.Random | None = None) -> list[str]:
    """Три разных угла: названные ГМом — как есть, недостающие добираются случайно."""
    pool = list(lenses_of(kit))
    chosen = [k for k in (wanted or []) if k in pool][:3]
    rest = [k for k in pool if k not in chosen]
    (rng or random).shuffle(rest)
    return chosen + rest[: 3 - len(chosen)]


def gazetteer(locations: list) -> str:
    rows = []
    for loc in locations:
        system = str((loc.fields or {}).get("system") or "").strip()
        first = (loc.summary or "").split(".")[0].strip()
        rows.append(f"• {loc.name}" + (f" ({system})" if system else "") + (f" — {first}." if first else ""))
    return "\n".join(rows)


WHO = {"faction": "организация", "npc": "человек", "character": "человек", "crew": "экипаж",
       "location": "место", "ship": "корабль", "item": "вещь", "job": "дело"}
if EN:
    WHO = {"faction": "faction", "npc": "person", "character": "person", "crew": "crew",
           "location": "place", "ship": "ship", "item": "item", "job": "job"}


def portrait(entity, blocks: list) -> str:
    """Что миру известно о причастном: сводка, внешность и открытые столу блоки."""
    rank = ROMAN.get(str((entity.fields or {}).get("rank") or ""), "")
    head = f"{entity.name} — {WHO.get(entity.kind, entity.kind)}" + (WORDS["rank"] + rank if rank else "")
    known = [entity.summary or ""]
    looks = (entity.fields or {}).get("gm_appearance")
    if looks:
        known.append(f"{WORDS['looks']}{looks}")
    known += [f"{b.title}:\n{b.content.strip()}" for b in blocks if (b.content or "").strip()]
    known = [k.strip() for k in known if k.strip()]
    return "\n".join([head, *known])


def goal_line(clock, owner_name: str = "") -> str:
    """Замысел со счётчика. Состояние словами: числа модель вклеивает в депешу."""
    goal = clock.name.strip() + (f" — {clock.description.strip()}" if (clock.description or "").strip() else "")
    if clock.segments and clock.filled >= clock.segments:
        state = WORDS["done"]
    elif clock.segments and clock.filled * 2 >= clock.segments:
        state = WORDS["near"]
    else:
        state = WORDS["far"]
    return f"• {owner_name + ': ' if owner_name else ''}{goal} ({state})"


def places_block(locations: list | None) -> str:
    return WORDS["places"] + "\n" + gazetteer(locations) if locations else ""


def dispatch_prompt(kit: dict, journalist: str, *, gm_text: str, entities: list[tuple], goals: list[tuple],
                    locations: list | None = None, lenses: list[str]) -> tuple[str, str]:
    """Инструкция и вход депеш: слова ГМа первыми, остальное — общим контекстом.

    entities — пары (запись, открытые блоки), goals — пары (счётчик, чей замысел).
    Закулисье сюда не попадает вовсе: запрет «ты этого не знаешь» модель не
    держит, и досье из книги утекало в депеши почти целиком.
    """
    texts = lenses_of(kit)
    return fill(news_template(kit, "dispatch"), {
        "persona": journalists_of(kit)[journalist]["persona"].strip(),
        "gm_words": gm_text.strip() or WORDS["silent"],
        "involved": WORDS["involved"] + "\n\n" + "\n\n".join(portrait(e, b) for e, b in entities)
                    if entities else "",
        "goals": WORDS["goals"] + "\n" + "\n".join(goal_line(c, who) for c, who in goals) if goals else "",
        "angles": WORDS["angles"] + "\n" + "\n".join(f"{i}. {texts[k]}" for i, k in enumerate(lenses, 1)),
        "places": places_block(locations),
    })


_MARKUP = re.compile(r"(\*{1,2}|_{2})(?=\S)(.+?)(?<=\S)\1")


def clean(text: str) -> str:
    """Депеша — простой текст: курсив звёздочками модель изредка всё же ставит."""
    return _MARKUP.sub(r"\2", str(text or "")).strip()


def sign(text: str, signature: str) -> str:
    """Депеша с подписью журналиста. Если модель всё же подписалась сама, её подпись
    срезается: в своей она путает позывной."""
    body = clean(text)
    signature = str(signature or "").strip()
    if not signature:
        return body
    slogan = re.split(r"\s+[—–-]\s+", signature, maxsplit=1)[-1].rstrip("!. ")
    words = r"\s+".join(re.escape(w) for w in slogan.split())
    tail = re.compile(r"[\s—–-]*(?:[^\s.!?]+\s*[—–-]\s*)?" + words + r"[!.]*\s*$", re.IGNORECASE)
    return f"{tail.sub('', body).rstrip()}\n\n{signature}"


_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def _norm(sentence: str) -> str:
    return re.sub(r"\W+", " ", sentence.lower()).strip()


def _sentences(text: str) -> list[str]:
    return [x for x in _SENTENCE.split(text) if x.strip()]


COMMENTS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "NewsComments",
        "schema": {
            "type": "object",
            "properties": {"comments": COMMENT_ITEMS},
            "required": ["comments"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def comments_prompt(kit: dict, *, headline: str = "", lead: str = "", body: str = "", locations: list | None = None,
                    manners: list[tuple[str, str, str]] | None = None) -> tuple[str, str]:
    """Инструкция и вход откликов жителей к новости."""
    return fill(news_template(kit, "comments"), {
        "story": "\n\n".join(x.strip() for x in (headline, lead, body) if (x or "").strip()),
        "comments": manners_block(manners or pick_manners(kit)),
        "places": places_block(locations),
    })


def clean_comments(raw: list | None, rng: random.Random | None = None) -> list[dict]:
    """Отклики для ленты: ник — случайный, stake и speech — подсказки модели, наружу не идут."""
    return [{"handle": random_nick(rng), "who": clean(x.get("who")), "text": clean(x.get("text"))}
            for x in raw or [] if isinstance(x, dict) and clean(x.get("text"))]


def _period(text: str) -> str:
    return text + "." if text and text[-1] not in ".!?…»\"" else text


def compose(lead: str, items: list[dict], signature: str) -> list[str]:
    """Тексты депеш набора: находка и репортаж, вывод, подпись журналиста. Суть — отдельным полем.

    Фраза вывода, общая для двух депеш, выпадает из всех; фраза сути или вывода,
    повторённая в репортаже, и повтор внутри репортажа — из репортажа.
    """
    lead = clean(lead)
    said = {_norm(x) for x in _sentences(lead)}
    paras = [[_sentences(" ".join(x for x in (_period(clean(it.get("find"))), clean(it.get("report"))) if x)),
              _sentences(clean(it.get("take")))] for it in items]
    counts = Counter(n for _, take in paras for n in {_norm(x) for x in take})
    texts = []
    for report, take in paras:
        take = [x for x in take if counts[_norm(x)] < 2]
        seen = said | {_norm(x) for x in take}
        kept = []
        for x in report:
            if _norm(x) not in seen:
                seen.add(_norm(x))
                kept.append(x)
        body = [" ".join(kept), " ".join(take)]
        texts.append(sign("\n\n".join(p for p in body if p), signature))
    return texts
