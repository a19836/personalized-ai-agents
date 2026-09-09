import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { debug } from "../../../shared/logger";
import { login, setToken } from "../service";
import { loginInitialState } from "../model";

export function useLoginController() {
  const navigate = useNavigate();
  const [state, setState] = useState(loginInitialState);

  async function submit() {
    debug("Submitting login", { email: state.email });
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const result = await login(state.email, state.password);
      setToken(result.id_token);
      debug("Login succeeded", { email: state.email });
      navigate("/dashboard");
    } catch (err) {
      debug("Login failed", { email: state.email, error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
    } finally {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }

  return {
    state,
    setEmail: (email) => setState((prev) => ({ ...prev, email })),
    setPassword: (password) => setState((prev) => ({ ...prev, password })),
    submit
  };
}
