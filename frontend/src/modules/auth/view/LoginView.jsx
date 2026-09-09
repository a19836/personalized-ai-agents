import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function LoginView({ state, setEmail, setPassword, onSubmit }) {
  useNotifyFromState(state.error, "");

  return (
    <Layout>
      <section className="card narrow">
        <h2>Login</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit();
          }}
          className="form"
        >
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={state.email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={state.password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <button disabled={state.loading} type="submit">
            {state.loading ? "Signing in..." : "Login"}
          </button>
        </form>
      </section>
    </Layout>
  );
}
