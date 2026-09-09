import Layout from "../../../components/Layout";
import { AGENT_MODEL_OPTIONS, AGENT_TOOL_OPTIONS } from "../model";
import { useNotifyFromState } from "../../../shared/useNotifyFromState";

export default function AgentsManageView({
  state,
  selectedAgent,
  setFormField,
  onSave,
  onSelectAgent,
  onDeploy,
  onDelete,
  onCreateNew,
  onCloseForm,
  onRefresh
}) {
  useNotifyFromState(state.error, state.success);

  const modelOptions = AGENT_MODEL_OPTIONS.some((item) => item.value === state.form.model)
    ? AGENT_MODEL_OPTIONS
    : [...AGENT_MODEL_OPTIONS, { value: state.form.model, label: state.form.model }];

  return (
    <Layout>
      <section className="card">
          <h2>Manage Agents</h2>
        <div className="actions">
          <button type="button" className="secondary" onClick={onRefresh} disabled={state.loading || state.saving}>
            Refresh
          </button>
          <button type="button" onClick={onCreateNew} disabled={state.saving}>
            New Agent
          </button>
        </div>

        {state.loading ? (
          <p>Loading...</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {state.items.length === 0 && (
                <tr>
                  <td colSpan={4}>No agents yet.</td>
                </tr>
              )}
              {state.items.map((agent) => (
                <tr key={agent.id}>
                  <td>{agent.name}</td>
                  <td>{agent.status}</td>
                  <td>{agent.updated_at ? new Date(agent.updated_at).toLocaleString() : "-"}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => onSelectAgent(agent.id)}
                      disabled={state.saving}
                    >
                      View/Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {state.showManageForm && (
          <>
            <hr />
            <div className="actions">
              <h3>{state.selectedAgentId ? "Edit Agent" : "Create Agent"}</h3>
            </div>
            {selectedAgent && (
              <p className="muted">
                Status:{" "}
                {selectedAgent.status === "DEPLOYING"
                  ? "Deploying..."
                  : selectedAgent.status === "READY"
                    ? "Ready"
                    : selectedAgent.status}
              </p>
            )}
            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault();
                void onSave();
              }}
            >
              <label htmlFor="agentName">Name</label>
              <input
                id="agentName"
                type="text"
                value={state.form.name}
                onChange={(event) => setFormField("name", event.target.value)}
                disabled={state.saving}
              />

              <label htmlFor="agentDescription">Description</label>
              <input
                id="agentDescription"
                type="text"
                value={state.form.description}
                onChange={(event) => setFormField("description", event.target.value)}
                disabled={state.saving}
              />

              <label htmlFor="agentModel">Model</label>
              <select
                id="agentModel"
                value={state.form.model}
                onChange={(event) => setFormField("model", event.target.value)}
                disabled={state.saving}
              >
                {modelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <label htmlFor="agentInstruction">Instruction</label>
              <textarea
                id="agentInstruction"
                rows="4"
                value={state.form.instruction}
                onChange={(event) => setFormField("instruction", event.target.value)}
                disabled={state.saving}
              />

              <fieldset className="tools-fieldset">
                <legend>Tools</legend>
                <div className="tools-list">
                  {AGENT_TOOL_OPTIONS.map((tool) => (
                    <label key={tool.value} className="tools-item">
                      <input
                        type="checkbox"
                        checked={(state.form.tools || []).includes(tool.value)}
                        onChange={() => setFormField("tools", (state.form.tools || []).includes(tool.value)
                          ? (state.form.tools || []).filter((item) => item !== tool.value)
                          : [...(state.form.tools || []), tool.value])}
                        disabled={state.saving}
                      />
                      <span>
                        <strong>{tool.label}</strong>
                        <span className="muted"> — {tool.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="actions">
                <button type="submit" disabled={state.saving}>
                  {state.saving ? "Saving..." : state.selectedAgentId ? "Save Agent" : "Create Agent"}
                </button>
                {state.selectedAgentId && (
                  <>
                    <button type="button" className="secondary" onClick={onDeploy} disabled={state.saving}>
                      Deploy
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        if (window.confirm("Delete this agent?")) {
                          void onDelete();
                        }
                      }}
                      disabled={state.saving}
                    >
                      Delete
                    </button>
                  </>
                )}
              <button type="button" className="secondary" onClick={onCloseForm} disabled={state.saving}>
                Close Popup
              </button>
              </div>
            </form>
          </>
        )}
      </section>
    </Layout>
  );
}
