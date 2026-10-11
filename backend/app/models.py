from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class PK:
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uid)


class Stamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


# --- accounts -----------------------------------------------------------------


class User(Base, PK, Stamps):
    __tablename__ = "users"
    login: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # пароль выдан по умолчанию (первый админ): пока не сменён, API пускает только в /auth/me и /auth/password
    password_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # растёт при смене пароля: токены со старым номером больше не принимаются
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class Campaign(Base, PK, Stamps):
    __tablename__ = "campaigns"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    # язык стартовых материалов: канон, карта, корабль, вырезки правил; заведённое так и остаётся
    lang: Mapped[str] = mapped_column(String(5), default="")
    members: Mapped[list[CampaignMember]] = relationship(back_populates="campaign")

    # --- генерация картинок: редактируемые инструкции для LLM-хаба
    # (OpenAI-совместимый API), который собирает из описания ГМа слоты промпта для
    # рисующей модели. Пусто — берётся голова из набора блоков (prompting/kit.py) ---
    # инструкция для персонажа
    img_meta_prompt: Mapped[str] = mapped_column(Text, default="")
    # инструкция для предмета: корабль, оружие, артефакт — всё, внутри чего никого нет
    img_object_prompt: Mapped[str] = mapped_column(Text, default="")
    # инструкция для локации: на входе описание места от ГМа, а не карточка сущности
    img_scene_prompt: Mapped[str] = mapped_column(Text, default="")
    # третья инструкция: правка уже готовой картинки по маске. На входе исходный
    # промпт кадра и просьба ГМа переписать область (см. DEFAULT_INPAINT_META_PROMPT)
    img_inpaint_prompt: Mapped[str] = mapped_column(Text, default="")
    # остальные блоки промпт-кита, которые правит ГМ: планы персонажа, словари
    # регистров, разметка слотов, списки нот, негативы и манеры. JSON с только теми
    # ключами, что ГМ действительно менял — остальное берётся из кода
    img_prompt_kit: Mapped[str] = mapped_column(Text, default="")
    # рисующая модель: у SDXL промпт — теги с весами и рабочий негатив, у z-image
    # теги без весов и без негатива вовсе. Профиль выбирает рендерер сборки, и от
    # него зависит, какие поля вообще имеют смысл в окне кадра
    img_renderer: Mapped[str] = mapped_column(String(20), default="zimage")
    img_base_url: Mapped[str] = mapped_column(String(300), default="")
    img_model: Mapped[str] = mapped_column(String(100), default="")
    img_api_key: Mapped[str] = mapped_column(String(200), default="")
    # хаб депеш и откликов; пустые адрес, модель и ключ — те же, что у картинок
    news_base_url: Mapped[str] = mapped_column(String(300), default="")
    news_model: Mapped[str] = mapped_column(String(100), default="")
    news_api_key: Mapped[str] = mapped_column(String(200), default="")
    # игровое время — дней от 1261.1.1; год, неделя и день недели считаются из него
    world_day: Mapped[int] = mapped_column(Integer, default=0)


class ServerSettings(Base):
    """Настройки сервера, общие для всех кампаний: хаб, модели и промпты.
    Одна строка с id «main»; пустое поле — значение кампании (переходный период)."""

    __tablename__ = "server_settings"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="main")
    hub_base_url: Mapped[str] = mapped_column(String(300), default="")
    hub_api_key: Mapped[str] = mapped_column(String(200), default="")
    img_model: Mapped[str] = mapped_column(String(100), default="")
    news_model: Mapped[str] = mapped_column(String(100), default="")
    # кто рисует: worker | api; протокол сервиса hub_draw определяет по ответу.
    # Адрес и ключ рисования пусты — берутся от текста
    draw_kind: Mapped[str] = mapped_column(String(20), default="")
    draw_model: Mapped[str] = mapped_column(String(100), default="")
    draw_base_url: Mapped[str] = mapped_column(String(300), default="")
    draw_api_key: Mapped[str] = mapped_column(String(200), default="")
    # смысл колонок тот же, что у одноимённых в campaigns
    img_meta_prompt: Mapped[str] = mapped_column(Text, default="")
    img_object_prompt: Mapped[str] = mapped_column(Text, default="")
    img_scene_prompt: Mapped[str] = mapped_column(Text, default="")
    img_inpaint_prompt: Mapped[str] = mapped_column(Text, default="")
    # инструкции хабу под сборку прозой; прежние img_*_prompt писались под слоты
    img_prose_person: Mapped[str] = mapped_column(Text, default="")
    img_prose_frame: Mapped[str] = mapped_column(Text, default="")
    img_prose_action: Mapped[str] = mapped_column(Text, default="")
    # правки набора без гардероба: гардероб остаётся у кампании
    img_prompt_kit: Mapped[str] = mapped_column(Text, default="")
    # язык экземпляра: интерфейс, канон книги, генерация; пусто — русский
    lang: Mapped[str] = mapped_column(String(5), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class CampaignMember(Base, PK, Stamps):
    __tablename__ = "campaign_members"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="player")  # gm|player|observer
    display_name: Mapped[str] = mapped_column(String(120), default="")
    campaign: Mapped[Campaign] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


