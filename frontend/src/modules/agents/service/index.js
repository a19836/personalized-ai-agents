import { getConfig } from "../../../config";
import { request } from "../../../shared/httpClient";
import { getAuthHeaders } from "../../auth/service";

const getAgentsBaseUrl = () => {
  const baseUrl = getConfig().agentsApiBaseUrl;
  if (!baseUrl) {
    throw new Error("Missing VITE_AGENTS_API_BASE_URL");
  }
  return baseUrl;
};

export async function fetchAvailableAgents() {
  return request(`${getAgentsBaseUrl()}/agents/available`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function chatWithAgent(payload) {
  return request(`${getAgentsBaseUrl()}/agents/chat`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function fetchChatSessions() {
  return request(`${getAgentsBaseUrl()}/agents/chat/sessions`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function fetchChatSession(chatId) {
  return request(`${getAgentsBaseUrl()}/agents/chat/sessions/${chatId}`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function deleteChatSession(chatId) {
  return request(`${getAgentsBaseUrl()}/agents/chat/sessions/${chatId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
}

export async function createChatSession(payload) {
  return request(`${getAgentsBaseUrl()}/agents/chat/sessions`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function fetchAgents() {
  return request(`${getAgentsBaseUrl()}/agents`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function createAgent(payload) {
  return request(`${getAgentsBaseUrl()}/agents`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function fetchAgent(agentId) {
  return request(`${getAgentsBaseUrl()}/agents/${agentId}`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function updateAgent(agentId, payload) {
  return request(`${getAgentsBaseUrl()}/agents/${agentId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function deployAgent(agentId) {
  return request(`${getAgentsBaseUrl()}/agents/${agentId}/deploy`, {
    method: "POST",
    headers: getAuthHeaders()
  });
}

export async function deleteAgent(agentId) {
  return request(`${getAgentsBaseUrl()}/agents/${agentId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
}
