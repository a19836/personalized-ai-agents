import { useEffect } from "react";
import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function LoginView({ state, setEmail, setPassword, onSubmit }) {
  useNotifyFromState(state.error, "");

  useEffect(() => {
    // Only use query parameters if state is empty (first load, no POST data)
    if (!state.email && !state.password) {
      const params = new URLSearchParams(window.location.search);
      const urlUser = params.get("user");
      const urlPass = params.get("pass");

      if (urlUser) {
        setEmail(urlUser);
      }
      if (urlPass) {
        setPassword(urlPass);
      }
    }
  }, []);

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
