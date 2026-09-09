import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function EditArticleView({ state, setTitle, setBody, onSave, onCancel }) {
  useNotifyFromState(state.error, "");

  return (
    <Layout>
      <section className="card">
        <h2>Edit Article</h2>
        {state.loading ? (
          <p>Loading...</p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void onSave();
            }}
            className="form"
          >
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
                {state.saving ? "Saving..." : "Save"}
              </button>
              <button className="secondary" type="button" onClick={onCancel}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>
    </Layout>
  );
}
