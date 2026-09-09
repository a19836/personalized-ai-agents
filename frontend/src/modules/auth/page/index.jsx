import { useLoginController } from "../controller/useLoginController";
import LoginView from "../view/LoginView";

export default function LoginPage() {
  const { state, setEmail, setPassword, submit } = useLoginController();
  return (
    <LoginView state={state} setEmail={setEmail} setPassword={setPassword} onSubmit={submit} />
  );
}
