import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function UsersManagementView({
  state,
  selectedUser,
  onRefresh,
  onOpenCreate,
  onCloseCreate,
  onSetCreateField,
  onCreate,
  onEdit,
  onCloseEdit,
  onSetField,
  onSave,
  onDelete
}) {
  useNotifyFromState(state.error, state.success);

  return (
    <Layout>
      <section className="card">
        <h2>Users Management</h2>
        <div className="actions">
          <button onClick={() => void onRefresh()} type="button" className="secondary" disabled={state.loading}>
            {state.loading ? "Refreshing..." : "Refresh"}
          </button>
          <button onClick={onOpenCreate} type="button">
            Add User
          </button>
        </div>
        {state.loading ? (
          <p>Loading...</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>UID</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Disabled</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {state.users.map((user) => (
                  <tr key={user.uid}>
                    <td>{user.uid}</td>
                    <td>{user.email || "-"}</td>
                    <td>{user.role || "-"}</td>
                    <td>{user.disabled ? "Yes" : "No"}</td>
                    <td>
                      <button type="button" onClick={() => onEdit(user.uid)}>
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
                {!state.users.length && (
                  <tr>
                    <td colSpan="5">No users found.</td>
                  </tr>
                )}
              </tbody>
            </table>

            {state.showCreateForm && (
              <>
                <hr />
                <form
                  className="form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void onCreate();
                  }}
                  style={{ marginTop: "1rem", marginBottom: "1rem" }}
                >
                  <h3>Create User</h3>
                  <label htmlFor="createUserEmail">Email</label>
                  <input
                    id="createUserEmail"
                    type="email"
                    value={state.createForm.email}
                    onChange={(event) => onSetCreateField("email", event.target.value)}
                    required
                  />
                  <label htmlFor="createUserPassword">Password</label>
                  <input
                    id="createUserPassword"
                    type="password"
                    value={state.createForm.password}
                    onChange={(event) => onSetCreateField("password", event.target.value)}
                    minLength={8}
                    required
                  />
                  <p className="muted">
                    Password must include at least 8 characters, uppercase, lowercase, number, and special character.
                  </p>
                  <label htmlFor="createUserDisplayName">Display Name</label>
                  <input
                    id="createUserDisplayName"
                    type="text"
                    value={state.createForm.displayName}
                    onChange={(event) => onSetCreateField("displayName", event.target.value)}
                  />
                  <label htmlFor="createUserRole">Role</label>
                  <input
                    id="createUserRole"
                    type="text"
                    value={state.createForm.role}
                    onChange={(event) => onSetCreateField("role", event.target.value)}
                  />
                  <label htmlFor="createUserPreferences">Preferences (JSON)</label>
                  <textarea
                    id="createUserPreferences"
                    rows="6"
                    value={state.createForm.preferencesText}
                    onChange={(event) => onSetCreateField("preferencesText", event.target.value)}
                  />
                  <div className="actions">
                    <button type="submit" disabled={state.creating}>
                      {state.creating ? "Creating..." : "Create User"}
                    </button>
                    <button type="button" className="secondary" onClick={onCloseCreate}>
                      Close popup
                    </button>
                  </div>
                </form>
              </>
            )}

            {selectedUser && (
              <>
                <hr />
                <form
                  className="form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void onSave();
                  }}
                  style={{ marginTop: "1rem" }}
                >
                  <h3>Edit User</h3>
                  <label htmlFor="editUserUid">UID</label>
                  <input id="editUserUid" type="text" value={state.form.uid} disabled />

                  <label htmlFor="editUserEmail">Email</label>
                  <input id="editUserEmail" type="text" value={state.form.email} disabled />

                  <label htmlFor="editUserDisplayName">Display Name</label>
                  <input
                    id="editUserDisplayName"
                    type="text"
                    value={state.form.displayName}
                    onChange={(event) => onSetField("displayName", event.target.value)}
                  />

                  <label htmlFor="editUserRole">Role</label>
                  <input
                    id="editUserRole"
                    type="text"
                    value={state.form.role}
                    onChange={(event) => onSetField("role", event.target.value)}
                  />

                  <label htmlFor="editUserPreferences">Preferences (JSON)</label>
                  <textarea
                    id="editUserPreferences"
                    rows="8"
                    value={state.form.preferencesText}
                    onChange={(event) => onSetField("preferencesText", event.target.value)}
                  />

                  <div className="actions">
                    <button type="submit" disabled={state.saving}>
                      {state.saving ? "Saving..." : "Save"}
                    </button>
                    <button type="button" className="danger" disabled={state.deleting} onClick={() => void onDelete()}>
                      {state.deleting ? "Deleting..." : "Delete User"}
                    </button>
                    <button type="button" className="secondary" onClick={onCloseEdit}>
                      Close popup
                    </button>
                  </div>
                </form>
              </>
            )}
          </>
        )}
      </section>
    </Layout>
  );
}
