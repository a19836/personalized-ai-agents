import { getAuthHeaders } from "../../auth/service";
import { request } from "../../../shared/httpClient";
import { getConfig } from "../../../config";

const getUsersBaseUrl = () => getConfig().usersApiBaseUrl;

export async function fetchCurrentUser() {
  return request(`${getUsersBaseUrl()}/me`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function updateCurrentUser(payload) {
  return request(`${getUsersBaseUrl()}/me`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function updatePassword(newPassword) {
  return request(`${getUsersBaseUrl()}/me/password`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ new_password: newPassword })
  });
}

export async function listUsers() {
  return request(`${getUsersBaseUrl()}/users`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function createUser(payload) {
  return request(`${getUsersBaseUrl()}/users`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function updateUser(uid, payload) {
  return request(`${getUsersBaseUrl()}/users/${uid}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function deleteUser(uid) {
  return request(`${getUsersBaseUrl()}/users/${uid}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
}
