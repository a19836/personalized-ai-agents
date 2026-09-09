import { request } from "../../../shared/httpClient";
import { debug } from "../../../shared/logger";
import { getConfig } from "../../../config";

const getAuthBaseUrl = () => getConfig().authApiBaseUrl;

export function getToken() {
  return localStorage.getItem("id_token");
}

export function setToken(token) {
  localStorage.setItem("id_token", token);
}

export function clearToken() {
  localStorage.removeItem("id_token");
}

export function getAuthHeaders() {
  const token = getToken();
  if (!token) {
    throw new Error("Missing authentication token");
  }
  debug("Using auth token", {
    preview: token.length > 20 ? `${token.slice(0, 12)}...${token.slice(-8)}` : token,
    length: token.length
  });
  return { Authorization: `Bearer ${token}` };
}

export async function login(email, password) {
  return request(`${getAuthBaseUrl()}/login`, {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function logout() {
  return request(`${getAuthBaseUrl()}/logout`, { method: "POST" });
}