# --- content ------------------------------------------------------------------


class VisMixin:
    """crew | selected | owner | gm"""

    visibility: Mapped[str] = mapped_column(String(20), default="crew")
    visible_to: Mapped[list] = mapped_column(JSONB, default=list)
    # не читается; в живой базе NOT NULL без DEFAULT — ORM заполняет, пока колонку не снесут
    knowledge_status: Mapped[str] = mapped_column(String(20), default="confirmed")


class Entity(Base, PK, Stamps, VisMixin):
    """Generic record: person, npc, faction, ship, crew, location, item."""

    __tablename__ = "entities"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    alias: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    faction_ids: Mapped[list] = mapped_column(JSONB, default=list)
    location_ids: Mapped[list] = mapped_column(JSONB, default=list)
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    owner_member_id: Mapped[str | None] = mapped_column(String(64))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # что ГМ пока не открыл игрокам: имена колонок карточки и ключи fields
    hidden_fields: Mapped[list] = mapped_column(JSONB, default=list)
    # снимок формы генерации: направление, регистр, манера, слоты, промпт. Живёт на
    # карточке, а не на заявке, — заявку сносит отмена, а следующий кадр почти всегда
    # правится от предыдущего. Столу не отдаётся: это кухня ГМа
    gen_form: Mapped[dict] = mapped_column(JSONB, default=dict)


class EntityLink(Base, PK, Stamps, VisMixin):
    """Directed link between two entities; every link carries its own visibility."""

    __tablename__ = "entity_links"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    from_id: Mapped[str] = mapped_column(String(64), index=True)
    to_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    created_by: Mapped[str | None] = mapped_column(String(64))


class ContentBlock(Base, PK, Stamps, VisMixin):
    __tablename__ = "content_blocks"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    block_type: Mapped[str] = mapped_column(String(30), default="text")
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_by_gm: Mapped[bool] = mapped_column(Boolean, default=False)
    edited_by: Mapped[str | None] = mapped_column(String(64))
    links: Mapped[list] = mapped_column(JSONB, default=list)  # id сущностей, о которых запись


class Clock(Base, PK, Stamps, VisMixin):
    __tablename__ = "clocks"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(60), default="", index=True)  # тип, задаёт стол
    color: Mapped[str] = mapped_column(String(20), default="amber")
    segments: Mapped[int] = mapped_column(Integer, default=6)
    filled: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    owner_type: Mapped[str | None] = mapped_column(String(30))
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # кому отдана правка: '*' — любой игрок, '' — только ГМ, иначе id участника
    owner_member_id: Mapped[str] = mapped_column(String(64), default="*")


class Message(Base, PK, Stamps, VisMixin):
    __tablename__ = "messages"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    sender_display: Mapped[str] = mapped_column(String(200), default="UNKNOWN")
    sender_entity_id: Mapped[str | None] = mapped_column(String(64))
    # привязка обычно закулисная; флаг открывает карточку отправителя столу
    sender_reveal: Mapped[bool] = mapped_column(Boolean, default=False)
    msg_type: Mapped[str] = mapped_column(String(40), default="crew")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|delivered|archived
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[str] = mapped_column(String(80), default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # игровой день письма (как Campaign.world_day)
    world_day: Mapped[int | None] = mapped_column(Integer, nullable=True)


class News(Base, PK, Stamps, VisMixin):
    """Новость сектора: депеша журналиста, которую ГМ выпустил в эфир."""

    __tablename__ = "news"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    headline: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    byline: Mapped[str] = mapped_column(String(120), default="")
    journalist: Mapped[str] = mapped_column(String(60), default="")
    # суть новости сводкой; ГМ может спрятать её от стола — тогда игроки разбираются по тексту
    lead: Mapped[str] = mapped_column(Text, default="")
    lead_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    # отклики жителей сети: [{handle, who, text}]
    comments: Mapped[list] = mapped_column(JSONB, default=list)
    # игровой день выхода (как Campaign.world_day); пусто — новость старше игрового времени
    world_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # о ком и о чём новость: записи кампании и счётчики
    entity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    clock_ids: Mapped[list] = mapped_column(JSONB, default=list)


class NewsJob(Base, PK, Stamps):
    """Заказ депеш журналисту: пишется в фоне, черновики ждут ГМа здесь же,
    пока он не выпустит их в эфир или не уберёт."""

    __tablename__ = "news_jobs"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ready|failed
    journalist: Mapped[str] = mapped_column(String(60), default="")
    gm_text: Mapped[str] = mapped_column(Text, default="")
    entity_ids: Mapped[list] = mapped_column(JSONB, default=list)
    clock_ids: Mapped[list] = mapped_column(JSONB, default=list)
    lenses: Mapped[list] = mapped_column(JSONB, default=list)
    # [{lens, angle, headline, text, manual, aired, news_id, dropped}]
    drafts: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str] = mapped_column(Text, default="")


