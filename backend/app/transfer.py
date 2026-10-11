"""Выгрузка и загрузка кампании целиком — в фоне, с ходом работы для Admin space.

Архив (формат procyon-archive/2): ``campaign.json`` — строки кампании по таблицам и язык
экземпляра, ``files/<имя>`` — файлы вложений как лежат на диске. Выгрузка без файлов —
один ``campaign.json``.

Загрузка заводит новую кампанию: все id переписываются на свежие (архив можно залить
дважды и на тот же сервер), участники остаются только те, чьи учётки есть на этом
сервере, загрузивший становится ГМом. Канон книги переводится на язык экземпляра.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone

from sqlalchemy import DateTime, insert

from .config import settings
from .db import SessionLocal
from .i18n import instance_lang
from .models import (
    Attachment,
    Board,
    BoardCard,
    BoardEdge,
    Campaign,
    CampaignMember,
    Clock,
    ContentBlock,
    Entity,
    EntityLink,
    Event,
    ImageGenJob,
    MapMarker,
    MapNode,
    MapStroke,
    Message,
    News,
    NewsJob,
    Note,
    User,
)
from .visibility import ANY_PLAYER

log = logging.getLogger("transfer")

FORMAT = "procyon-archive/2"
TABLES = [
    ("campaign_members", CampaignMember),
    ("entities", Entity),
    ("entity_links", EntityLink),
    ("content_blocks", ContentBlock),
    ("clocks", Clock),
    ("messages", Message),
    ("news", News),
    ("map_nodes", MapNode),
    ("map_markers", MapMarker),
    ("map_strokes", MapStroke),
    ("notes", Note),
    ("boards", Board),
    ("board_cards", BoardCard),
    ("board_edges", BoardEdge),
    ("attachments", Attachment),
    ("events", Event),
    # попытки мастерской и заказы депеш: лента попыток и черновики живут на них
    ("image_gen_jobs", ImageGenJob),
    ("news_jobs", NewsJob),
]
# заявка в работе на новом месте не продолжится — заливаем её неудавшейся
FINAL = {"image_gen_jobs": ("ready", "done", "failed"), "news_jobs": ("ready", "failed")}
# ключи хаба в выгрузку не кладём: файл резервной копии уходит из рук. Адрес и модели —
# тоже: это настройка сервера, на новом месте они стали бы запасными для всех кампаний
HUB_COLUMNS = ("img_api_key", "news_api_key", "img_base_url", "news_base_url", "img_model", "news_model")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
WORK_DIR = os.path.join(settings.upload_dir, "_transfers")
KEEP_SECONDS = 6 * 3600
CHUNK = 1 << 20

# задачи живут в памяти процесса: после перезапуска сервера незаконченная пропадает
JOBS: dict[str, dict] = {}
_lock = threading.Lock()


def _job(kind: str, **kw) -> dict:
    _sweep()
    job = {"id": uuid.uuid4().hex, "kind": kind, "status": "running", "stage": "start",
           "done": 0, "total": 0, "error": "", "file": "", "download": "", "campaign_id": "",
           "name": "", "started": time.time(), **kw}
    with _lock:
        JOBS[job["id"]] = job
    return job


def _set(job: dict, **kw) -> None:
    with _lock:
        job.update(kw)


def job_out(job: dict) -> dict:
    return {k: job[k] for k in ("id", "kind", "status", "stage", "done", "total", "error",
                                "download", "campaign_id", "name")}


def _sweep() -> None:
    """Готовые архивы и брошенные загрузки живут несколько часов."""
    now = time.time()
    with _lock:
        for jid, job in list(JOBS.items()):
            if job["status"] != "running" and now - job["started"] > KEEP_SECONDS:
                JOBS.pop(jid)
    if not os.path.isdir(WORK_DIR):
        return
    for name in os.listdir(WORK_DIR):
        path = os.path.join(WORK_DIR, name)
        try:
            if now - os.path.getmtime(path) > KEEP_SECONDS:
                os.remove(path)
        except OSError:
            pass


# --- выгрузка -----------------------------------------------------------------


def _row(obj) -> dict:
    out = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        out[col.name] = val.isoformat() if isinstance(val, datetime) else val
    return out


def dump(db, campaign_id: str, progress=None) -> dict:
    camp = db.get(Campaign, campaign_id)
    payload: dict = {
        "format": FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "lang": instance_lang(),
        "campaign": {k: v for k, v in _row(camp).items() if k not in HUB_COLUMNS},
    }
    for i, (name, model) in enumerate(TABLES):
        rows = db.query(model).filter(model.campaign_id == campaign_id).all()
        payload[name] = [_row(r) for r in rows]
        if progress:
            progress(i + 1, len(TABLES))
    return payload


def _flat_name(url) -> str:
    """Имя файла вложения без каталогов; пусто — имени нет."""
    name = os.path.basename(str(url or ""))
    return "" if name in (".", "..") else name


def _slugify(name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:40]
    return base or "campaign"


def start_export(campaign_id: str, with_files: bool) -> dict:
    job = _job("export", campaign_id=campaign_id)
    threading.Thread(target=_export, args=(job, with_files), daemon=True).start()
    return job


def _export(job: dict, with_files: bool) -> None:
    db = SessionLocal()
    try:
        camp = db.get(Campaign, job["campaign_id"])
        _set(job, name=camp.name, stage="rows")
        payload = dump(db, camp.id, lambda d, t: _set(job, done=d, total=t))
        os.makedirs(WORK_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d")
        nice = f"{_slugify(camp.name)}-{stamp}"
        data = json.dumps(payload, ensure_ascii=False, indent=1).encode()
        if not with_files:
            path = os.path.join(WORK_DIR, f"{job['id']}.json")
            with open(path, "wb") as fh:
                fh.write(data)
            _set(job, status="done", stage="done", file=path, download=f"{nice}.json")
            return
        folder = os.path.join(settings.upload_dir, camp.id)
        # только файлы живых вложений: от удалённых на диске остаются сироты
        names = sorted({a.url for a in db.query(Attachment.url).filter_by(campaign_id=camp.id)
                        if a.url and _flat_name(a.url) == a.url})
        sizes = {n: os.path.getsize(os.path.join(folder, n)) for n in names
                 if os.path.isfile(os.path.join(folder, n))}
        _set(job, stage="files", done=0, total=sum(sizes.values()))
        path = os.path.join(WORK_DIR, f"{job['id']}.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            z.writestr(zipfile.ZipInfo("campaign.json"), data, compress_type=zipfile.ZIP_DEFLATED)
            done = 0
            for n, size in sizes.items():
                # картинки и так сжаты: кладём как есть, без второго прохода компрессии
                z.write(os.path.join(folder, n), f"files/{n}")
                done += size
                _set(job, done=done)
        _set(job, status="done", stage="done", file=path, download=f"{nice}.zip")
    except Exception as exc:  # noqa: BLE001 — ошибку показываем в Admin space
        log.exception("export %s", job["campaign_id"])
        _set(job, status="failed", error=str(exc)[:500])
    finally:
        db.close()


# --- загрузка -----------------------------------------------------------------


def upload_path(job: dict) -> str:
    os.makedirs(WORK_DIR, exist_ok=True)
    return os.path.join(WORK_DIR, f"{job['id']}.upload")


def new_import(filename: str, user_id: str) -> dict:
    return _job("import", name=filename, user_id=user_id, stage="upload")


def start_import(job: dict) -> None:
    threading.Thread(target=_import, args=(job,), daemon=True).start()


def _read(path: str) -> tuple[dict, zipfile.ZipFile | None]:
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        return json.loads(z.read("campaign.json")), z
    with open(path, encoding="utf-8") as fh:
        return json.load(fh), None


def _typed(model, row: dict) -> dict:
    cols = {c.name: c for c in model.__table__.columns}
    out = {}
    for key, val in row.items():
        col = cols.get(key)
        if col is None:
            continue
        if isinstance(col.type, DateTime) and isinstance(val, str):
            val = datetime.fromisoformat(val)
        out[key] = val
    return out


def _import(job: dict) -> None:
    path = upload_path(job)
    db = SessionLocal()
    folder = ""
    try:
        _set(job, stage="read", done=0, total=0)
        payload, z = _read(path)
        if not str(payload.get("format", "")).startswith("procyon-archive/") or "campaign" not in payload:
            raise ValueError("not a Procyon Archive campaign export")

        # все id кампании — свежие; текстом, чтобы переписались и ссылки внутри JSON и путей
        ids = {payload["campaign"]["id"]}
        for name, _model in TABLES:
            ids |= {r["id"] for r in payload.get(name, []) if r.get("id")}
        remap = {old: str(uuid.uuid4()) for old in ids}
        text = UUID_RE.sub(lambda m: remap.get(m.group(0), m.group(0)), json.dumps(payload))
        payload = json.loads(text)
        src = payload["campaign"]
        cid = src["id"]

        importer = db.get(User, job["user_id"])
        users = {u for (u,) in db.query(User.id).all()}
        members = [m for m in payload.get("campaign_members", []) if m.get("user_id") in users]
        kept = {m["id"] for m in members}
        if not any(m["user_id"] == importer.id for m in members):
            members.append({"id": str(uuid.uuid4()), "campaign_id": cid, "user_id": importer.id,
                            "role": "gm", "display_name": importer.display_name})
        for m in members:
            if m["user_id"] == importer.id:
                m["role"] = "gm"
        payload["campaign_members"] = members
        for e in payload.get("entities", []):
            if e.get("owner_member_id") and e["owner_member_id"] not in kept | {ANY_PLAYER}:
                e["owner_member_id"] = None
        # файл вложения — только имя в папке кампании: путь из чужого архива не доверяем
        for a in payload.get("attachments", []):
            a["url"] = _flat_name(a.get("url"))
        payload["attachments"] = [a for a in payload.get("attachments", []) if a["url"]]
        for name, final in FINAL.items():
            for job_row in payload.get(name, []):
                if job_row.get("status") not in final:
                    job_row["status"] = "failed"

        camp = _typed(Campaign, src)
        camp.update(owner_id=importer.id, created_at=datetime.now(timezone.utc), **{col: "" for col in HUB_COLUMNS})
        total = sum(len(payload.get(name, [])) for name, _m in TABLES)
        _set(job, stage="rows", done=0, total=total, name=src.get("name", ""))
        db.execute(insert(Campaign.__table__), [camp])
        done = 0
        for name, model in TABLES:
            rows = [_typed(model, r) for r in payload.get(name, [])]
            # пачкой вставляются строки с одинаковым набором колонок: дописанный ГМ — короче
            for keys in dict.fromkeys(tuple(sorted(r)) for r in rows):
                same = [r for r in rows if tuple(sorted(r)) == keys]
                for i in range(0, len(same), 500):
                    part = same[i:i + 500]
                    db.execute(insert(model.__table__), part)
                    done += len(part)
                    _set(job, done=done)

        if z is not None:
            files = [i for i in z.infolist() if i.filename.startswith("files/") and not i.is_dir()]
            _set(job, stage="files", done=0, total=sum(i.file_size for i in files))
            folder = os.path.join(settings.upload_dir, cid)
            os.makedirs(folder, exist_ok=True)
            done = 0
            for info in files:
                target = os.path.join(folder, os.path.basename(info.filename))
                with z.open(info) as src_fh, open(target, "wb") as dst:
                    while chunk := src_fh.read(CHUNK):
                        dst.write(chunk)
                        done += len(chunk)
                        _set(job, done=done)
            z.close()

        db.commit()
        _set(job, status="done", stage="done", campaign_id=cid)
    except Exception as exc:  # noqa: BLE001 — ошибку показываем в Admin space
        log.exception("import %s", job.get("name"))
        db.rollback()
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        _set(job, status="failed", error=str(exc)[:500])
    finally:
        db.close()
        try:
            os.remove(path)
        except OSError:
            pass


def get(job_id: str) -> dict | None:
    with _lock:
        return JOBS.get(job_id)
