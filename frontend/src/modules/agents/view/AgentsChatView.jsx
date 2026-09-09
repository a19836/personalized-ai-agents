import { useEffect, useRef } from "react";
import Layout from "../../../components/Layout";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function AgentsChatView({
  state,
  onRefreshChatAgents,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
  getSessionPreview,
  onSetChatAgent,
  onSetChatMessage,
  onSendChat
}) {
  useNotifyFromState(state.error, state.success);
  const chatBoxRef = useRef(null);

  useEffect(() => {
    if (!chatBoxRef.current) return;
    chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
  }, [state.chatMessages.length, state.sending, state.selectedChatSessionId]);

  const activeSession = state.chatSessions.find((item) => item.id === state.selectedChatSessionId) || null;
  const activeSessionAgent = state.chatAgents.find((item) => item.id === activeSession?.agent_id) || null;
  const activeSessionUnavailable = Boolean(activeSession && (!activeSessionAgent || activeSessionAgent.unavailable));
  const activeAgentName = (state.chatAgents.find((item) => item.id === (activeSession || {}).agent_id) || {}).name
    || (activeSession || {}).agent_id
    || "";
  const activeSessionTitle = (activeSession || {}).title || "Session";
  const showAgentAfterTitle =
    Boolean(activeAgentName) && !String(activeSessionTitle).toLowerCase().includes(String(activeAgentName).toLowerCase());
  const formatDateTime = (value) => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "-";
    return parsed.toLocaleString([], {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  return (
    <Layout>
      <section className="card">
        <h2>Agents Chat</h2>

        <div className="actions chat-header-actions">
          <h3>Chat with an agent</h3>
          <div className="actions chat-header-actions-right">
              <button type="button" onClick={onCreateSession} disabled={state.loadingChatAgents || state.sending || !state.chatAgents.length}>
                Create New Chat
              </button>
              <select
                id="agentChatSelect"
                value={state.selectedChatAgentId}
                onChange={(event) => onSetChatAgent(event.target.value)}
                disabled={state.loadingChatAgents || state.sending}
                aria-label="Chat Agent"
              >
                {state.chatAgents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
              <button type="button" className="secondary" onClick={onRefreshChatAgents} disabled={state.loadingChatAgents || state.sending}>
                Refresh Chat Agents
              </button>
          </div>
        </div>
        <hr/>
        <div className="chat-layout">
          <aside className="chat-sessions-panel">
            <div className="actions">
              <h4>Sessions</h4>
            </div>
            <div className="chat-sessions-list">
              {state.chatSessions.length === 0 ? (
                <p className="muted">No sessions yet.</p>
              ) : (
                state.chatSessions.map((session) => (
                  <div key={session.id} className="chat-session-row">
                    <button
                      type="button"
                      className={`chat-session-item ${state.selectedChatSessionId === session.id ? "active" : ""}`}
                      onClick={() => onSelectSession(session.id)}
                      disabled={state.sending || state.loadingChatAgents}
                    >
                      <strong>{session.title || "Session"}</strong>
                      <span className="muted">{getSessionPreview(session)}</span>
                      <span className="chat-session-agent">Agent: {(state.chatAgents.find((item) => item.id === session.agent_id) || {}).name || session.agent_id}</span>
                      <span className="chat-session-count">Messages: {session.message_count ?? 0}</span>
                      <div className="chat-session-dates">
                        <span className="chat-session-date chat-session-date-created">Created {formatDateTime(session.created_at)}</span>
                        <span className="chat-session-date chat-session-date-updated">Updated {formatDateTime(session.updated_at)}</span>
                      </div>
                    </button>
                    <button
                      type="button"
                      className="chat-session-delete"
                      title="Delete session"
                      aria-label={`Delete ${session.title || "session"}`}
                      disabled={state.sending || state.loadingChatAgents}
                      onClick={() => {
                        if (window.confirm("Delete this chat session?")) {
                          void onDeleteSession(session.id);
                        }
                      }}
                    >
                      🗑
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>

          <div className="chat-main-panel">
            {state.selectedChatSessionId && (
              <p className="muted">
                Active session: {activeSessionTitle}
                {showAgentAfterTitle ? ` · ${activeAgentName}` : ""}
              </p>
            )}
            <div className="form">
              <p><strong>Selected agent:</strong> {activeSessionAgent?.name || activeSession?.agent_id || "-"}</p>
              {activeSessionAgent?.description && (
                <p className="muted">
                  {activeSessionAgent.description}
                </p>
              )}
              {activeSessionUnavailable && (
                <p className="error">This session agent is unavailable. Switch session to re-enable chat.</p>
              )}
            </div>

            <div className="chat-box" ref={chatBoxRef}>
              {state.chatMessages.length === 0 ? (
                <p className="muted">Start a conversation with an agent.</p>
              ) : (
                state.chatMessages.map((item, index) => (
                  <div key={`${item.role}-${index}`} className={`chat-message ${item.role}`}>
                    <small className="muted"><strong>{item.role === "user" ? "You" : "Agent"}:</strong></small>{" "}
                    {item.role === "assistant" ? (
                      <span
                        className="chat-message-content"
                        dangerouslySetInnerHTML={{ __html: item.text || "" }}
                      />
                    ) : (
                      <span className="chat-message-content">{item.text}</span>
                    )}
                  </div>
                ))
              )}
              {state.sending && (
                <div className="chat-loading" role="status" aria-live="polite">
                  <span className="chat-loading-spinner" aria-hidden="true" />
                  <span>Agent is thinking...</span>
                </div>
              )}
            </div>

            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault();
                void onSendChat();
              }}
            >
              <label htmlFor="chatMessage">Message</label>
              <textarea
                id="chatMessage"
                rows="4"
                value={state.chatMessage}
                onChange={(event) => onSetChatMessage(event.target.value)}
                placeholder="Ask something..."
                disabled={state.loadingChatAgents || state.sending || activeSessionUnavailable}
              />
              <div className="actions">
            <button
              type="submit"
              disabled={
                state.loadingChatAgents
                || state.sending
                || !state.selectedChatAgentId
                || activeSessionUnavailable
                || !state.chatMessage.trim()
              }
            >
              {state.sending ? "Sending..." : "Send"}
            </button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </Layout>
  );
}
