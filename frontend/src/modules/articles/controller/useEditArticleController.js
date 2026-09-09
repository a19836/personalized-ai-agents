import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchArticle, saveArticle } from "../service";
import { editArticleInitialState } from "../model";
import { debug } from "../../../shared/logger";

export function useEditArticleController() {
  const navigate = useNavigate();
  const { articleId } = useParams();
  const [state, setState] = useState(editArticleInitialState);

  useEffect(() => {
    async function loadArticle() {
      if (!articleId) {
        return;
      }
      debug("Loading article for edit", { articleId });
      setState((prev) => ({ ...prev, loading: true, error: "" }));
      try {
        const article = await fetchArticle(articleId);
        debug("Loaded article for edit", { articleId });
        setState((prev) => ({
          ...prev,
          title: article.title,
          body: article.body
        }));
      } catch (err) {
        debug("Failed to load article for edit", { articleId, error: err.message });
        setState((prev) => ({ ...prev, error: err.message }));
      } finally {
        setState((prev) => ({ ...prev, loading: false }));
      }
    }
    void loadArticle();
  }, [articleId]);

  async function save() {
    if (!articleId) {
      return;
    }
    debug("Saving article", { articleId });
    setState((prev) => ({ ...prev, saving: true, error: "" }));
    try {
      await saveArticle(articleId, { title: state.title, body: state.body });
      debug("Saved article", { articleId });
      navigate("/articles");
    } catch (err) {
      debug("Failed to save article", { articleId, error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  return {
    state,
    setTitle: (title) => setState((prev) => ({ ...prev, title })),
    setBody: (body) => setState((prev) => ({ ...prev, body })),
    save,
    cancel: () => navigate("/articles")
  };
}
