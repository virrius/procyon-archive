from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine

log = logging.getLogger("dbpatch")

# Схема живых баз догоняет модели: create_all заводит новые таблицы, а колонки,
# добавленные или снятые в моделях, правятся здесь. Каждая запись идемпотентна;
# записи, которые уже прошли на всех известных базах, отсюда убираются.

# (table, column, type + null/default clause)
_COLUMNS: list[tuple[str, str, str]] = []

_DROP_TABLES: list[str] = [
    # «заметки»-обсуждения: интерфейс снят 09.10.2026, на обоих экземплярах таблица пуста
    "notes",
    # тики счётчиков прежнего вида: история счётчика давно читается из журнала событий
    "clock_events",
]

_DROP_COLUMNS: list[tuple[str, str]] = [
    # инструкции слотовой сборки и рендерер: сборка теперь одна, прозой
    ("campaigns", "img_meta_prompt"),
    ("campaigns", "img_object_prompt"),
    ("campaigns", "img_scene_prompt"),
    ("campaigns", "img_inpaint_prompt"),
    ("campaigns", "img_renderer"),
    ("server_settings", "img_meta_prompt"),
    ("server_settings", "img_object_prompt"),
    ("server_settings", "img_scene_prompt"),
    # хаб — настройка сервера, у кампании его больше нет
    ("campaigns", "img_base_url"),
    ("campaigns", "img_model"),
    ("campaigns", "img_api_key"),
    ("campaigns", "news_base_url"),
    ("campaigns", "news_model"),
    ("campaigns", "news_api_key"),
    # негатив рисующая модель не читает (Z-Image, cfg 1.0)
    ("image_gen_jobs", "negative_prompt"),
    # поля без читателя: статус знания и раскладка карты прежних версий
    ("entities", "knowledge_status"),
    ("entity_links", "knowledge_status"),
    ("content_blocks", "knowledge_status"),
    ("clocks", "knowledge_status"),
    ("messages", "knowledge_status"),
    ("news", "knowledge_status"),
    ("map_nodes", "knowledge_status"),
    ("map_markers", "knowledge_status"),
    ("map_strokes", "knowledge_status"),
    ("attachments", "knowledge_status"),
    ("map_nodes", "order"),
    ("map_nodes", "x"),
    ("map_nodes", "y"),
    ("map_nodes", "node_kind"),
    ("map_nodes", "color"),
    ("map_markers", "orbit"),
    ("map_markers", "status"),
    ("map_markers", "layer"),
    ("map_strokes", "layer"),
]


def _statements() -> list[str]:
    out = [
        f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
        for table, column, ddl in _COLUMNS
    ]
    out += [f"DROP TABLE IF EXISTS {table}" for table in _DROP_TABLES]
    out += [
        f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"'
        for table, column in _DROP_COLUMNS
    ]
    return out


def patch_schema() -> None:
    """Догнать схему живой базы. Сбой оператора — ошибка в логе: тихо пропущенный ALTER
    всплывёт потом падением на вставке."""
    for sql in _statements():
        # своя транзакция на оператор: Postgres после ошибки откатывает всю
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            log.exception("dbpatch failed [%s]", sql)
