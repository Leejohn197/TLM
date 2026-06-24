const jsonHeaders = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: jsonHeaders,
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `请求失败：${response.status}`);
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),
  systems: () => request("/api/systems"),
  createSystem: (data) =>
    request("/api/systems", { method: "POST", body: JSON.stringify(data) }),
  updateSystem: (id, data) =>
    request(`/api/systems/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSystem: (id) => request(`/api/systems/${id}`, { method: "DELETE" }),
  accounts: (systemId) => request(`/api/systems/${systemId}/accounts`),
  createAccount: (systemId, data) =>
    request(`/api/systems/${systemId}/accounts`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateAccount: (accountId, data) =>
    request(`/api/accounts/${accountId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteAccount: (accountId) => request(`/api/accounts/${accountId}`, { method: "DELETE" }),
  fill: (data) => request("/api/fill", { method: "POST", body: JSON.stringify(data) }),
  release: (accountId) =>
    request(`/api/accounts/${accountId}/release`, { method: "POST", body: "{}" }),
  lock: (accountId, locked) =>
    request(`/api/accounts/${accountId}/lock`, {
      method: "POST",
      body: JSON.stringify({ locked }),
    }),
  guestSessions: () => request("/api/browser/guest-sessions"),
  logs: () => request("/api/logs"),
  clearLogs: () => request("/api/logs", { method: "DELETE" }),
};
