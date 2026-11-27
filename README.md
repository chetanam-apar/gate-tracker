# 🎮 Game Tracker

Tracks the **top 50 games in India** on the App Store, Play Store and Roblox, every night at 12 AM.
It saves each day's data so we can see trends over time, and shows it on a dashboard.

> **Status:** Step 3 done. App Store + Play Store + Roblox collectors, PostgreSQL database with daily history.
> Next: 12 AM scheduler (Step 4), backend API (Step 5), dashboard (Step 6).

---

## What's inside

```
game-tracker/
├── config.yaml          ← SETTINGS. Change country, top N, platforms here. No coding needed.
├── .env.example         ← template for secrets. Copy it to .env
├── docker-compose.yml   ← starts the database (later: the whole app)
├── scripts/             ← collect.sh (the nightly job) + install/uninstall cron
├── backend/
│   ├── app/
│   │   ├── core/        ← shared tools: settings loader, logs, HTTP client with retries
│   │   ├── collectors/  ← one file per platform. Each one fetches data and converts it
│   │   ├── db/          ← database tables (models.py) and all reads/writes (repository.py)
│   │   ├── api/         ← the web API the website calls (main.py)
│   │   └── cli.py       ← the commands you run
│   ├── migrations/      ← version history of the database tables (Alembic)
│   └── tests/           ← automatic checks with saved sample data
└── frontend/            ← dashboard (Step 6)
```

## How data flows

```
config.yaml → cli.py → each collector → platform API → GameRank → database
```

Every platform returns data in a different shape. Each collector converts it into the same
shape (`GameRank`), so the rest of the app doesn't care where the data came from.

## Database tables

| Table | One row = |
|---|---|
| `games` | one game on one platform (name, developer, icon). Stored once. |
| `rankings` | one game's rank in one chart, on one device, on one day. This is the history. |
| `collection_runs` | one run of the job: when, success or fail, how many saved |

**No duplicates:** running `collect` many times on the same day replaces that day's chart, it doesn't add copies.

---

## Run it on your computer (first time)

Needs: Python 3.11+, Docker Desktop (open and running).

```bash
cp .env.example .env              # your own secrets file. Change the password in BOTH places
docker compose up -d              # start the database in the background
cd backend
python3 -m venv .venv             # create a private Python space for this project
source .venv/bin/activate         # turn it on (you'll see (.venv) in the terminal)
pip install -r requirements-dev.txt
alembic upgrade head              # create the tables
```

## Everyday commands (from `backend/`, with `.venv` active)

| What | Command |
|---|---|
| Fetch all enabled platforms and save | `python -m app.cli collect` |
| Fetch only, don't save | `python -m app.cli collect --dry-run` |
| List every chart saved today | `python -m app.cli charts` |
| Show saved chart with rank changes | `python -m app.cli show --chart top_free` |
| Show a Roblox chart (phone) | `python -m app.cli show --platform roblox --chart top_trending --device high_end_phone` |
| Show a chart for a past day | `python -m app.cli show --chart top_paid --date 2026-11-26` |
| History of runs (did it work?) | `python -m app.cli runs` |
| Run tests | `python -m pytest` |

Next time you only need: Docker Desktop open, `cd backend`, `source .venv/bin/activate`.

## The 12 AM job (automatic daily collection)

Every night at the time in `config.yaml` (`daily_run_time`, default `"00:00"` = 12 AM), cron runs
`scripts/collect.sh`, which runs `collect` and writes to `logs/collect_YYYY-MM.log`.

| What | Command (from the project folder) |
|---|---|
| Turn it on (or update the time after changing config.yaml) | `./scripts/install_cron.sh` |
| See it | `crontab -l` |
| Turn it off | `./scripts/uninstall_cron.sh` |
| Run it now by hand (same as cron) | `./scripts/collect.sh` |
| Read the log | `tail -50 logs/collect_$(date +%Y-%m).log` |

Did last night work? Check the **Run history** page (trigger = `scheduled`) or the log file.

**On a Mac:** cron only runs if the Mac is **on and awake** at that time, and **Docker Desktop is running**.
If it was asleep, that night is skipped (stores don't give past data). On EC2 the server is always on.

## The API (Step 4)

The website reads data through the API. Start it from `backend/` (with `.venv` active):

```bash
uvicorn app.api.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** in your browser. You can try every address there.
Stop it with `Ctrl + C`.

| Address | Gives back |
|---|---|
| `/api/health` | `{"status": "ok"}` if the API and database work |
| `/api/charts` | every chart saved on the latest day |
| `/api/charts/appstore/top_grossing` | one chart, with rank change |
| `/api/charts/roblox/top_trending?device=high_end_phone` | a Roblox chart for phones |
| `/api/runs` | history of collection runs |

## Database commands (from the project folder)

| What | Command |
|---|---|
| Start database | `docker compose up -d` |
| Stop database (data is kept) | `docker compose down` |
| Is it running? | `docker compose ps` |
| Open the database console | `docker exec -it gametracker-db psql -U gametracker` |

---

## For non-tech users: changing settings

Open `config.yaml` in any text editor:

- **Change country:** `country: "in"` → `"us"` for USA
- **Save top 100 instead of 50:** `top_n: 50` → `top_n: 100`
- **Turn a platform off:** `enabled: true` → `enabled: false`
- **Roblox: only some lists:** `charts: all` → `charts: [top_trending, top_playing_now]` (names from `python -m app.cli charts`)
- **Roblox: change devices:** edit the `devices:` list (`high_end_phone`, `computer`, `console`...)

If you type something wrong, the app stops and tells you exactly which line is wrong.

## Common problems

| You see | Fix |
|---|---|
| `Can't reach the database. Is Docker running?` | Open Docker Desktop, then `docker compose up -d` |
| `DATABASE_URL is missing` | Copy the database lines from `.env.example` into `.env` |
| `Tables are missing` / `column ... does not exist` | Run `alembic upgrade head` from `backend/` (needed after every update that adds a migration) |
| `password authentication failed` | Password in `DATABASE_URL` must match the one the database was created with |

## Data sources

| Platform | Source | Gives |
|---|---|---|
| App Store | Apple public RSS feed (official, free, no key) | Rank in Top Free / Paid / Grossing |
| Play Store | Copies the Play Store website's own internal request (same method as the open-source google-play-scraper). No login. **Unofficial, can break if Google changes it.** | Rank in Top Free / Paid / Grossing games |
| Roblox | Same API as roblox.com/charts (works without login, but not officially documented) | ~26 lists (Trending, Top Playing Now, Top Earning, genres...) with live player counts, per device |

Note: Roblox "Top Playing Now" is the same worldwide. "Top Trending" and others change by country and device.
