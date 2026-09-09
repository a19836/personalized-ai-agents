import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createArticleInitialState } from "../model";
import { saveArticle } from "../service";
import { debug } from "../../../shared/logger";

function slugify(value) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function useCreateArticleController() {
  const navigate = useNavigate();
  const [state, setState] = useState(createArticleInitialState);

  async function create() {
    const finalArticleId = state.articleId.trim() || slugify(state.title);
    if (!finalArticleId) {
      setState((prev) => ({
        ...prev,
        error: "Provide an Article ID or a Title to generate one."
      }));
      return;
    }

    debug("Creating article", { articleId: finalArticleId });
    setState((prev) => ({ ...prev, saving: true, error: "" }));
    try {
      await saveArticle(finalArticleId, { title: state.title, body: state.body });
      debug("Created article", { articleId: finalArticleId });
      navigate("/articles");
    } catch (err) {
      debug("Failed to create article", { articleId: finalArticleId, error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  return {
    state,
    setArticleId: (articleId) => setState((prev) => ({ ...prev, articleId })),
    setTitle: (title) => setState((prev) => ({ ...prev, title })),
    setBody: (body) => setState((prev) => ({ ...prev, body })),
    create,
    cancel: () => navigate("/articles")
  };
}
