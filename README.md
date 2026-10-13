<p align="center"><img src="docs/banner.webp" alt="Procyon Archive"></p>

**[Overview and screenshots](https://virrius.github.io/procyon-archive-promo/)**

![Procyon Archive with the sector map open](docs/screenshot.webp)

## Run

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/): Windows, macOS or Linux, 8 GB RAM.

1. Download `procyon-archive.zip` from [Releases](https://github.com/virrius/procyon-archive/releases/latest) and unzip it.
2. Open a terminal in the unzipped folder and run `docker compose up -d`.
3. Open http://localhost:7726, sign in as `admin` / `admin`, set your password.
4. Optional, pictures and news: add an external model key in Admin space → LLM and Images,
   or draw on your own NVIDIA GPU with the [local image worker](worker/README.md).

Players on your network open `http://<your computer's IP>:7726`.
Stopping, updating, pictures and news: [INSTALL.md](INSTALL.md).

## Structure

```
backend/     API: FastAPI, PostgreSQL
frontend/    web app: React, nginx
worker/      image worker for your own GPU (optional)
assets/      rules clippings, sector map
release/     docker-compose.yml for installing from images
samples/     demo campaign
docs/        story boards API for agents
INSTALL.md   how to install
DEV.md       development, deploy
```
