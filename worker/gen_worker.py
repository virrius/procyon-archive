"""Procyon Archive image worker: takes jobs from the server, draws in a local ComfyUI
(Z-Image-Turbo), uploads candidates. Jobs are txt2img and inpaint. How to run: README.md."""

from __future__ import annotations

import argparse
import io
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def load_env() -> None:
    """KEY=VALUE from a .env next to the worker or one level up; the environment takes precedence."""
    for f in (HERE / ".env", HERE.parent / ".env"):
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.partition("=")
                key = key.strip()
                if sep and key and not key.startswith("#") and value.strip():
                    os.environ.setdefault(key, value.strip())


load_env()
SERVER = os.environ.get("PA_SERVER_URL", "").rstrip("/")
TOKEN = os.environ.get("PA_WORKER_TOKEN", "")
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

POLL_SECONDS = 4
HEARTBEAT_SECONDS = 10
CANDIDATES = 4
# a batch of PNGs over a home uplink takes minutes
UPLOAD_TIMEOUT = 600
UPLOAD_TRIES = 3
# the second inpaint pass blends the object into the frame; above 0.4 it changes the object itself
HARMONIZE_DENOISE = 0.35

ZIMAGE_UNET = "z_image_turbo_int8_convrot.safetensors"
ZIMAGE_CLIP = "qwen_3_4b_fp8_mixed.safetensors"
ZIMAGE_VAE = "ae.safetensors"
ZIMAGE_STEPS = 8
ZIMAGE_SHIFT = 3.0

SHOWN_MODEL = f"{ZIMAGE_UNET} ({ZIMAGE_STEPS} steps, cfg 1.0)"
SHOWN_INPAINT = f"{ZIMAGE_UNET} + differential diffusion"

# what is being drawn now: written by the main loop, read by heartbeat
CURRENT = {"job_id": None, "progress": None}
SAVE = "out"  # SaveImage node, used to find the result in history


def heartbeat_loop() -> None:
    """Separate thread: while the main loop waits for ComfyUI, the status badge in the UI must stay lit."""
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
        except Exception:  # noqa: BLE001, S110 — server unreachable, the badge will go out on its own
            pass
        time.sleep(HEARTBEAT_SECONDS)


def zimage_base(prompt: str) -> dict:
    """Loaders, prompt and schedule shift. At cfg 1.0 the negative is not computed — it is empty."""
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


def sampler(seed: int, denoise: float, model: list, latent: list) -> dict:
    return {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": ZIMAGE_STEPS, "cfg": 1.0,
        "sampler_name": "res_multistep", "scheduler": "simple", "denoise": denoise,
        "model": model, "positive": ["2", 0], "negative": ["3", 0], "latent_image": latent,
    }}


def workflow(prompt: str, width: int, height: int, seed: int) -> dict:
    g = zimage_base(prompt)
    g.update({
        "4": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": sampler(seed, 1.0, ["ms", 0], ["4", 0]),
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["11", 0]}},
        SAVE: {"class_type": "SaveImage", "inputs": {"filename_prefix": "job", "images": ["6", 0]}},
    })
    return g


def inpaint_workflow(prompt: str, source: str, mask: str, seed: int, denoise: float) -> dict:
    """Redraw an area. The seam is held by DifferentialDiffusion over the blurred mask from the server;
    composite with the source so the VAE does not shift color outside the mask; a second pass at low
    denoise blends the object with its surroundings."""
    g = zimage_base(prompt)
    g.update({
        "dd": {"class_type": "DifferentialDiffusion", "inputs": {"model": ["ms", 0]}},
        "src": {"class_type": "LoadImage", "inputs": {"image": source}},
        "msk": {"class_type": "LoadImageMask", "inputs": {"image": mask, "channel": "red"}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["src", 0], "vae": ["11", 0]}},
        "lat": {"class_type": "SetLatentNoiseMask",
                "inputs": {"samples": ["enc", 0], "mask": ["msk", 0]}},
        "5": sampler(seed, round(denoise, 3), ["dd", 0], ["lat", 0]),
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["11", 0]}},
        "mix": {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["src", 0], "source": ["6", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["msk", 0]}},
        "enc2": {"class_type": "VAEEncode", "inputs": {"pixels": ["mix", 0], "vae": ["11", 0]}},
        "ks2": sampler(seed + 1, HARMONIZE_DENOISE, ["dd", 0], ["enc2", 0]),
        "dec2": {"class_type": "VAEDecode", "inputs": {"samples": ["ks2", 0], "vae": ["11", 0]}},
        "mix2": {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["src", 0], "source": ["dec2", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["msk", 0]}},
        SAVE: {"class_type": "SaveImage", "inputs": {"filename_prefix": "inpaint", "images": ["mix2", 0]}},
    })
    return g


def comfy_upload(name: str, data: bytes) -> str:
    """Into the ComfyUI input folder. The name is fixed — overwrite instead of a new file per job."""
    r = requests.post(
        f"{COMFY}/upload/image", timeout=60,
        files={"image": (name, io.BytesIO(data), "image/png")},
        data={"overwrite": "true", "type": "input"},
    )
    r.raise_for_status()
    return r.json().get("name") or name


class JobGone(Exception):
    """The job was cancelled or returned to the queue — drop the batch, do not send /fail."""


