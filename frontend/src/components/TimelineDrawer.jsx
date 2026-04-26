import { useState, useEffect } from "react";
import { getTimeline } from "../lib/api";
import "./TimelineDrawer.css";

const EVENT_ICONS = {
  email_received: "📧",
  status_change: "🔄",
  manual_edit: "✏️",
  sync_created: "🔗",
};

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export default function TimelineDrawer({ application, onClose, onEdit }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!application) return;
    setLoading(true);
    getTimeline(application.id)
      .then((data) => setEvents(data.events || []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [application]);

  if (!application) return null;

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer__header">
          <div>
            <h2 className="drawer__company">{application.company}</h2>
            <p className="drawer__role">{application.role}</p>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
        </div>

        <div className="drawer__status-row">
          <span className={`badge badge-${application.status === "rejected" ? "red" : application.status === "offer" ? "green" : "blue"}`}>
            {application.status?.toUpperCase()}
          </span>
          {application.manualOverride && <span className="badge badge-blue">✏️ Verified</span>}
        </div>

        <div className="drawer__content">
          {loading ? (
            <div className="drawer__loading">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton" style={{ height: 60, marginBottom: 12 }} />
              ))}
            </div>
          ) : (
            <>
              {/* Highlight Latest Email */}
              {events.length > 0 && events.find(e => e.emailSubject) && (
                <div className="drawer__latest-email">
                  <span className="drawer__latest-email-label">Latest Email Subject:</span>
                  <p className="drawer__latest-email-subject">
                    {events.find(e => e.emailSubject).emailSubject}
                  </p>
                  <p className="drawer__latest-email-time">
                    Received {timeAgo(events.find(e => e.emailSubject).timestamp)}
                  </p>
                </div>
              )}

              {events.length === 0 ? (
                <p className="drawer__empty">No timeline events yet.</p>
              ) : (
                <div className="timeline">
              {events.map((event, i) => (
                <div className="timeline-item" key={event.id || i}>
                  <div className="timeline-item__line" />
                  <div className="timeline-item__dot">
                    {EVENT_ICONS[event.type] || "📌"}
                  </div>
                  <div className="timeline-item__content">
                    <div className="timeline-item__header">
                      <span className="timeline-item__type">
                        {event.type?.replace(/_/g, " ")}
                      </span>
                      <span className="timeline-item__time">
                        {timeAgo(event.timestamp)}
                      </span>
                    </div>
                    {event.emailSubject && (
                      <p className="timeline-item__subject">{event.emailSubject}</p>
                    )}
                    {event.description && (
                      <p className="timeline-item__desc">{event.description}</p>
                    )}
                    {event.toStatus && (
                      <div className="timeline-item__status-change">
                        {event.fromStatus && (
                          <span className="badge badge-gray">{event.fromStatus}</span>
                        )}
                        {event.fromStatus && <span className="timeline-arrow">→</span>}
                        <span className="badge badge-green">{event.toStatus}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          </>
        )}
        </div>

        <div className="drawer__footer">
          <button className="btn btn-primary" onClick={() => onEdit(application)}>
            ✏️ Override
          </button>
        </div>
      </div>
    </>
  );
}