class MessageState(Base, PK):
    __tablename__ = "message_states"
    __table_args__ = (UniqueConstraint("message_id", "member_id"),)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(64), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class MapNode(Base, PK, Stamps, VisMixin):
    __tablename__ = "map_nodes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20), default="sector")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    # order, x, y, node_kind и color не читаются; в живой базе NOT NULL без DEFAULT
    order: Mapped[int] = mapped_column(Integer, default=0)
    x: Mapped[float] = mapped_column(Float, default=0.5)
    y: Mapped[float] = mapped_column(Float, default=0.5)
    node_kind: Mapped[str] = mapped_column(String(20), default="system")
    color: Mapped[str] = mapped_column(String(20), default="")


class MapMarker(Base, PK, Stamps, VisMixin):
    __tablename__ = "map_markers"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    map_id: Mapped[str] = mapped_column(ForeignKey("map_nodes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    x: Mapped[float] = mapped_column(Float, default=0.5)
    y: Mapped[float] = mapped_column(Float, default=0.5)
    marker_type: Mapped[str] = mapped_column(String(30), default="location")
    icon: Mapped[str] = mapped_column(String(20), default="dot")
    label: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    # orbit, status и layer не читаются; в живой базе NOT NULL без DEFAULT
    orbit: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="rumored")
    layer: Mapped[str] = mapped_column(String(30), default="crew")
    linked_type: Mapped[str | None] = mapped_column(String(30))
    linked_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str | None] = mapped_column(String(64))


class MapStroke(Base, PK, Stamps, VisMixin):
    """Freehand marker stroke: normalised points, so the background can change."""

    __tablename__ = "map_strokes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    map_id: Mapped[str] = mapped_column(ForeignKey("map_nodes.id"), index=True)
    points: Mapped[list] = mapped_column(JSONB, default=list)
    color: Mapped[str] = mapped_column(String(20), default="amber")
    width: Mapped[int] = mapped_column(Integer, default=3)
    # не читается; в живой базе NOT NULL без DEFAULT
    layer: Mapped[str] = mapped_column(String(20), default="crew")
    created_by: Mapped[str | None] = mapped_column(String(64))


class Note(Base, PK, Stamps, VisMixin):
    """Threaded note attached to a marker or any entity (Miro-style comment card)."""

    __tablename__ = "notes"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(30), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    author_member_id: Mapped[str | None] = mapped_column(String(64))


class Board(Base, PK, Stamps):
    """Доска квеста: холст ГМа, куда стягиваются карточки, вырезки записей и
    свободные заметки, связанные нитями. Кухня ГМа — столу не отдаётся вовсе, поэтому
    ни у доски, ни у её карточек нет видимости."""

    __tablename__ = "boards"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))


class BoardCard(Base, PK, Stamps):
    """Карточка на доске: entity — миниатюра записи с ключевыми заметками, text —
    свободный стикер, image — улика-кадр, clock — живой счётчик кампании,
    sketch — поле, на котором ГМ рисует от руки, name — статист (npc-эпизодник): имя
    и описание, в базу кампании не идёт. Координаты в единицах холста
    (не в долях: холст бесконечный, фона под ним нет)."""

    __tablename__ = "board_cards"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id"), index=True)
    # человекочитаемый ключ в пределах доски: по нему карточку зовут в снимке и в
    # пакетной правке, вместо uuid («gregor-varg», «ulika-manifest»)
    key: Mapped[str] = mapped_column(String(64), default="", index=True)
    kind: Mapped[str] = mapped_column(String(20), default="text")
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # счётчик живёт своей жизнью в кампании: на доске лежит только ссылка на него
    clock_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # записки, привязанные к карточке на доске: [{id, text, tag}]. В саму запись
    # кампании они уходят одним блоком, сгруппированные по тегу
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    # id того блока: правка ложится в него, а не плодит новые записи
    block_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    color: Mapped[str] = mapped_column(String(20), default="amber")
    # кегль текстового поля: подпись на доске бывает и мелкой пометкой, и заголовком
    font_size: Mapped[int] = mapped_column(Integer, default=14)
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    w: Mapped[float] = mapped_column(Float, default=240.0)
    # высота задаётся вручную только у полей, где её нечем вывести из содержимого
    # (набросок); у остальных карточек высоту считает браузер по тексту
    h: Mapped[float] = mapped_column(Float, default=0.0)
    # росчерки наброска: [{color, width, pts: [x, y, ...]}] в координатах карточки
    ink: Mapped[list] = mapped_column(JSONB, default=list)
    collapsed: Mapped[bool] = mapped_column(Boolean, default=False)
    z: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64))


