import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearToken } from "../../auth/service";
import { fetchCurrentUser, updateCurrentUser, updatePassword } from "../service";
import { profileInitialState, validateSecurePassword } from "../model";
import { debug } from "../../../shared/logger";

export function useProfileController() {
  const navigate = useNavigate();
  const [state, setState] = useState(profileInitialState);

  useEffect(() => {
    async function loadProfile() {
      debug("Loading user profile");
      setState((prev) => ({ ...prev, loading: true, error: "" }));
      try {
        const data = await fetchCurrentUser();
        debug("Loaded user profile", { uid: data.uid });
        setState((prev) => ({
          ...prev,
          profile: data,
          displayName: data.display_name || "",
          role: data.role || "",
          preferencesText: JSON.stringify(data.preferences || {}, null, 2)
        }));
      } catch (err) {
        debug("Failed to load user profile", { error: err.message });
        setState((prev) => ({ ...prev, error: err.message }));
        if (err.message.toLowerCase().includes("token")) {
          clearToken();
          navigate("/login");
        }
      } finally {
        setState((prev) => ({ ...prev, loading: false }));
      }
    }

    void loadProfile();
  }, []);

  async function saveProfile() {
    debug("Saving user profile");
    setState((prev) => ({ ...prev, saving: true, error: "", success: "" }));

    const newPassword = state.newPassword || "";
    const confirmPassword = state.confirmPassword || "";
    if (newPassword || confirmPassword) {
      if (!newPassword) {
        setState((prev) => ({ ...prev, error: "New password is required", saving: false }));
        return;
      }
      if (newPassword !== confirmPassword) {
        setState((prev) => ({ ...prev, error: "Password confirmation does not match", saving: false }));
        return;
      }
      const passwordError = validateSecurePassword(newPassword);
      if (passwordError) {
        setState((prev) => ({ ...prev, error: passwordError, saving: false }));
        return;
      }
    }

    let preferencesPayload;
    try {
      preferencesPayload = JSON.parse(state.preferencesText || "{}");
    } catch {
      setState((prev) => ({ ...prev, error: "Preferences must be valid JSON", saving: false }));
      return;
    }

    try {
      const updated = await updateCurrentUser({
        display_name: state.displayName || null,
        role: state.role || null,
        preferences: preferencesPayload
      });
      let success = "Profile updated";
      if (newPassword) {
        await updatePassword(newPassword);
        success = "Profile and password updated";
      }
      debug("Saved user profile", { uid: updated.uid });
      setState((prev) => ({
        ...prev,
        profile: updated,
        success,
        newPassword: "",
        confirmPassword: ""
      }));
    } catch (err) {
      debug("Failed to save user profile", { error: err.message });
      setState((prev) => ({ ...prev, error: err.message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  return {
    state,
    setDisplayName: (displayName) => setState((prev) => ({ ...prev, displayName })),
    setRole: (role) => setState((prev) => ({ ...prev, role })),
    setPreferencesText: (preferencesText) => setState((prev) => ({ ...prev, preferencesText })),
    setNewPassword: (newPassword) => setState((prev) => ({ ...prev, newPassword })),
    setConfirmPassword: (confirmPassword) => setState((prev) => ({ ...prev, confirmPassword })),
    saveProfile
  };
}
