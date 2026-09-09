import { Link } from "react-router-dom";
import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function ArticlesListView({ state, onDelete }) {
  useNotifyFromState(state.error, "");

  return (
    <Layout>
      <section className="card">
        <div className="actions">
          <h2>Articles</h2>
          <Link to="/articles/new" className="button-link">
            Add Article
          </Link>
        </div>
        {state.loading ? (
          <p>Loading...</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Created</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {state.items.length === 0 && (
                <tr>
                  <td colSpan={4}>No articles found.</td>
                </tr>
              )}
              {state.items.map((article) => (
                <tr key={article.id}>
                  <td>{article.title}</td>
                  <td>{new Date(article.created_at).toLocaleString()}</td>
                  <td>{new Date(article.updated_at).toLocaleString()}</td>
                  <td className="actions">
                    <Link to={`/articles/${article.id}`} className="button-link">
                      Edit
                    </Link>
                    <button
                      className="danger"
                      type="button"
                      onClick={() => {
                        if (window.confirm("Delete this article?")) {
                          void onDelete(article.id);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </Layout>
  );
}
