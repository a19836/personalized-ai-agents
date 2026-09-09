import { useAgentsController } from "../controller/useAgentsController";
import AgentsChatView from "../view/AgentsChatView";
import AgentsManageView from "../view/AgentsManageView";

export function AgentsManagePage() {
  const {
    state,
    selectedAgent,
    setFormField,
    save,
    selectAgent,
    deploySelected,
    deleteSelected,
    openCreateForm,
    resetForm,
    refresh
  } = useAgentsController({ mode: "manage" });

  return (
    <AgentsManageView
      state={state}
      selectedAgent={selectedAgent}
      setFormField={setFormField}
      onSave={save}
      onSelectAgent={selectAgent}
      onDeploy={deploySelected}
      onDelete={deleteSelected}
      onCreateNew={openCreateForm}
      onCloseForm={resetForm}
      onRefresh={refresh}
    />
  );
}

export function AgentsChatPage() {
  const {
    state,
    refreshChatAgents,
    setChatMessage,
    setSelectedChatAgentId,
    sendChatMessage,
    createChatSession,
    selectChatSession,
    deleteChatSession,
    sessionPreview
  } = useAgentsController({ mode: "chat" });

  return (
    <AgentsChatView
      state={state}
      onRefreshChatAgents={refreshChatAgents}
      onSetChatAgent={setSelectedChatAgentId}
      onSetChatMessage={setChatMessage}
      onSendChat={sendChatMessage}
      onCreateSession={createChatSession}
      onSelectSession={selectChatSession}
      onDeleteSession={deleteChatSession}
      getSessionPreview={sessionPreview}
    />
  );
}

export default AgentsManagePage;
