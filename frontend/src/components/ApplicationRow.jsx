import "./ApplicationRow.css";

const STATUSES = ["applied", "oa", "interview", "offer"];
const STATUS_LABELS = { applied: "Applied", oa: "OA", interview: "Interview", offer: "Offer" };

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export default function ApplicationRow({ application, onSelect, onEdit, onDelete }) {
  const { company, role, status, manualOverride, lastActivityAt } = application;
  const isTerminal = ["rejected", "withdrawn"].includes(status);
  const currentIndex = STATUSES.indexOf(status);

  return (
    <div
      className={`app-row ${isTerminal ? "app-row--terminal" : ""}`}
      onClick={() => onSelect(application)}
      id={`app-row-${application.id}`}
    >
      <div className="app-row__info">
        <h3 className="app-row__company">{company}</h3>
        <p className="app-row__role">{role}</p>
      </div>

      <div className="app-row__pipeline">
        {isTerminal ? (
          <div className={`app-row__terminal-badge ${status === "rejected" ? "badge-red" : "badge-gray"}`}>
            {status === "rejected" ? "Rejected" : "Withdrawn"}
          </div>
        ) : (
          <div className="app-row__progress">
            {STATUSES.map((s, i) => (
              <div
                key={s}
                className={`progress-step ${i <= currentIndex ? "progress-step--filled" : ""}`}
              >
                <div className="progress-step__bar" />
                <span className="progress-step__label">{STATUS_LABELS[s]}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="app-row__meta">
        <span className="app-row__time">{timeAgo(lastActivityAt)}</span>
        {manualOverride && (
          <span className="badge badge-blue" title="Manually verified">
            ✏️ Verified
          </span>
        )}
      </div>

      <div className="app-row__actions">
        <button
          className="btn btn-ghost btn-icon"
          onClick={(e) => { e.stopPropagation(); onEdit(application); }}
          title="Edit"
        >
          ✏️
        </button>
        <button
          className="btn btn-ghost btn-icon app-row__delete"
          onClick={(e) => { e.stopPropagation(); onDelete(application); }}
          title="Delete"
        >
          🗑️
        </button>
      </div>
    </div>
  );
}
