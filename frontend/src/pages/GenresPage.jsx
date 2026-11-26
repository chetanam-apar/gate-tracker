import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { DEVICE_NAMES, chartName, formatDay, formatNumber } from "../labels.js";

// Genre trends (Roblox only): total live players per genre, per day.
// Each line = one genre. Height = players of all its games in the chosen chart that day.

const COLORS = ["#2f5fd0", "#d9822b", "#2e7d32", "#c62828", "#7b4fbf", "#00838f", "#ad1457", "#6d6d6d"];
const MAX_LINES = 8; // more lines than this is hard to read

export default function GenresPage() {
  const [available, setAvailable] = useState(null);
  const [chart, setChart] = useState("top_playing_now");
  const [device, setDevice] = useState("high_end_phone");
  const [days, setDays] = useState(30);
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.charts().then(setAvailable).catch((e) => setError(e.message));
  }, []);

  // Roblox charts and devices that really exist in the database
  const robloxCharts = useMemo(() => {
    const charts = {};
    for (const c of available?.charts || []) {
      if (c.platform === "roblox") (charts[c.chart] ??= []).push(c.device);
    }
    return charts;
  }, [available]);

  useEffect(() => {
    if (!available) return;
    setError(null);
    api.robloxGenres(chart, device, days).then(setTrend).catch((e) => { setTrend(null); setError(e.message); });
  }, [available, chart, device, days]);

  // Recharts wants one object per date: { date: "...", Simulation: 1200, RPG: 800, ... }
  const genres = (trend?.genres || []).slice(0, MAX_LINES);
  const rows = (trend?.dates || []).map((d, i) => {
    const row = { date: d };
    for (const g of genres) row[g.genre] = g.players[i];
    return row;
  });

  if (!available) return error ? <div className="error-box">{error}</div> : <p className="muted">Loading…</p>;
  if (Object.keys(robloxCharts).length === 0) {
    return <div className="error-box">No Roblox data yet. Run: python -m app.cli collect</div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Roblox genre trends</h1>
        <div className="pickers">
          <select value={chart} onChange={(e) => setChart(e.target.value)}>
            {Object.keys(robloxCharts).sort().map((c) => <option key={c} value={c}>{chartName(c)}</option>)}
          </select>
          <select value={device} onChange={(e) => setDevice(e.target.value)}>
            {(robloxCharts[chart] || []).map((d) => <option key={d} value={d}>{DEVICE_NAMES[d] || d}</option>)}
          </select>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      <p className="muted hint">
        Each line is a genre. Its height is the total players right now of all its games in “{chartName(chart)}”.
      </p>

      {error && <div className="error-box">Couldn't load data: {error}</div>}

      {trend && (
        <>
          {trend.dates.length < 2 && (
            <div className="info-box">
              Only {trend.dates.length} day of data so far, so each genre is a single dot.
              The lines appear after the 12 AM job has run a few nights.
            </div>
          )}
          <div className="card chart-card">
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={rows} margin={{ top: 10, right: 20, bottom: 0, left: 10 }}>
                <CartesianGrid stroke="#e4e3de" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(d) => formatDay(d).slice(5, 11)} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={compactNumber} tick={{ fontSize: 12 }} width={56} />
                <Tooltip formatter={(v) => formatNumber(v)} labelFormatter={formatDay} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {genres.map((g, i) => (
                  <Line key={g.genre} type="monotone" dataKey={g.genre} stroke={COLORS[i % COLORS.length]}
                        strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <h2 className="section-title">Latest day: {formatDay(trend.dates.at(-1))}</h2>
          <table className="chart-table">
            <thead>
              <tr>
                <th>Genre</th>
                <th className="col-num">Players now</th>
                <th className="col-num">Games in chart</th>
              </tr>
            </thead>
            <tbody>
              {trend.genres.map((g) => (
                <tr key={g.genre}>
                  <td>{g.genre}</td>
                  <td className="col-num">{formatNumber(g.players.at(-1))}</td>
                  <td className="col-num">{g.games.at(-1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

// 1250000 -> "1.3M", 45000 -> "45K"
function compactNumber(n) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}
