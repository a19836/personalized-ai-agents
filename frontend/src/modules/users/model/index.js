export const profileInitialState = {
  loading: true,
  saving: false,
  error: "",
  success: "",
  profile: null,
  displayName: "",
  role: "",
  preferencesText: "{}",
  newPassword: "",
  confirmPassword: ""
};

export function validateSecurePassword(password) {
  const checks = [
    { ok: password.length >= 8, message: "at least 8 characters" },
    { ok: /[A-Z]/.test(password), message: "one uppercase letter" },
    { ok: /[a-z]/.test(password), message: "one lowercase letter" },
    { ok: /[0-9]/.test(password), message: "one number" },
    { ok: /[^A-Za-z0-9]/.test(password), message: "one special character" }
  ];
  const missing = checks.filter((item) => !item.ok).map((item) => item.message);
  if (!missing.length) {
    return "";
  }
  return `Password must include ${missing.join(", ")}.`;
}
