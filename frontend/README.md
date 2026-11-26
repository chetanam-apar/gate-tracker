# Frontend (dashboard)

React website that shows the data from the API.

## Run it on your computer

Needs Node.js 20+ (`node --version`). The API must be running too (see main README).

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

## Files

```
src/
├── main.jsx            starting point
├── App.jsx             sidebar + list of pages
├── api.js              ALL calls to the backend API (one place)
├── labels.js           nice names: "top_trending" -> "Top trending"
├── styles.css          all styling
├── pages/
│   ├── ChartsPage.jsx  pick platform / chart / device, see the table
│   ├── GenresPage.jsx  Roblox genre trends (line graph)
│   └── RunsPage.jsx    run history
└── components/
    ├── ChartTable.jsx  the games table
    ├── ChangeBadge.jsx ▲ 3 / ▼ 2 / NEW
    └── StatCard.jsx    small box at the top
```

`/api/...` calls are forwarded to the API at port 8000 (see `vite.config.js`).
