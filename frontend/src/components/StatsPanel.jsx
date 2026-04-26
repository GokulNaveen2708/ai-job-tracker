import "./StatsPanel.css";

const STAT_ITEMS = [
  { key: "total", label: "Total", icon: "📋" },
  { key: "active", label: "Active", icon: "🟢" },
  { key: "interviews", label: "Interviews", icon: "🎯" },
  { key: "offers", label: "Offers", icon: "🏆" },
];

function computeStats(applications) {
  const total = applications.length;
  if (total === 0) {
    return { total: 0, active: 0, interviews: 0, offers: 0 };
  }

  const active = applications.filter(
    (a) => !["rejected", "withdrawn", "offer"].includes(a.status)
  ).length;

  const responded = applications.filter((a) => a.status !== "applied").length;
  const interviews = applications.filter(
    (a) => ["interview", "offer"].includes(a.status)
  ).length;
  const offers = applications.filter((a) => a.status === "offer").length;

  return { total, active, interviews, offers };
}

export default function StatsPanel({ applications }) {
  const stats = computeStats(applications);

  return (
    <div className="stats-panel">
      {STAT_ITEMS.map((item, i) => (
        <div
          className="stat-pill"
          key={item.key}
          style={{ animationDelay: `${i * 0.06}s` }}
        >
          <span className="stat-icon">{item.icon}</span>
          <div className="stat-content">
            <span className="stat-value">
              {stats[item.key]}
              {item.suffix && stats[item.key] !== "—" ? item.suffix : ""}
            </span>
            <span className="stat-label">{item.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