def job_state(job_id: str) -> str:
    try:
        r = requests.get(f"{SERVER}/api/worker/image-jobs/{job_id}/state",
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get("status") or "gone"
    except Exception:  # noqa: BLE001 — network blip: assume it is alive
        return "claimed"


def send_candidates(job_id: str, files: list) -> None:
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
                raise JobGone(f"server says {code} on upload") from exc
            last = exc
        except Exception as exc:  # noqa: BLE001 — a network issue, not the job: try again
            last = exc
        print(f"[job {job_id}] upload attempt {attempt + 1} failed: {last}")
        time.sleep(5)
    raise RuntimeError(f"upload failed: {last}")


def fetch_blob(job_id: str, what: str) -> bytes:
    r = requests.get(
        f"{SERVER}/api/worker/image-jobs/{job_id}/{what}", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.content


def run_graph(graph: dict) -> bytes:
    r = requests.post(f"{COMFY}/prompt", json={"prompt": graph}, timeout=30)
    r.raise_for_status()
    prompt_id = r.json()["prompt_id"]
    # up to 15 minutes per candidate, counting the ComfyUI queue
    for _ in range(900):
        entry = requests.get(f"{COMFY}/history/{prompt_id}", timeout=15).json().get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"comfyui error: {status}")
            img = next(iter(entry.get("outputs", {}).get(SAVE, {}).get("images", [])), None)
            if img:
                resp = requests.get(f"{COMFY}/view", params={
                    "filename": img["filename"], "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                }, timeout=30)
                resp.raise_for_status()
                return resp.content
        time.sleep(1)
    raise TimeoutError("comfyui generation timed out")


def handle_job(job: dict) -> None:
    job_id = job["id"]
    prompt = job["prompt"]
    # the line for each candidate is assembled on the server
    variants = job.get("prompts") or [prompt]
    width, height = job["width"], job["height"]
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
            source = comfy_upload("pa_source.png", fetch_blob(job_id, "source"))
            mask = comfy_upload("pa_mask.png", fetch_blob(job_id, "mask"))
        render_error = None
        fixed = int(job.get("seed") or 0)  # 0 — random
        for i in range(count):
            if i and job_state(job_id) != "claimed":
                raise JobGone("canceled on server mid-batch")
            CURRENT["progress"] = f"{i + 1}/{count}"
            seed = fixed + i if fixed else random.randint(0, 2**31 - 1)
            graph = (inpaint_workflow(prompt, source, mask, seed, denoise) if inpaint
                     else workflow(variants[i % len(variants)], width, height, seed))
            try:
                data = run_graph(graph)
            except Exception as exc:  # noqa: BLE001 — upload what was drawn as an incomplete batch
                render_error = exc
                print(f"[job {job_id}] candidate {i + 1}/{count} failed: {exc}")
                break
            files.append(("files", (f"candidate_{i}.png", io.BytesIO(data), "image/png")))
        if not files:
            raise render_error or RuntimeError("no candidates drawn")
        send_candidates(job_id, files)
        tail = f" ({count - len(files)} missing: {render_error})" if render_error else ""
        print(f"[job {job_id}] {len(files)} candidates uploaded{tail}")
    except JobGone as gone:
        print(f"[job {job_id}] dropped: {gone}")
    except Exception as exc:  # noqa: BLE001 — report and move on
        print(f"[job {job_id}] FAILED: {exc}")
        try:
            requests.post(
                f"{SERVER}/api/worker/image-jobs/{job_id}/fail",
                headers=HEADERS, data={"error": str(exc)[:2000]}, timeout=30,
            )
        except Exception as tell:  # noqa: BLE001 — the server's stuck-job sweeper will pick the job up
            print(f"[job {job_id}] fail report lost: {tell}")
    finally:
        CURRENT.update(job_id=None, progress=None)


def start_comfy(folder: str) -> subprocess.Popen:
    """Start ComfyUI from its folder (venv, .venv or portable) and wait for it to respond."""
    root = Path(folder).resolve()
    python = next((p for p in (
        root / "venv" / "Scripts" / "python.exe", root / "venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python",
        root.parent / "python_embeded" / "python.exe",
    ) if p.is_file()), Path(sys.executable))
    port = COMFY.rsplit(":", 1)[-1].split("/")[0]
    log = open(HERE / "comfyui.log", "w", encoding="utf-8")  # noqa: SIM115 — lives until exit
    proc = subprocess.Popen([str(python), "main.py", "--listen", "127.0.0.1", "--port", port],
                            cwd=root, stdout=log, stderr=subprocess.STDOUT)
    print(f"starting ComfyUI from {root} (log: worker/comfyui.log)")
    while proc.poll() is None:
        try:
            requests.get(f"{COMFY}/system_stats", timeout=2).raise_for_status()
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(2)
    sys.exit(f"ComfyUI exited with code {proc.returncode}, see worker/comfyui.log")


def main() -> None:
    ap = argparse.ArgumentParser(description="Procyon Archive image worker")
    ap.add_argument("--comfy", metavar="DIR", help="start ComfyUI from this folder and stop it on exit")
    args = ap.parse_args()
    if not SERVER or not TOKEN:
        sys.exit("Set PA_SERVER_URL and PA_WORKER_TOKEN (environment or worker/.env)")
    comfy = start_comfy(args.comfy) if args.comfy else None
    print(f"worker up: server={SERVER} comfy={COMFY} dit={ZIMAGE_UNET} steps={ZIMAGE_STEPS} cfg=1.0")
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    try:
        while True:
            try:
                # caps: inpaint jobs will not go to an older worker version
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
    except KeyboardInterrupt:
        print("stopping")
    finally:
        if comfy:
            comfy.terminate()
            try:
                comfy.wait(15)
            except subprocess.TimeoutExpired:
                comfy.kill()


if __name__ == "__main__":
    main()
