# Installing Procyon Archive

Needs Windows 10/11, macOS or Linux with 8 GB RAM.

```mermaid
flowchart LR
  P[Players' browsers] -- http://your-ip:7726 --> D[Your computer: Docker]
```

## Install

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.
2. Download `procyon-archive.zip` from [Releases](https://github.com/virrius/procyon-archive/releases/latest) and unzip it.
3. Open a terminal in the unzipped folder and run:
   ```
   docker compose up -d
   ```
   Windows: type `cmd` in the folder's address bar. macOS: type `cd `, drag the folder into Terminal.
4. Open http://localhost:7726, sign in as `admin` / `admin`, set your password.

The first start downloads about 250 MB. After that Procyon Archive starts with Docker Desktop.

## First steps

| Where | What |
|---|---|
| Admin space → Campaigns | create a campaign, or **import from archive** → `demo-silence-over-brekk.zip` |
| GM space → Accounts | **+ grant access**: a login per player |
| Admin space → Language | English / Russian |

Players on your home network open `http://<your computer's IP>:7726`. Players elsewhere:

| | |
|---|---|
| ngrok | install [ngrok](https://ngrok.com/download), run `ngrok http 7726`, send players the `https://…` address it prints. Works while your computer is on |
| Server | the same steps on a VPS with Docker, open port 7726; players open `http://<server IP>:7726`. Set the admin password right after the first start |

## Optional: pictures and news

| Feature | Setup |
|---|---|
| Prompts, news | Admin space → LLM: any OpenAI-compatible API |
| Pictures via API | Admin space → Images: an OpenAI-compatible image API |
| Pictures on your GPU | local pipeline, ComfyUI + worker: [worker/README.md](https://github.com/virrius/procyon-archive/blob/main/worker/README.md) |

## Manage

Run in the same folder:

| | |
|---|---|
| Stop | `docker compose down` |
| Update | `docker compose pull` then `docker compose up -d` |
| Delete all campaigns | `docker compose down -v` |
| Backup a campaign | Admin space → Campaigns → **export** |

Port 7726 busy: change it in `docker-compose.yml`.
From source: `docker compose up -d --build` in a clone of the repository.