class BoardEdge(Base, PK, Stamps):
    """Нить между карточками: как красная верёвка на детективной доске."""

    __tablename__ = "board_edges"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    board_id: Mapped[str] = mapped_column(ForeignKey("boards.id"), index=True)
    from_card_id: Mapped[str] = mapped_column(String(64), index=True)
    to_card_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    color: Mapped[str] = mapped_column(String(20), default="rust")
    style: Mapped[str] = mapped_column(String(20), default="thread")
    created_by: Mapped[str | None] = mapped_column(String(64))


class Attachment(Base, PK, Stamps, VisMixin):
    __tablename__ = "attachments"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    target_type: Mapped[str | None] = mapped_column(String(30), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    caption: Mapped[str] = mapped_column(String(300), default="")
    uploaded_by: Mapped[str | None] = mapped_column(String(64))
    # рамка превью в пикселях оригинала, "x,y,w,h"; пусто — превью со всего кадра.
    # Файл при кадрировании не режем: миниатюры берут рамку, полный размер — оригинал
    crop_box: Mapped[str] = mapped_column(String(60), default="")


class ImageGenJob(Base, PK, Stamps):
    """Заявка на генерацию портрета: ГМ ставит промпт, локальный воркер поллит,
    приносит 4 кандидата, ГМ выбирает — остальные удаляются. Живёт до выбора/отмены,
    поэтому её можно свернуть (закрыть окно) и вернуться позже — статус переживает
    закрытие модалки на фронте."""

    __tablename__ = "image_gen_jobs"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    # пусто — заявка не привязана к карточке (кадр кампании, экран «Кадры кампании»)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # txt2img — рисуем с нуля; inpaint — перерисовываем область готовой картинки по
    # маске. Второй случай тянет за собой исходник, маску и другой граф в воркере
    kind: Mapped[str] = mapped_column(String(20), default="txt2img", index=True)
    # inpaint: что правим и по какой маске (маска — своё вложение, target_id = id заявки)
    source_attachment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # кусок исходника, который реально уходит в модель: "x,y,w,h" в координатах
    # подготовленной копии. Пусто — правим кадр целиком (маска почти во весь кадр)
    crop_box: Mapped[str] = mapped_column(String(60), default="")
    # когда воркер забрал заявку и какой это заход: пропавшего воркера видно только
    # по этим двум полям — иначе заявка висит в claimed вечно (см. reap_stale_jobs)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # 1.0 — переписать область начисто, ниже — подправить, сохранив исходную форму
    denoise: Mapped[float] = mapped_column(Float, default=1.0)
    prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    width: Mapped[int] = mapped_column(Integer, default=768)
    height: Mapped[int] = mapped_column(Integer, default=960)
    n_images: Mapped[int] = mapped_column(Integer, default=4)
    # сид по заявке: две сборки промпта сравнимы, только если шум под ними один
    seed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(64))
    # развилки и слоты попытки: лента мастерской показывает, из чего она собрана
    params: Mapped[dict] = mapped_column(JSONB, default=dict)


class Event(Base, PK):
    """Журнал кампании: кто, когда и что поправил. Пишется на каждую правку
    (см. history.log), поэтому переживает удаление самой записи — в отличие от
    created_at/updated_at строк. `before`/`after` держат только изменившиеся ключи."""

    __tablename__ = "events"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    actor_member_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_name: Mapped[str] = mapped_column(String(120), default="")
    by_gm: Mapped[bool] = mapped_column(Boolean, default=False)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    target_title: Mapped[str] = mapped_column(String(200), default="")
    # карточка, на которую ведёт ссылка из ленты (запись, заметка, счётчик — на своей)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detail: Mapped[str] = mapped_column(String(400), default="")
    visibility: Mapped[str] = mapped_column(String(20), default="")
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class AuditLog(Base, PK):
    __tablename__ = "audit_log"
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
