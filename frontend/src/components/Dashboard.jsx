import { useState, useEffect } from "react";
import { useApplications } from "../hooks/useApplications";
import { useSync } from "../hooks/useSync";
import { deleteApplication as apiDelete } from "../lib/api";
import { signOut } from "firebase/auth";
import { auth } from "../lib/firebase";
import ApplicationRow from "./ApplicationRow";
import StatsPanel from "./StatsPanel";
import TimelineDrawer from "./TimelineDrawer";
import OverrideModal from "./OverrideModal";
import "./Dashboard.css";

export default function Dashboard({ user }) {
  const {
    applications, loading: appsLoading, hasMore,
    loadApplications, loadMore, updateLocal, removeLocal,
  } = useApplications();
  const { sync, loading: syncLoading, error: syncError, results, cooldownRemaining } = useSync();

  const [selectedApp, setSelectedApp] = useState(null);
  const [editApp, setEditApp] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadApplications();
  }, []);

  // ── Auto-Sync on Load ──────────────────────────────────────────────
  useEffect(() => {
    if (!user) return;
    
    const lastSyncStr = localStorage.getItem(`lastAutoSync_${user.uid}`);
    const now = Date.now();
    const TWELVE_HOURS = 12 * 60 * 60 * 1000;
    
    if (!lastSyncStr || (now - parseInt(lastSyncStr, 10)) > TWELVE_HOURS) {
      // Small delay to allow initial load to finish
      setTimeout(() => {
        handleSync();
      }, 2000);
    }
  }, [user]);

  const handleSync = async () => {
    const result = await sync();
    if (result) {
      loadApplications();
      if (user) {
        localStorage.setItem(`lastAutoSync_${user.uid}`, Date.now().toString());
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await apiDelete(deleteConfirm.id);
      removeLocal(deleteConfirm.id);
      setDeleteConfirm(null);
    } catch (err) {
      alert("Failed to delete: " + err.message);
    } finally {
      setDeleting(false);
    }
  };

  const handleOverrideSaved = (appId, updates) => {
    updateLocal(appId, updates);
  };

  const handleSignOut = () => signOut(auth);

  return (
    <div className="dashboard">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="dashboard__header">
        <div className="dashboard__header-left">
          <h1 className="dashboard__title">
            <span className="dashboard__logo">✓</span>
            Job Tracker
          </h1>
        </div>
        <div className="dashboard__header-right">
          <button
            className="btn btn-primary dashboard__sync-btn"
            onClick={handleSync}
            disabled={syncLoading || cooldownRemaining > 0}
            id="sync-btn"
          >
            {syncLoading ? (
              <><span className="sync-spinner" /> Syncing...</>
            ) : cooldownRemaining > 0 ? (
              `⏳ Wait ${Math.ceil(cooldownRemaining / 60)}m`
            ) : (
              <>🔄 Sync Gmail</>
            )}
          </button>
          <div className="dashboard__user">
            <span className="dashboard__email">{user?.email}</span>
            <button className="btn btn-ghost" onClick={handleSignOut}>Sign out</button>
          </div>
        </div>
      </header>

      {/* ── Sync feedback ───────────────────────────────────────────── */}
      {syncLoading && (
        <div className="dashboard__alert dashboard__alert--info">
          ⏳ Scanning your inbox... First sync can take 1-2 minutes. Please don't close this tab.
        </div>
      )}
      {syncError && (
        <div className="dashboard__alert dashboard__alert--error">
          {syncError.includes("Rate limited") || syncError.includes("429")
            ? "⏳ You've synced recently. Please try again in 30 minutes."
            : syncError}
        </div>
      )}
      {results && !syncLoading && (
        <div className="dashboard__alert dashboard__alert--success">
          Sync complete — {results.processed} processed, {results.created} new, {results.updated} updated, {results.skipped} skipped
        </div>
      )}

      {/* ── Stats ───────────────────────────────────────────────────── */}
      <div className="container">
        <StatsPanel applications={applications} />

        {/* ── Application Rows ──────────────────────────────────────── */}
        {appsLoading && applications.length === 0 ? (
          <div className="dashboard__list">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="skeleton" style={{ height: 60 }} />
            ))}
          </div>
        ) : applications.length === 0 ? (
          <div className="dashboard__empty">
            <p className="dashboard__empty-icon">📭</p>
            <p className="dashboard__empty-title">No applications yet</p>
            <p className="dashboard__empty-desc">
              Click "Sync Gmail" to scan your inbox for job application emails.
            </p>
          </div>
        ) : (
          <>
            <div className="dashboard__list">
              {applications.map((app) => (
                <ApplicationRow
                  key={app.id}
                  application={app}
                  onSelect={setSelectedApp}
                  onEdit={setEditApp}
                  onDelete={setDeleteConfirm}
                />
              ))}
            </div>

            {hasMore && (
              <div className="dashboard__load-more">
                <button className="btn btn-secondary" onClick={loadMore} disabled={appsLoading}>
                  {appsLoading ? "Loading..." : "Load More"}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Drawer ──────────────────────────────────────────────────── */}
      {selectedApp && (
        <TimelineDrawer
          application={selectedApp}
          onClose={() => setSelectedApp(null)}
          onEdit={(app) => { setSelectedApp(null); setEditApp(app); }}
        />
      )}

      {/* ── Override Modal ──────────────────────────────────────────── */}
      {editApp && (
        <OverrideModal
          application={editApp}
          onClose={() => setEditApp(null)}
          onSaved={handleOverrideSaved}
        />
      )}

      {/* ── Delete Confirm ──────────────────────────────────────────── */}
      {deleteConfirm && (
        <div className="overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 8 }}>Delete Application</h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 20 }}>
              Are you sure you want to delete <strong>{deleteConfirm.company} — {deleteConfirm.role}</strong>? This cannot be undone.
            </p>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
