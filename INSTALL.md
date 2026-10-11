# Installing Procyon Archive

What it looks like: https://virrius.github.io/procyon-archive-promo/

You need a computer that can run Docker: Windows 10/11, macOS or Linux, 8 GB of RAM or more.
Everything runs on that computer; players open it in a browser over your home network.

## 1. Install Docker Desktop

Download it from https://www.docker.com/products/docker-desktop/ and install it with the default
settings. Restart the computer if it asks you to. Then open Docker Desktop once and leave it running.

## 2. Get Procyon Archive

Open https://github.com/virrius/procyon-archive, press the green **Code** button → **Download ZIP**,
then unzip it anywhere, for example into `Documents\procyon-archive`.

## 3. Start it

Open a terminal in the unzipped folder:

- **Windows:** open the folder, click the address bar at the top, type `cmd` and press Enter.
- **macOS:** open Terminal, type `cd `, drag the folder into the window and press Enter.

Then type this and press Enter:

```
docker compose up -d --build
```

The first start takes 5–10 minutes. Later starts take seconds.

## 4. Sign in

Open http://localhost:5180 in a browser and sign in as `admin` with the password `admin`.
It will ask you to set your own password right away.

The interface starts in Russian. Press **Admin space**, open **Язык** and pick English.

Then, in **Admin space**:

1. **Campaigns**: press **new campaign** to start an empty one, with the sector's factions, places
   and the Procyon map already in it.
2. To look around a filled campaign first, press **import from archive** and pick
   `samples/demo-silence-over-brekk.zip` from the project folder.

Open the campaign. Under **GM space → Accounts**, press **+ grant access** to create a login and
password for each player, then give them to the players in person.

Players on the same network open `http://<your computer's address>:5180`.

## Pictures and news (optional)

Everything works without them. To write prompts and news, enter the address and key of any
OpenAI-compatible service in **Admin space → LLM**. Pictures are drawn either by that kind of
service (**Admin space → Images**) or by the local worker on your own NVIDIA card with 16 GB of
memory (see `worker/README.md`).

## Stopping and updating

- Stop: run `docker compose down` in the same folder. Your campaigns stay.
- Update: download the new ZIP, unzip it over the old folder and run `docker compose up -d --build`.
- Start over from scratch (this **deletes all campaigns**): `docker compose down -v`.
