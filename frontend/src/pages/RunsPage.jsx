import { useEffect, useState } from "react";
import { api } from "../api.js";
import { formatDateTime, formatNumber } from "../labels.js";

// Run history: every time "collect" ran, did it work?
export default function RunsPage() {
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-box">Couldn't load runs: {error}</div>;
  if (!runs) return <p className="muted">Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h1>Run history</h1>
      </div>
      <table className="chart-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Started</th>
            <th>Status</th>
            <th className="col-num">Saved</th>
            <th>Trigger</th>
            <th>Problem</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>{run.id}</td>
              <td>{formatDateTime(run.started_at)}</td>
              <td><span className={`badge badge-${run.status}`}>{run.status}</span></td>
              <td className="col-num">{formatNumber(run.games_collected)}</td>
              <td className="muted">{run.trigger}</td>
              <td className="muted problem">
                {run.failed_platforms ? `Failed: ${run.failed_platforms}` : run.error_message || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
