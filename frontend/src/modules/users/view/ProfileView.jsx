import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function ProfileView({
  state,
  setDisplayName,
  setRole,
  setPreferencesText,
  setNewPassword,
  setConfirmPassword,
  onSave
}) {
  useNotifyFromState(state.error, state.success);

  return (
    <Layout>
      <section className="card">
        <h2>User Profile</h2>
        {state.loading ? (
          <p>Loading...</p>
        ) : (
          <>
            <div className="profile-box">
              <p>
                <strong>UID:</strong> {state.profile?.uid}
              </p>
              <p>
                <strong>Email:</strong> {state.profile?.email || "-"}
              </p>
              <p>
                <strong>Created At:</strong>{" "}
                {state.profile?.created_at
                  ? new Date(state.profile.created_at).toLocaleString()
                  : "-"}
              </p>
              <p>
                <strong>Updated At:</strong>{" "}
                {state.profile?.updated_at
                  ? new Date(state.profile.updated_at).toLocaleString()
                  : "-"}
              </p>
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void onSave();
              }}
              className="form"
            >
              <label htmlFor="displayName">Display Name</label>
              <input
                id="displayName"
                type="text"
                value={state.displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
              <label htmlFor="role">Role</label>
              <input
                id="role"
                type="text"
                value={state.role}
                onChange={(event) => setRole(event.target.value)}
              />
              <label htmlFor="preferences">Preferences (JSON)</label>
              <textarea
                id="preferences"
                rows="8"
                value={state.preferencesText}
                onChange={(event) => setPreferencesText(event.target.value)}
              />
              <label htmlFor="newPassword">New Password</label>
              <input
                id="newPassword"
                type="password"
                value={state.newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
              />
              <p className="muted">
                Password must include at least 8 characters, uppercase, lowercase, number, and special character.
              </p>
              <label htmlFor="confirmPassword">Confirm New Password</label>
              <input
                id="confirmPassword"
                type="password"
                value={state.confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
              />
              <div className="actions">
                <button disabled={state.saving} type="submit">
                  {state.saving ? "Saving..." : "Update User"}
                </button>
              </div>
            </form>
          </>
        )}
      </section>
    </Layout>
  );
}
