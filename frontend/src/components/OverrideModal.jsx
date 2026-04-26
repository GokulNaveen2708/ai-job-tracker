import { useState, useEffect } from "react";
import { overrideApplication } from "../lib/api";
import "./OverrideModal.css";

const STATUS_OPTIONS = [
  { value: "applied", label: "Applied" },
  { value: "oa", label: "Online Assessment" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

export default function OverrideModal({ application, onClose, onSaved }) {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (application) {
      setCompany(application.company || "");
      setRole(application.role || "");
      setStatus(application.status || "applied");
    }
  }, [application]);

  if (!application) return null;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const fields = {};
      if (company !== application.company) fields.company = company;
      if (role !== application.role) fields.role = role;
      if (status !== application.status) fields.status = status;

      if (Object.keys(fields).length === 0) {
        onClose();
        return;
      }

      await overrideApplication(application.id, fields);
      onSaved(application.id, { ...fields, manualOverride: true });
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal override-modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="override-modal__title">Edit Application</h2>
        <p className="override-modal__subtitle">
          Changes will be marked as manually verified and won't be overwritten by future syncs.
        </p>

        <div className="override-modal__field">
          <label className="override-modal__label">Company</label>
          <input className="input" value={company} onChange={(e) => setCompany(e.target.value)} />
        </div>

        <div className="override-modal__field">
          <label className="override-modal__label">Role</label>
          <input className="input" value={role} onChange={(e) => setRole(e.target.value)} />
        </div>

        <div className="override-modal__field">
          <label className="override-modal__label">Status</label>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {error && <p className="override-modal__error">{error}</p>}

        <div className="override-modal__actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
