import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearToken } from "../../auth/service";
import { AGENT_TOOL_OPTIONS, agentsInitialState, createDefaultAgentForm } from "../model";
import {
  chatWithAgent,
  createAgent,
  createChatSession as createChatSessionApi,
  deleteChatSession as deleteChatSessionApi,
  deleteAgent,
  deployAgent,
  fetchAgents,
  fetchAvailableAgents,
  fetchChatSession,
  fetchChatSessions,
  updateAgent
} from "../service";

const allowedTools = new Set(AGENT_TOOL_OPTIONS.map((item) => item.value));
const toolGroups = {
  articles: ["list_articles", "get_article"],
  users: ["get_my_profile", "update_my_profile"],
  web: ["web_search"],
  research: ["web_research"]
};

const normalizeTools = (tools = []) => {
  const expanded = tools.flatMap((item) => toolGroups[item] || [item]);
  return expanded.filter((item) => allowedTools.has(item));
};

const mergeChatAgentsWithSessionAgents = (chatAgents) => (Array.isArray(chatAgents) ? chatAgents : []);

const pickValidAgentId = (chatAgents, preferredAgentId) => {
  if (preferredAgentId && chatAgents.some((item) => item.id === preferredAgentId)) {
    return preferredAgentId;
  }
  return chatAgents[0]?.id || "";
};

const mapChatMessages = (messages) =>
  (Array.isArray(messages) ? messages : []).map((item) => ({
    role: item.role,
    text: item.text,
    agentId: item.agent_id
  }));

const sessionPreview = (session) => {
  if (session?.last_message_preview) return String(session.last_message_preview).slice(0, 60);
  return "No messages yet";
};

const AGENT_STATUS_POLL_MS = 10000;

