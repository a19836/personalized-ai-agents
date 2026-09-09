import { Navigate } from "react-router-dom";
import { getToken } from "../modules/auth/service";

export default function ProtectedRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}
