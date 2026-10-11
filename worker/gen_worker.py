"""Локальный воркер генерации картинок: поллит Procyon Archive за задачами,
рисует локальным ComfyUI (Z-Image-Turbo) столько вариантов, сколько просит
задача (портрет — 4, кадр локации — 1), шлёт кандидатов обратно.

Умеет два вида заявок: txt2img (с нуля) и inpaint (перерисовать область готовой
картинки по маске — тоже 4 варианта).

Запуск:
    PA_SERVER_URL=https://<host> PA_WORKER_TOKEN=<токен> python gen_worker.py
"""

from __future__ import annotations

import io
import os
import random
import threading
import time

import requests

SERVER = os.environ["PA_SERVER_URL"].rstrip("/")
TOKEN = os.environ["PA_WORKER_TOKEN"]
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
POLL_SECONDS = 4
HEARTBEAT_SECONDS = 10
CANDIDATES = 4
# отдача пачки кандидатов вверх по домашнему каналу: минуты, а не секунды
UPLOAD_TIMEOUT = 600
UPLOAD_TRIES = 3
# второй проход: перерисовать кусок целиком, чтобы свести предмет с кадром по
# манере и свету. Выше 0.4 начинает менять сам предмет, ниже 0.25 не сводит
HARMONIZE_DENOISE = 0.35

# Z-Image: DiT, энкодер и VAE лежат порознь. Значения сняты на стенде
ZIMAGE_UNET = "z_image_turbo_int8_convrot.safetensors"
ZIMAGE_CLIP = "qwen_3_4b_fp8_mixed.safetensors"
ZIMAGE_VAE = "z_image_ae.safetensors"
ZIMAGE_STEPS = 8
ZIMAGE_SHIFT = 3.0
# лёгкая композиционная подсказка на не-первый кандидат — нулевой индекс остаётся
# «чистым» базовым промптом без добавок
COMPOSITION_HINTS = [
    "", "alternate pose and framing, ", "different camera angle, ",
    "varied composition and lighting, ",
]

# что показывать в плашке воркера: имя весов, которыми он рисует на самом деле
SHOWN_MODEL = f"{ZIMAGE_UNET} ({ZIMAGE_STEPS} шагов, cfg 1.0)"
SHOWN_INPAINT = f"{ZIMAGE_UNET} + differential diffusion"

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# что рисуем прямо сейчас — читает heartbeat-тред, пишет основной цикл
CURRENT = {"job_id": None, "progress": None}


def heartbeat_loop() -> None:
    """Отдельный тред: основной цикл на время рендера уходит в ComfyUI на минуты
    и пинговать не может, а плашка в интерфейсе должна гореть именно тогда."""
    while True:
        try:
            requests.get(f"{COMFY}/system_stats", timeout=2).raise_for_status()
            comfy = "up"
        except Exception:  # noqa: BLE001
            comfy = "down"
        try:
            requests.post(
                f"{SERVER}/api/worker/heartbeat", headers=HEADERS, timeout=5,
                json={"comfy": comfy, "checkpoint": SHOWN_MODEL,
                      "inpaint_checkpoint": SHOWN_INPAINT,
                      "job_id": CURRENT["job_id"], "progress": CURRENT["progress"]},
            )
        except Exception:  # noqa: BLE001 — сервер недоступен, плашка сама погаснет
            pass
        time.sleep(HEARTBEAT_SECONDS)


SAVE = "out"  # ключ узла SaveImage — по нему забираем результат из history


def zimage_base(prompt: str) -> dict:
    """Загрузчики, кодирование промпта и сдвиг расписания — общие для обоих графов.

    Негатива нет физически: при cfg 1.0 формула guidance вырождается в cond, и
    безусловная ветвь не считается, поэтому её вход зануляется.
    """
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": ZIMAGE_UNET, "weight_dtype": "default"}},
        "10": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": ZIMAGE_CLIP, "type": "lumina2"}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": ZIMAGE_VAE}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["10", 0]}},
        "3": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["2", 0]}},
        "ms": {"class_type": "ModelSamplingAuraFlow",
               "inputs": {"model": ["1", 0], "shift": ZIMAGE_SHIFT}},
    }


def workflow(prompt: str, width: int, height: int, seed: int) -> dict:
    """Кадр с нуля: 8 шагов, cfg 1.0, res_multistep по simple."""
    g = zimage_base(prompt)
    g.update({
        "4": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": ZIMAGE_STEPS, "cfg": 1.0,
            "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1.0,
            "model": ["ms", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0],
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["11", 0]}},
        SAVE: {"class_type": "SaveImage",
               "inputs": {"filename_prefix": "job", "images": ["6", 0]}},
    })
    return g


