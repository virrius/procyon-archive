<p align="center"><img src="docs/banner.webp" alt="Procyon Archive"></p>

**[Overview highlights and screenshots](https://virrius.github.io/procyon-archive-promo/)**

![Procyon Archive with the sector map open](docs/screenshot.webp)

## Run

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/): Windows, macOS or Linux, 8 GB RAM.

1. Download `procyon-archive.zip` from [Releases](https://github.com/virrius/procyon-archive/releases/latest) and unzip it.
2. Open a terminal in the unzipped folder and run `docker compose up -d`.
   Windows: type `cmd` in the folder's address bar. macOS: type `cd `, drag the folder into Terminal.
3. Open http://localhost:7726, sign in as `admin` / `admin`, set your password.
4. Optional, pictures and news: add an OpenAI-compatible API key in Admin space → LLM and Images,
   or draw on your own NVIDIA GPU with the [local image worker](worker/README.md).

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

## Manage

Run in the unzipped folder:

| | |
|---|---|
| Stop | `docker compose down` |
| Update | `docker compose pull` then `docker compose up -d` |
| Delete all campaigns | `docker compose down -v`, then delete the `data` folder |
| Backup a campaign | Admin space → Campaigns → **export** |

Port 7726 busy: change it in `docker-compose.yml`.

## Structure

```
backend/     API: FastAPI, PostgreSQL
frontend/    web app: React, nginx
worker/      image worker for your own GPU (optional)
assets/      rules clippings, sector map
release/     docker-compose.yml for installing from images
samples/     demo campaign
docs/        development and deploy, story boards API for agents
```