export function useAgentsController({ mode = "manage" } = {}) {
  const navigate = useNavigate();
  const [state, setState] = useState(() => ({ ...agentsInitialState }));
  const isManageMode = mode === "manage";
  const isChatMode = mode === "chat";

  const selectedAgent = useMemo(
    () => state.items.find((item) => item.id === state.selectedAgentId) || null,
    [state.items, state.selectedAgentId]
  );

  async function load({ silent = false } = {}) {
    if (!silent) {
      setState((prev) => ({ ...prev, loading: true, error: "" }));
    }
    try {
      const items = await fetchAgents();
      setState((prev) => {
        const selectedAgentId = items.some((item) => item.id === prev.selectedAgentId)
          ? prev.selectedAgentId
          : "";
        const creatingNewAgent = prev.showManageForm && !prev.selectedAgentId;
        const shouldKeepManageForm = creatingNewAgent || (selectedAgentId ? prev.showManageForm : false);
        const selectedAgentChanged = selectedAgentId !== prev.selectedAgentId;
        const nextSelectedAgent = items.find((item) => item.id === selectedAgentId);
        const nextForm =
          shouldKeepManageForm && selectedAgentChanged && nextSelectedAgent
            ? {
                name: nextSelectedAgent.name || "",
                description: nextSelectedAgent.description || "",
                model: nextSelectedAgent.model || "gemini-2.5-flash",
                instruction: nextSelectedAgent.instruction || "",
                tools: normalizeTools(nextSelectedAgent.tools || [])
              }
            : prev.form;
        return {
          ...prev,
          items,
          selectedAgentId,
          showManageForm: shouldKeepManageForm,
          form: nextForm
        };
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load agents";
      if (!silent) {
        setState((prev) => ({ ...prev, error: message }));
      }
      if (message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      if (!silent) {
        setState((prev) => ({ ...prev, loading: false }));
      }
    }
  }

  async function loadChatAgents() {
    const currentSelectedSessionId = state.selectedChatSessionId;
    const currentSelectedAgentId = state.selectedChatAgentId;
    setState((prev) => ({ ...prev, loadingChatAgents: true, error: "" }));
    try {
      const [availableResult, sessionsResult] = await Promise.allSettled([fetchAvailableAgents(), fetchChatSessions()]);

      const availableAgents = availableResult.status === "fulfilled" ? availableResult.value.agents || [] : [];
      const sessions = sessionsResult.status === "fulfilled" ? sessionsResult.value || [] : [];
      const availableChatAgents = mergeChatAgentsWithSessionAgents(availableAgents, sessions);
      const chatAgents = availableChatAgents;

      if (!chatAgents.length && availableResult.status === "rejected" && sessionsResult.status === "rejected") {
        throw new Error("Failed to load chat agents and sessions");
      }

      const selectedChatSessionId =
        sessions.some((item) => item.id === currentSelectedSessionId)
          ? currentSelectedSessionId
          : sessions[0]?.id || "";

      const selectedChatAgentId = pickValidAgentId(chatAgents, currentSelectedAgentId);
      let chatMessages = [];
      if (selectedChatSessionId) {
        try {
          const detail = await fetchChatSession(selectedChatSessionId);
          chatMessages = mapChatMessages(detail.messages);
        } catch {
          chatMessages = [];
        }
      }

      setState((prev) => ({
        ...prev,
        availableChatAgents,
        chatAgents,
        chatSessions: sessions,
        selectedChatSessionId,
        selectedChatAgentId,
        chatMessages
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load chat sessions";
      setState((prev) => ({ ...prev, error: message }));
      if (message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, loadingChatAgents: false }));
    }
  }

  useEffect(() => {
    if (isManageMode) {
      void load();
    }
    if (isChatMode) {
      void loadChatAgents();
    }
  }, [isManageMode, isChatMode]);

  useEffect(() => {
    if (!isManageMode) return undefined;

    const pollIntervalId = window.setInterval(() => {
      void load({ silent: true });
    }, AGENT_STATUS_POLL_MS);

    return () => window.clearInterval(pollIntervalId);
  }, [isManageMode]);

  function setFormField(field, value) {
    setState((prev) => ({ ...prev, form: { ...prev.form, [field]: value } }));
  }

  function selectAgent(agentId) {
    const item = state.items.find((agent) => agent.id === agentId);
    setState((prev) => ({
      ...prev,
      showManageForm: true,
      selectedAgentId: agentId,
      success: "",
      error: "",
      form: item
        ? {
            name: item.name || "",
            description: item.description || "",
            model: item.model || "gemini-2.5-flash",
            instruction: item.instruction || "",
            tools: normalizeTools(item.tools || [])
          }
        : createDefaultAgentForm()
    }));
  }

  function resetForm() {
    setState((prev) => ({
      ...prev,
      showManageForm: false,
      selectedAgentId: "",
      form: createDefaultAgentForm(),
      success: "",
      error: ""
    }));
  }

  function openCreateForm() {
    setState((prev) => ({
      ...prev,
      showManageForm: true,
      selectedAgentId: "",
      form: createDefaultAgentForm(),
      success: "",
      error: ""
    }));
  }

  function setChatMessage(chatMessage) {
    setState((prev) => ({ ...prev, chatMessage }));
  }

  function setSelectedChatAgentId(selectedChatAgentId) {
    setState((prev) => {
      const nextAgentId = pickValidAgentId(prev.chatAgents, selectedChatAgentId);
      return {
        ...prev,
        selectedChatAgentId: nextAgentId
      };
    });
  }

  async function createChatSession() {
    const baseAgentId = state.selectedChatAgentId || state.chatAgents[0]?.id;
    if (!baseAgentId) return;

    setState((prev) => ({ ...prev, loadingChatAgents: true, error: "", success: "" }));
    try {
      const created = await createChatSessionApi({ agent_id: baseAgentId });
      const [availableResult, sessions] = await Promise.all([fetchAvailableAgents(), fetchChatSessions()]);
      const availableChatAgents = mergeChatAgentsWithSessionAgents(availableResult.agents || [], sessions || []);
      const chatAgents = availableChatAgents;
      setState((prev) => ({
        ...prev,
        availableChatAgents,
        chatAgents,
        chatSessions: sessions || [],
        selectedChatSessionId: created.id,
        selectedChatAgentId: pickValidAgentId(chatAgents, created.agent_id || baseAgentId),
        chatMessages: [],
        chatMessage: ""
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create chat session";
      setState((prev) => ({ ...prev, error: message }));
      if (message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, loadingChatAgents: false }));
    }
  }

  async function selectChatSession(sessionId) {
    setState((prev) => ({ ...prev, loadingChatAgents: true, error: "" }));
    try {
      const detail = await fetchChatSession(sessionId);
      setState((prev) => {
        const chatAgents = prev.availableChatAgents;
        return {
          ...prev,
          chatAgents,
          selectedChatSessionId: detail.id,
          selectedChatAgentId: pickValidAgentId(chatAgents, prev.selectedChatAgentId),
          chatMessages: mapChatMessages(detail.messages),
          chatMessage: prev.chatMessage
        };
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load chat session";
      setState((prev) => ({ ...prev, error: message }));
      if (message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, loadingChatAgents: false }));
    }
  }

  async function deleteChatSession(sessionId) {
    if (!sessionId) return;
    setState((prev) => ({ ...prev, loadingChatAgents: true, error: "", success: "" }));
    try {
      await deleteChatSessionApi(sessionId);
      const [availableResult, sessionsResult] = await Promise.all([fetchAvailableAgents(), fetchChatSessions()]);
      const sessions = sessionsResult || [];
      const availableChatAgents = mergeChatAgentsWithSessionAgents(availableResult.agents || [], sessions);
      const chatAgents = availableChatAgents;
      const selectedChatSessionId =
        state.selectedChatSessionId === sessionId
          ? sessions[0]?.id || ""
          : sessions.some((item) => item.id === state.selectedChatSessionId)
            ? state.selectedChatSessionId
            : sessions[0]?.id || "";

      const selectedChatAgentId = pickValidAgentId(chatAgents, state.selectedChatAgentId);
      let chatMessages = [];
      if (selectedChatSessionId) {
        const detail = await fetchChatSession(selectedChatSessionId);
        chatMessages = mapChatMessages(detail.messages);
      }

      setState((prev) => ({
        ...prev,
        success: "Chat session deleted.",
        availableChatAgents,
        chatAgents,
        chatSessions: sessions,
        selectedChatSessionId,
        selectedChatAgentId,
        chatMessages,
        chatMessage: ""
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete chat session";
      setState((prev) => ({ ...prev, error: message }));
      if (message.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, loadingChatAgents: false }));
    }
  }

  async function save() {
    const payload = {
      name: state.form.name.trim(),
      description: state.form.description.trim(),
      model: state.form.model.trim(),
      instruction: state.form.instruction.trim(),
      tools: normalizeTools(state.form.tools || [])
    };
    if (!payload.name || !payload.description || !payload.model || !payload.instruction || payload.tools.length === 0) {
      setState((prev) => ({ ...prev, error: "Name, description, model, instruction and tools are required." }));
      return;
    }

    setState((prev) => ({ ...prev, saving: true, error: "", success: "" }));
    try {
      if (state.selectedAgentId) {
        await updateAgent(state.selectedAgentId, payload);
        setState((prev) => ({ ...prev, success: "Agent updated." }));
      } else {
        const created = await createAgent(payload);
        setState((prev) => ({ ...prev, showManageForm: true, selectedAgentId: created.id, success: "Agent created." }));
      }
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save agent";
      setState((prev) => ({ ...prev, error: message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  async function deploySelected() {
    if (!state.selectedAgentId) return;
    setState((prev) => ({ ...prev, saving: true, error: "", success: "" }));
    try {
      await deployAgent(state.selectedAgentId);
      setState((prev) => ({ ...prev, success: "Deployment started." }));
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to deploy agent";
      setState((prev) => ({ ...prev, error: message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  async function deleteSelected() {
    if (!state.selectedAgentId) return;
    setState((prev) => ({ ...prev, saving: true, error: "", success: "" }));
    try {
      await deleteAgent(state.selectedAgentId);
      setState((prev) => ({ ...prev, success: "Delete started." }));
      resetForm();
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete agent";
      setState((prev) => ({ ...prev, error: message }));
    } finally {
      setState((prev) => ({ ...prev, saving: false }));
    }
  }

  async function sendChatMessage() {
    const message = state.chatMessage.trim();
    if (!message) return;

    let sessionId = state.selectedChatSessionId;
    const activeSession = state.chatSessions.find((item) => item.id === sessionId) || null;
    let selectedAgentId = state.selectedChatAgentId || state.chatAgents[0]?.id || "";
    if (activeSession?.agent_id) {
      selectedAgentId = activeSession.agent_id;
    }
    if (!selectedAgentId) return;

    if (!sessionId) {
      const created = await createChatSessionApi({ agent_id: selectedAgentId });
      sessionId = created.id;
      selectedAgentId = created.agent_id || selectedAgentId;
      const sessions = await fetchChatSessions();
      setState((prev) => ({
        ...prev,
        chatSessions: sessions || [],
        selectedChatSessionId: created.id,
        selectedChatAgentId: pickValidAgentId(prev.chatAgents, selectedAgentId)
      }));
    }

    setState((prev) => ({
      ...prev,
      sending: true,
      error: "",
      chatMessage: "",
      chatMessages: [...prev.chatMessages, { role: "user", text: message, agentId: selectedAgentId }]
    }));

    try {
      const result = await chatWithAgent({
        agent_id: selectedAgentId,
        message,
        session_id: sessionId
      });
      const [detail, sessions] = await Promise.all([
        fetchChatSession(result.session_id || sessionId),
        fetchChatSessions()
      ]);
      setState((prev) => ({
        ...prev,
        chatSessions: sessions || [],
        selectedChatSessionId: detail.id,
        chatMessages: mapChatMessages(detail.messages)
      }));
    } catch (err) {
      const messageText = err instanceof Error ? err.message : "Agent chat failed";
      setState((prev) => ({ ...prev, error: messageText }));
      if (messageText.toLowerCase().includes("token")) {
        clearToken();
        navigate("/login");
      }
    } finally {
      setState((prev) => ({ ...prev, sending: false }));
    }
  }

  return {
    state,
    selectedAgent,
    setFormField,
    save,
    selectAgent,
    deploySelected,
    deleteSelected,
    openCreateForm,
    resetForm,
    refresh: load,
    refreshChatAgents: loadChatAgents,
    setChatMessage,
    setSelectedChatAgentId,
    sendChatMessage,
    createChatSession,
    selectChatSession,
    deleteChatSession,
    sessionPreview
  };
}
