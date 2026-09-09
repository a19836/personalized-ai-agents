import { getAuthHeaders } from "../../auth/service";
import { request } from "../../../shared/httpClient";
import { getConfig } from "../../../config";

const getArticlesBaseUrl = () => getConfig().articlesApiBaseUrl;

export async function fetchArticles() {
  return request(`${getArticlesBaseUrl()}/articles`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function fetchArticle(articleId) {
  return request(`${getArticlesBaseUrl()}/articles/${articleId}`, {
    method: "GET",
    headers: getAuthHeaders()
  });
}

export async function saveArticle(articleId, payload) {
  return request(`${getArticlesBaseUrl()}/articles/${articleId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });
}

export async function deleteArticle(articleId) {
  return request(`${getArticlesBaseUrl()}/articles/${articleId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
}
