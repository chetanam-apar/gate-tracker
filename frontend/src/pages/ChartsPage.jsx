import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { DEVICE_NAMES, PLATFORM_NAMES, chartName, formatDay, formatNumber } from "../labels.js";
import ChartTable from "../components/ChartTable.jsx";
import StatCard from "../components/StatCard.jsx";

// Charts page: pick a platform, a chart and a device, see the top games.
export default function ChartsPage() {
  const [available, setAvailable] = useState(null); // every chart saved on the latest day
  const [platform, setPlatform] = useState("appstore");
  const [chart, setChart] = useState("top_free");
  const [device, setDevice] = useState("all");
  const [dates, setDates] = useState([]);   // days that have data for this chart, newest first
  const [date, setDate] = useState("");     // "" = latest
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // 1. Load the list of charts once, when the page opens
  useEffect(() => {
    api.charts().then(setAvailable).catch((e) => setError(e.message));
  }, []);

  // Build the dropdown options from what's really in the database
  const options = useMemo(() => {
    const byPlatform = {};
    for (const c of available?.charts || []) {
      byPlatform[c.platform] ??= {};
      byPlatform[c.platform][c.chart] ??= [];
      byPlatform[c.platform][c.chart].push(c.device);
    }
    return byPlatform;
  }, [available]);

  const charts = Object.keys(options[platform] || {}).sort();
  const devices = options[platform]?.[chart] || [];

  // When the platform changes, pick its first chart and device
  function changePlatform(next) {
    const firstChart = Object.keys(options[next] || {}).sort()[0];
    setPlatform(next);
    setChart(firstChart);
    setDevice(pickDevice(options[next]?.[firstChart]));
  }

  function changeChart(next) {
    setChart(next);
    if (!options[platform]?.[next]?.includes(device)) setDevice(pickDevice(options[platform]?.[next]));
  }

  // 2. When platform / chart / device changes: load the list of dates, go back to the latest day
  useEffect(() => {
    if (!available || !chart) return;
    setDate("");
    api.chartDates(platform, chart, device).then(setDates).catch(() => setDates([]));
  }, [available, platform, chart, device]);

  // 3. Load the chosen chart whenever any choice changes (including the date)
  useEffect(() => {
    if (!available || !chart) return;
    setLoading(true);
    setError(null);
    api.chart(platform, chart, device, date)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [available, platform, chart, device, date]);

  if (error && !available) return <ErrorBox message={error} />;
  if (!available) return <p className="muted">Loading…</p>;
  if (available.charts.length === 0) {
    return <ErrorBox message="No data yet. Run: python -m app.cli collect" />;
  }

  const rows = data?.rows || [];
  const climber = [...rows].filter((r) => r.change > 0).sort((a, b) => b.change - a.change)[0];
  const newCount = rows.filter((r) => r.change == null).length;
  const isRoblox = platform === "roblox";

  return (
    <>
      <div className="page-header">
        <h1>Top games in India</h1>
        <div className="pickers">
          <select value={platform} onChange={(e) => changePlatform(e.target.value)}>
            {Object.keys(options).sort().map((p) => (
              <option key={p} value={p}>{PLATFORM_NAMES[p] || p}</option>
            ))}
          </select>
          <select value={chart} onChange={(e) => changeChart(e.target.value)}>
            {charts.map((c) => <option key={c} value={c}>{chartName(c)}</option>)}
          </select>
          {devices.length > 1 && (
            <select value={device} onChange={(e) => setDevice(e.target.value)}>
              {devices.map((d) => <option key={d} value={d}>{DEVICE_NAMES[d] || d}</option>)}
            </select>
          )}
          <select value={date} onChange={(e) => setDate(e.target.value)} title="Only days with saved data are listed">
            {dates.map((d, i) => (
              <option key={d} value={i === 0 ? "" : d}>{i === 0 ? `Latest (${formatDay(d)})` : formatDay(d)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="stats">
        <StatCard label="Date" value={data?.date ? formatDay(data.date) : "-"}
                  note={dates.length ? `${dates.length} day${dates.length > 1 ? "s" : ""} of history` : ""} />
        <StatCard
          label="Biggest climber"
          value={climber ? climber.name : "-"}
          note={climber ? `up ${climber.change} places` : "needs 2 days of data"}
          tone={climber ? "up" : ""}
        />
        <StatCard label="New in this chart" value={newCount} note="compared to the day before" />
        {isRoblox && rows[0] && (
          <StatCard label="Most players (#1)" value={formatNumber(rows[0].player_count)} note={rows[0].name} />
        )}
      </div>

      {error && <ErrorBox message={error} />}
      {loading && !data ? <p className="muted">Loading…</p> : <ChartTable rows={rows} showPlayers={isRoblox} />}
    </>
  );
}

function pickDevice(devices = []) {
  if (devices.includes("high_end_phone")) return "high_end_phone"; // phones first: most players in India
  return devices[0] || "all";
}

function ErrorBox({ message }) {
  return <div className="error-box">Couldn't load data: {message}</div>;
}
