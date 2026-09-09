import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function CreateArticleView({
  state,
  setArticleId,
  setTitle,
  setBody,
  onCreate,
  onCancel
}) {
  useNotifyFromState(state.error, "");

  return (
    <Layout>
      <section className="card">
        <h2>Create Article</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void onCreate();
          }}
          className="form"
        >
          <label htmlFor="articleId">Article ID (optional)</label>
          <input
            id="articleId"
            type="text"
            value={state.articleId}
            onChange={(event) => setArticleId(event.target.value)}
            placeholder="my-first-article"
          />
          <label htmlFor="title">Title</label>
          <input
            id="title"
            type="text"
            value={state.title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
          <label htmlFor="body">Body</label>
          <textarea
            id="body"
            rows="12"
            value={state.body}
            onChange={(event) => setBody(event.target.value)}
            required
          />
          <div className="actions">
            <button disabled={state.saving} type="submit">
              {state.saving ? "Creating..." : "Create"}
            </button>
            <button className="secondary" type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>
      </section>
    </Layout>
  );
}
