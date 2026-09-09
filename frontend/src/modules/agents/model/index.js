export const AGENT_MODEL_OPTIONS = [
  { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" }
];

export const AGENT_TOOL_OPTIONS = [
  {
    value: "list_articles",
    label: "List articles",
    description: "List available articles."
  },
  {
    value: "get_article",
    label: "Get article",
    description: "Read one article by id."
  },
  {
    value: "get_my_profile",
    label: "Get my profile",
    description: "Read the current user's profile."
  },
  {
    value: "update_my_profile",
    label: "Update my profile",
    description: "Update the current user's profile."
  },
  {
    value: "web_search",
    label: "Web Search",
    description: "Search the web, validate page relevance, and return top matching pages."
  },
  {
    value: "web_research",
    label: "Web Research",
    description: "Plan web research, verify sources, and extract structured information."
  },
  {
    value: "fetch_url_content",
    label: "Fetch URL Content",
    description: "Fetch a public URL page and extract title and visible text content."
  }
];

export const createDefaultAgentForm = () => ({
  name: "",
  description: "",
  model: "gemini-2.5-flash",
  instruction: "",
  tools: ["list_articles", "get_article"]
});

export const agentsInitialState = {
  loading: true,
  saving: false,
  sending: false,
  loadingChatAgents: true,
  error: "",
  success: "",
  items: [],
  showManageForm: false,
  selectedAgentId: "",
  availableChatAgents: [],
  chatAgents: [],
  selectedChatAgentId: "",
  chatSessions: [],
  selectedChatSessionId: "",
  chatMessage: "",
  chatMessages: [],
  form: createDefaultAgentForm()
};
