import { debug } from "./logger";

export async function request(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  debug(`HTTP ${method} ${url} start`);
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.detail || "Request failed";
    debug(`HTTP ${method} ${url} failed`, { status: response.status, message });
    throw new Error(typeof message === "string" ? message : "Request failed");
  }
  debug(`HTTP ${method} ${url} ok`, { status: response.status });
  return data;
}
