import { useProfileController } from "../controller/useProfileController";
import { useUsersManagementController } from "../controller/useUsersManagementController";
import ProfileView from "../view/ProfileView";
import UsersManagementView from "../view/UsersManagementView";

export function ProfilePage() {
  const {
    state,
    setDisplayName,
    setRole,
    setPreferencesText,
    setNewPassword,
    setConfirmPassword,
    saveProfile
  } = useProfileController();

  return (
    <ProfileView
      state={state}
      setDisplayName={setDisplayName}
      setRole={setRole}
      setPreferencesText={setPreferencesText}
      setNewPassword={setNewPassword}
      setConfirmPassword={setConfirmPassword}
      onSave={saveProfile}
    />
  );
}

export function UsersManagementPage() {
  const {
    state,
    selectedUser,
    refresh,
    openCreateForm,
    closeCreateForm,
    startEdit,
    closeEditForm,
    setFormField,
    setCreateField,
    create,
    save,
    removeSelected
  } =
    useUsersManagementController();

  return (
    <UsersManagementView
      state={state}
      selectedUser={selectedUser}
      onRefresh={refresh}
      onOpenCreate={openCreateForm}
      onCloseCreate={closeCreateForm}
      onSetCreateField={setCreateField}
      onCreate={create}
      onEdit={startEdit}
      onCloseEdit={closeEditForm}
      onSetField={setFormField}
      onSave={save}
      onDelete={removeSelected}
    />
  );
}

export default ProfilePage;