def inpaint_workflow(prompt: str, source: str, mask: str, seed: int, denoise: float) -> dict:
    """Перерисовать область: исходник и маска уже лежат во входной папке ComfyUI.

    Отдельной inpaint-модели нет, поэтому область держит DifferentialDiffusion:
    серое значение маски решает, на каком шаге пиксель перестанет быть
    зафиксированным, и жёсткого стыка не возникает. Маска приходит с сервера уже
    размытой по кромке — градиент, на котором это держится, есть.

    На выходе ImageCompositeMasked с исходником: VAE прогоняет весь кадр, и
    незакрашенное иначе поедет по цвету. Затем проход-гармонизация: первый проход
    рисует предмет, не видя красок вокруг, второй перерисовывает его на слабом
    denoise уже глядя на окружение, и снова composite по маске.
    """
    g = zimage_base(prompt)
    g.update({
        "src": {"class_type": "LoadImage", "inputs": {"image": source}},
        "msk": {"class_type": "LoadImageMask", "inputs": {"image": mask, "channel": "red"}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["src", 0], "vae": ["11", 0]}},
        "lat": {"class_type": "SetLatentNoiseMask",
                "inputs": {"samples": ["enc", 0], "mask": ["msk", 0]}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": ZIMAGE_STEPS, "cfg": 1.0,
            "sampler_name": "res_multistep", "scheduler": "simple",
            "denoise": round(denoise, 3), "model": ["dd", 0],
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["lat", 0],
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["11", 0]}},
        "mix": {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["src", 0], "source": ["6", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["msk", 0]}},
        "enc2": {"class_type": "VAEEncode", "inputs": {"pixels": ["mix", 0], "vae": ["11", 0]}},
        "ks2": {"class_type": "KSampler", "inputs": {
            "seed": seed + 1, "steps": ZIMAGE_STEPS, "cfg": 1.0,
            "sampler_name": "res_multistep", "scheduler": "simple",
            "denoise": HARMONIZE_DENOISE, "model": ["dd", 0],
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["enc2", 0],
        }},
        "dec2": {"class_type": "VAEDecode", "inputs": {"samples": ["ks2", 0], "vae": ["11", 0]}},
        "mix2": {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["src", 0], "source": ["dec2", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["msk", 0]}},
        SAVE: {"class_type": "SaveImage",
               "inputs": {"filename_prefix": "inpaint", "images": ["mix2", 0]}},
        "dd": {"class_type": "DifferentialDiffusion", "inputs": {"model": ["ms", 0]}},
    })
    return g


def comfy_upload(name: str, data: bytes) -> str:
    """Положить картинку во входную папку ComfyUI — LoadImage берёт файлы только оттуда."""
    r = requests.post(
        f"{COMFY}/upload/image", timeout=60,
        files={"image": (name, io.BytesIO(data), "image/png")},
        data={"overwrite": "true", "type": "input"},
    )
    r.raise_for_status()
    return r.json().get("name") or name


class JobGone(Exception):
    """Заявки больше нет на сервере (отмена или сборщик висяков) — пачку бросаем
    молча, репортить /fail некому."""


def job_state(job_id: str) -> str:
    """Жива ли заявка: ГМ мог отменить её посреди пачки."""
    try:
        r = requests.get(f"{SERVER}/api/worker/image-jobs/{job_id}/state",
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get("status") or "gone"
    except Exception:  # noqa: BLE001 — сеть моргнула: считаем живой и рисуем дальше
        return "claimed"


def send_candidates(job_id: str, files: list) -> None:
    """Отдать кандидатов серверу, пережив медленный или моргнувший канал.

    Четыре PNG в полный кадр — это десятки мегабайт вверх по домашнему аплинку:
    прежний минутный таймаут срывался ровно здесь, и вся нарисованная пачка
    пропадала уже после рендера. Файлы читаем один раз и перематываем на каждый
    заход — иначе повтор ушёл бы пустым.
    """
    last = None
    for attempt in range(UPLOAD_TRIES):
        for _, (_, buf, _) in files:
            buf.seek(0)
        try:
            r = requests.post(
                f"{SERVER}/api/worker/image-jobs/{job_id}/candidates",
                headers=HEADERS, files=files, timeout=UPLOAD_TIMEOUT,
            )
            r.raise_for_status()
            return
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else 0
            if code in (404, 409):
                # заявку отменили или сборщик висяков вернул её в очередь —
                # повторять бессмысленно, пачка уходит в корзину
                raise JobGone(f"server says {code} on upload") from exc
            last = exc
            print(f"[job {job_id}] upload attempt {attempt + 1} failed: {exc}")
            time.sleep(5)
        except Exception as exc:  # noqa: BLE001 — сеть, а не заявка: пробуем ещё
            last = exc
            print(f"[job {job_id}] upload attempt {attempt + 1} failed: {exc}")
            time.sleep(5)
    raise RuntimeError(f"не удалось отдать кандидатов: {last}")


def fetch_blob(job_id: str, what: str) -> bytes:
    """Исходник и маску отдаёт сервер: они привязаны к заявке, а не к кампании."""
    r = requests.get(
        f"{SERVER}/api/worker/image-jobs/{job_id}/{what}", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.content


def run_graph(graph: dict) -> bytes:
    r = requests.post(f"{COMFY}/prompt", json={"prompt": graph}, timeout=30)
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]

    # до 15 минут: очередь ComfyUI своя, и время в ней тоже идёт. Сервер считает
    # заявку потерянной после 25 минут — воркер должен сдаться раньше и сказать об этом
    for _ in range(900):
        h = requests.get(f"{COMFY}/history/{prompt_id}", timeout=15).json()
        entry = h.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"comfyui error: {status}")
            outputs = entry.get("outputs", {})
            img_info = next(iter(outputs.get(SAVE, {}).get("images", [])), None)
            if img_info:
                resp = requests.get(f"{COMFY}/view", params={
                    "filename": img_info["filename"],
                    "subfolder": img_info.get("subfolder", ""),
                    "type": img_info.get("type", "output"),
                }, timeout=30)
                resp.raise_for_status()
                return resp.content
        time.sleep(1)
    raise TimeoutError("comfyui generation timed out")


