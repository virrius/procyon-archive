# Image worker

Draws Procyon Archive pictures on your own NVIDIA GPU.

```mermaid
flowchart LR
  A[Procyon Archive] -- job --> W[gen_worker.py]
  W -- graph --> C[ComfyUI on GPU]
  C -- image --> W
  W -- candidates --> A
```

While the worker runs, it takes jobs from the queue. Nothing to switch in the app.

## Requirements

- NVIDIA GPU, 16 GB VRAM
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
- Python 3.10+ with `requests` (`pip install -r requirements.txt`)

Models, into ComfyUI's `models/`:

| File | Folder |
|---|---|
| [z_image_turbo_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_int8_convrot.safetensors) | `diffusion_models` |
| [qwen_3_4b_fp8_mixed.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors) | `text_encoders` |
| [ae.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors) | `vae` |

## Setup

1. Server: `.env` next to `docker-compose.yml`, then `docker compose up -d`.
   ```
   PA_WORKER_TOKEN=any-long-random-string
   ```
2. Worker: `.env` next to `gen_worker.py`.
   ```
   PA_SERVER_URL=http://<server address>:7726
   PA_WORKER_TOKEN=<same string>
   ```

## Run

```
python gen_worker.py --comfy <ComfyUI folder>   # starts ComfyUI, stops it on exit
python gen_worker.py                            # ComfyUI already running
```

Ctrl+C frees the GPU. Jobs wait in the queue until the next start.
ComfyUI not on `127.0.0.1:8188`: set `COMFY_URL`.

## Problems

| In the log | Fix |
|---|---|
| `poll error: 401` | `PA_WORKER_TOKEN` differs on server and worker |
| `ComfyUI exited` | see `worker/comfyui.log` |
| `os error 1455` (Windows) | enlarge the page file |
