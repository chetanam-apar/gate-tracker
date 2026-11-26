// Shows how a game's rank moved since the previous day: ▲ 3, ▼ 2, = or NEW.
export default function ChangeBadge({ change }) {
  if (change == null) return <span className="badge badge-new">NEW</span>;
  if (change > 0) return <span className="change up">▲ {change}</span>;
  if (change < 0) return <span className="change down">▼ {-change}</span>;
  return <span className="change same">=</span>;
}