def handle_job(job: dict) -> None:
    job_id = job["id"]
    # негатив задачи не читается: при cfg 1.0 он не участвует в выводе
    prompt = job["prompt"]
    width = job["width"]
    height = job["height"]
    inpaint = job.get("kind") == "inpaint"
    denoise = float(job.get("denoise") or 1.0)
    count = max(1, min(CANDIDATES, int(job.get("n_images") or CANDIDATES)))
    what = f"inpaint d={denoise:g}" if inpaint else "generating"
    print(f"[job {job_id}] {what} {count}x {width}x{height}: {prompt!r}")
    files = []
    CURRENT.update(job_id=job_id, progress=f"0/{count}")
    try:
        source = mask = ""
        if inpaint:
            source = comfy_upload(f"pa_{job_id}_src.png", fetch_blob(job_id, "source"))
            mask = comfy_upload(f"pa_{job_id}_mask.png", fetch_blob(job_id, "mask"))
        render_error = None
        for i in range(count):
            if i and job_state(job_id) != "claimed":
                raise JobGone("canceled on server mid-batch")
            CURRENT["progress"] = f"{i + 1}/{count}"
            # сид заявки: на нём держится сравнение сборок; ноль — случайный
            fixed = int(job.get("seed") or 0)
            seed = fixed + i if fixed else random.randint(0, 2**31 - 1)
            if inpaint:
                # кадр и композиция заданы исходником: разнообразие даёт только seed,
                # подсказки вроде «другой ракурс» здесь были бы прямым вредом
                graph = inpaint_workflow(prompt, source, mask, seed, denoise)
            elif job.get("prompts"):
                # варианты хаба — разные абзацы той же сцены: Turbo от сида почти
                # не меняет кадр, разных кандидатов даёт только текст
                variants = job["prompts"]
                graph = workflow(variants[i % len(variants)], width, height, seed)
            else:
                hint = COMPOSITION_HINTS[i % len(COMPOSITION_HINTS)]
                graph = workflow(f"{hint}{prompt}", width, height, seed)
            try:
                data = run_graph(graph)
            except Exception as exc:  # noqa: BLE001 — уже нарисованное дороже падения:
                # пачка уходит неполной, а не в корзину
                render_error = exc
                print(f"[job {job_id}] candidate {i + 1}/{count} failed: {exc}")
                break
            files.append(("files", (f"candidate_{i}.png", io.BytesIO(data), "image/png")))
        if not files:
            raise render_error or RuntimeError("не нарисован ни один кандидат")
        send_candidates(job_id, files)
        tail = f" (без {count - len(files)} из-за: {render_error})" if render_error else ""
        print(f"[job {job_id}] {len(files)} candidates uploaded{tail}")
    except JobGone as gone:
        print(f"[job {job_id}] dropped: {gone}")
    except Exception as exc:  # noqa: BLE001 — репортим наверх и едем дальше
        print(f"[job {job_id}] FAILED: {exc}")
        try:
            requests.post(
                f"{SERVER}/api/worker/image-jobs/{job_id}/fail",
                headers=HEADERS, data={"error": str(exc)[:2000]}, timeout=30,
            )
        except Exception as tell:  # noqa: BLE001 — сервер недоступен: заявку
            # подберёт серверный сборщик висяков, воркер не должен на этом падать
            print(f"[job {job_id}] fail report lost: {tell}")
    finally:
        CURRENT.update(job_id=None, progress=None)


def main() -> None:
    print(f"worker up: server={SERVER} comfy={COMFY} "
          f"dit={ZIMAGE_UNET} steps={ZIMAGE_STEPS} cfg=1.0")
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    while True:
        try:
            # caps — чтобы сервер не отдал заявку на правку воркеру старой версии:
            # тот нарисовал бы по её промпту обычную картинку и подменил кадр
            r = requests.get(f"{SERVER}/api/worker/image-jobs/next",
                             params={"caps": "inpaint"}, headers=HEADERS, timeout=15)
            r.raise_for_status()
            job = r.json().get("job")
            if job:
                handle_job(job)
                continue
        except Exception as exc:  # noqa: BLE001
            print(f"poll error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
