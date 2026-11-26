import ChangeBadge from "./ChangeBadge.jsx";
import { formatNumber } from "../labels.js";

// The table of games for one chart.
export default function ChartTable({ rows, showPlayers }) {
  return (
    <table className="chart-table">
      <thead>
        <tr>
          <th className="col-rank">#</th>
          <th className="col-change">Change</th>
          <th>Game</th>
          <th>{showPlayers ? "Genre" : "Developer"}</th>
          {showPlayers && <th className="col-num">Players now</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.game_id}>
            <td className="col-rank">{row.rank}</td>
            <td className="col-change"><ChangeBadge change={row.change} /></td>
            <td>
              <div className="game">
                {row.icon_url ? <img src={row.icon_url} alt="" className="icon" loading="lazy"
                    onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} /> : <div className="icon" />}
                {row.store_url ? (
                  <a href={row.store_url} target="_blank" rel="noreferrer">{row.name}</a>
                ) : (
                  row.name
                )}
              </div>
            </td>
            <td className="muted">{showPlayers ? row.genre || "-" : row.developer || "-"}</td>
            {showPlayers && <td className="col-num">{formatNumber(row.player_count)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
