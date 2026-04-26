import { useState, useCallback, useRef } from "react";
import { runSync as apiRunSync } from "../lib/api";

const COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes
const MAX_BURST = 2;

export function useSync() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [cooldownEnd, setCooldownEnd] = useState(null);
  const syncCount = useRef(0);
  const lastSyncTime = useRef(null);

  const cooldownRemaining =
    cooldownEnd && cooldownEnd > Date.now()
      ? Math.ceil((cooldownEnd - Date.now()) / 1000)
      : 0;

  const sync = useCallback(async () => {
    // Client-side rate limit check
    const now = Date.now();
    if (lastSyncTime.current && now - lastSyncTime.current < COOLDOWN_MS) {
      if (syncCount.current >= MAX_BURST) {
        const remaining = COOLDOWN_MS - (now - lastSyncTime.current);
        setCooldownEnd(now + remaining);
        setError(`Rate limited. Please wait ${Math.ceil(remaining / 1000)}s`);
        return null;
      }
    } else {
      syncCount.current = 0;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await apiRunSync();
      setResults(data);
      syncCount.current += 1;
      lastSyncTime.current = now;
      return data;
    } catch (err) {
      if (err.status === 429) {
        const retryAfter = err.data?.detail?.retryAfter || 300;
        setCooldownEnd(Date.now() + retryAfter * 1000);
      }
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { sync, loading, error, results, cooldownRemaining };
}
