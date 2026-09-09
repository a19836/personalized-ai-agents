import { useEffect, useMemo, useState } from "react";
import { clearToken } from "../../auth/service";
import { createUser, deleteUser, listUsers, updateUser } from "../service";
import { validateSecurePassword } from "../model";

const initialForm = {
  uid: "",
  email: "",
  displayName: "",
  role: "",
  preferencesText: "{}"
};

const initialCreateForm = {
  email: "",
  password: "",
  displayName: "",
  role: "",
  preferencesText: "{}"
};

const initialState = {
  loading: true,
  showCreateForm: false,
  creating: false,
  saving: false,
  deleting: false,
  error: "",
  success: "",
  users: [],
  selectedUserId: "",
  form: initialForm,
  createForm: initialCreateForm
};

export function useUsersManagementController() {
  const [state, setState] = useState(initialState);

  const selectedUser = useMemo(
    () => state.users.find((item) => item.uid === state.selectedUserId) || null,
    [state.users, state.selectedUserId]
  );

  async function refresh() {
    setState((prev) => ({ ...prev, loading: true, error: "", success: "" }));
    try {
      const users = await listUsers();
      setState((prev) => ({
        ...prev,
        users,
        selectedUserId: prev.selectedUserId && users.some((u) => u.uid === prev.selectedUserId)
          ? prev.selectedUserId
          : ""
      }));
    } catch (err) {
      if ((err.message || "").toLowerCase().includes("token")) {
        clearToken();
      }
      setState((prev) => ({ ...prev, error: err.message || "Failed to load users" }));
    } finally {
      setState((prev) => ({ ...prev, loading: false }));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  function startEdit(uid) {
    const user = state.users.find((item) => item.uid === uid);
    if (!user) return;
    setState((prev) => ({
      ...prev,
      showCreateForm: false,
      createForm: initialCreateForm,
      selectedUserId: uid,
      success: "",
      error: "",
      form: {
        uid: user.uid,
        email: user.email || "",
        displayName: user.display_name || "",
        role: user.role || "",
        preferencesText: JSON.stringify(user.preferences || {}, null, 2)
      }
    }));
  }

  function setFormField(field, value) {
    setState((prev) => ({ ...prev, form: { ...prev.form, [field]: value } }));
  }

  function setCreateField(field, value) {
    setState((prev) => ({ ...prev, createForm: { ...prev.createForm, [field]: value } }));
  }

  function openCreateForm() {
    setState((prev) => ({
      ...prev,
      showCreateForm: true,
      selectedUserId: "",
      form: initialForm,
      error: "",
      success: ""
    }));
  }

  function closeCreateForm() {
    setState((prev) => ({
      ...prev,
      showCreateForm: false,
      createForm: initialCreateForm
    }));
  }

  function closeEditForm() {
    setState((prev) => ({
      ...prev,
      selectedUserId: "",
      form: initialForm
    }));
  }

  async function create() {
    setState((prev) => ({ ...prev, creating: true, error: "", success: "" }));
    const passwordError = validateSecurePassword(state.createForm.password || "");
    if (passwordError) {
      setState((prev) => ({ ...prev, creating: false, error: passwordError }));
      return;
    }
    let preferences;
    try {
      preferences = JSON.parse(state.createForm.preferencesText || "{}");
    } catch {
      setState((prev) => ({ ...prev, creating: false, error: "New user preferences must be valid JSON" }));
      return;
    }

    try {
      const created = await createUser({
        email: state.createForm.email,
        password: state.createForm.password,
        display_name: state.createForm.displayName || null,
        role: state.createForm.role || null,
        preferences
      });
      await refresh();
      setState((prev) => ({
        ...prev,
        success: "User created",
        createForm: initialCreateForm,
        showCreateForm: false
      }));
      startEdit(created.uid);
    } catch (err) {
      setState((prev) => ({ ...prev, error: err.message || "Failed to create user" }));
    } finally {
      setState((prev) => ({ ...prev, creating: false }));
    }
  }

  async function save() {
    if (!state.form.uid) return;
    setState((prev) => ({ ...prev, saving: true, error: "", success: "" }));
    let preferences;
    try {
      preferences = JSON.parse(state.form.preferencesText || "{}");
    } catch {
      setState((prev) => ({ ...prev, saving: false, error: "Preferences must be valid JSON" }));
      return;
    }

    try {
      await updateUser(state.form.uid, {
        display_name: state.form.displayName || null,
        role: state.form.role || null,
        preferences
      });
      await refresh();
      setState((prev) => ({ ...prev, success: "User updated" }));
      startEdit(state.form.uid);
    } catch (err) {
      setState((prev) => ({ ...prev, error: err.message || "Failed to update user" }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  async function removeSelected() {
    if (!state.form.uid) return;
    if (!window.confirm(`Delete user ${state.form.uid}?`)) return;
    setState((prev) => ({ ...prev, deleting: true, error: "", success: "" }));
    try {
      await deleteUser(state.form.uid);
      setState((prev) => ({
        ...prev,
        success: "User deleted",
        selectedUserId: "",
        form: initialForm
      }));
      await refresh();
    } catch (err) {
      setState((prev) => ({ ...prev, error: err.message || "Failed to delete user" }));
    } finally {
      setState((prev) => ({ ...prev, deleting: false }));
    }
  }

  return {
    state,
    selectedUser,
    refresh,
    startEdit,
    closeEditForm,
    setFormField,
    setCreateField,
    openCreateForm,
    closeCreateForm,
    create,
    save,
    removeSelected
  };
}
