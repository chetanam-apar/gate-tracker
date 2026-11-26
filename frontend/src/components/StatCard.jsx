// A small box with a label and a big value, used at the top of a page.
export default function StatCard({ label, value, note, tone }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone || ""}`}>{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}
