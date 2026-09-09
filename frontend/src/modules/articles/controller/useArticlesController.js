import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearToken } from "../../auth/service";
import { deleteArticle, fetchArticles } from "../service";
import { articlesInitialState } from "../model";
import { debug } from "../../../shared/logger";

export function useArticlesController() {
  const navigate = useNavigate();
  const [state, setState] = useState(articlesInitialState);

  async function load() {
    debug("Loading articles list");
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const items = await fetchArticles();
      debug("Loaded articles list", { count: items.length });
      setState((prev) => ({ ...prev, items }));
    } catch (err) {
      debug("Failed to load articles list", { error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
      if (err.message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function remove(articleId) {
    debug("Deleting article", { articleId });
    try {
      await deleteArticle(articleId);
      await load();
    } catch (err) {
      debug("Failed to delete article", { articleId, error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
    }
  }

  return { state, remove };
}
