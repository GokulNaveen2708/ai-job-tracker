const BASE_URL = import.meta.env.VITE_BACKEND_URL;

async function authFetch(path, options = {}) {
  const { getAuth } = await import("firebase/auth");
  const token = await getAuth().currentUser?.getIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    const err = new Error(error.detail?.message || error.detail || "Request failed");
    err.status = res.status;
    err.data = error;
    throw err;
  }

  return res.json();
}

export async function authCallback(idToken, accessToken) {
  const res = await fetch(`${BASE_URL}/auth/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken, access_token: accessToken }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "Auth callback failed");
  }
  return res.json();
}

export async function runSync() {
  return authFetch("/sync/run", { method: "POST" });
}

export async function getApplications(cursor = null, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  return authFetch(`/applications/?${params}`);
}

export async function getTimeline(appId) {
  return authFetch(`/applications/${appId}/timeline`);
}

export async function overrideApplication(appId, fields) {
  return authFetch(`/applications/${appId}`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
}

export async function deleteApplication(appId) {
  return authFetch(`/applications/${appId}`, { method: "DELETE" });
}
