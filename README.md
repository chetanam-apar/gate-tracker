# 🎮 Game Tracker

Tracks the **top 50 games in India** on the App Store, Play Store and Roblox, every night at 12 AM.
It saves each day's data so we can see trends over time, and shows it on a dashboard.

> **Status:** Step 1 of 8 done. The App Store collector works. Database, scheduler and dashboard are coming next.

---

## What's inside

```
game-tracker/
├── config.yaml          ← SETTINGS. Change country, top N, platforms here. No coding needed.
├── .env.example         ← template for secrets. Copy it to .env
├── backend/
│   ├── app/
│   │   ├── core/        ← shared tools: settings loader, logs, HTTP client with retries
│   │   ├── collectors/  ← one file per platform. Each one fetches data and converts it
│   │   └── cli.py       ← the command you run
│   └── tests/           ← automatic checks with saved sample data
└── frontend/            ← dashboard (Step 6)
```

## How data flows

```
config.yaml → cli.py → each collector → platform API → convert to GameRank → print / save
```

Every platform returns data in a different shape. Each collector converts it into the same
shape (`GameRank`), so the rest of the app doesn't care where the data came from.

---

## Run it on your computer (first time)

Open Terminal in the project folder, then:

```bash
cp .env.example .env              # make your own settings file for secrets
cd backend
python3 -m venv .venv             # create a private Python space for this project
source .venv/bin/activate         # turn it on (you'll see (.venv) in the terminal)
pip install -r requirements-dev.txt
```

## Everyday commands (from the `backend/` folder, with `.venv` active)

| What | Command |
|---|---|
| Fetch all enabled platforms | `python -m app.cli collect` |
| Fetch only App Store | `python -m app.cli collect --platform appstore` |
| Fetch and save to `data/` as JSON | `python -m app.cli collect --save` |
| Run tests | `python -m pytest` |

Next time you only need `cd backend` and `source .venv/bin/activate`.

---

## For non-tech users: changing settings

Open `config.yaml` in any text editor:

- **Change country:** `country: "in"` → `"us"` for USA
- **Save top 100 instead of 50:** `top_n: 50` → `top_n: 100`
- **Turn a platform off:** `enabled: true` → `enabled: false`

If you type something wrong, the app stops and tells you exactly which line is wrong.

## Data sources

| Platform | Source | Gives |
|---|---|---|
| App Store | Apple public RSS feed (official, free, no key) | Rank in Top Free / Paid / Grossing |
| Play Store | Step 3 | Rank |
| Roblox | Step 3 | Live player count |
