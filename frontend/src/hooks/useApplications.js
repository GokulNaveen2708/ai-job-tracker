import { useState, useCallback } from "react";
import { getApplications as fetchApps } from "../lib/api";

export function useApplications() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(true);

  const loadApplications = useCallback(async (reset = true) => {
    setLoading(true);
    setError(null);
    try {
      const cursor = reset ? null : nextCursor;
      const data = await fetchApps(cursor, 20);
      const apps = data.applications || [];

      if (reset) {
        setApplications(apps);
      } else {
        setApplications((prev) => [...prev, ...apps]);
      }

      setNextCursor(data.nextCursor || null);
      setHasMore(!!data.nextCursor);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [nextCursor]);

  const loadMore = useCallback(() => {
    if (hasMore && !loading) {
      loadApplications(false);
    }
  }, [hasMore, loading, loadApplications]);

  const refresh = useCallback(() => {
    loadApplications(true);
  }, [loadApplications]);

  const updateLocal = useCallback((appId, updates) => {
    setApplications((prev) =>
      prev.map((app) => (app.id === appId ? { ...app, ...updates } : app))
    );
  }, []);

  const removeLocal = useCallback((appId) => {
    setApplications((prev) => prev.filter((app) => app.id !== appId));
  }, []);

  return {
    applications,
    loading,
    error,
    hasMore,
    loadApplications: refresh,
    loadMore,
    updateLocal,
    removeLocal,
  };
}
