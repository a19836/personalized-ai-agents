// Config module that reads from runtime (Secret Manager) or build-time (.env)
// Priority: runtime config (window.APP_CONFIG) > build-time env vars

export const getConfig = () => {
  // Use runtime config from Secret Manager if available (Cloud Run)
  if (window.APP_CONFIG) {
    return {
      authApiBaseUrl: window.APP_CONFIG.VITE_AUTH_API_BASE_URL,
      articlesApiBaseUrl: window.APP_CONFIG.VITE_ARTICLES_API_BASE_URL,
      usersApiBaseUrl: window.APP_CONFIG.VITE_USERS_API_BASE_URL,
      agentsApiBaseUrl: window.APP_CONFIG.VITE_AGENTS_API_BASE_URL,
      logLevel: window.APP_CONFIG.VITE_LOG_LEVEL || 'info',
      source: 'Secret Manager (runtime)',
    };
  }

  // Fall back to build-time env vars (local development)
  return {
    authApiBaseUrl: import.meta.env.VITE_AUTH_API_BASE_URL,
    articlesApiBaseUrl: import.meta.env.VITE_ARTICLES_API_BASE_URL,
    usersApiBaseUrl: import.meta.env.VITE_USERS_API_BASE_URL,
    agentsApiBaseUrl: import.meta.env.VITE_AGENTS_API_BASE_URL,
    logLevel: import.meta.env.VITE_LOG_LEVEL || 'info',
    source: '.env (build-time)',
  };
};

// Validate that all required vars exist
export const validateConfig = () => {
  const config = getConfig();
  const required = ['authApiBaseUrl', 'articlesApiBaseUrl', 'usersApiBaseUrl', 'agentsApiBaseUrl'];
  const missing = required.filter(key => !config[key]);

  if (missing.length > 0) {
    console.error('Missing required config:', missing);
    console.error('Config source:', config.source);
    return false;
  }

  console.log('✓ Config loaded from', config.source);
  console.log('  Auth API:', config.authApiBaseUrl);
  console.log('  Articles API:', config.articlesApiBaseUrl);
  console.log('  Users API:', config.usersApiBaseUrl);
  console.log('  Agents API:', config.agentsApiBaseUrl || '(not set)');

  return true;
};

// Export as default for easy access
export default getConfig();
