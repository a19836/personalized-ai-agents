import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";
import { validateConfig } from "./config";
import { NotificationsProvider } from "./shared/notifications";

// Initialize app with config (from Secret Manager on Cloud Run, or .env locally)
async function initApp() {
  // Give config.js time to load (created by entrypoint.sh on Cloud Run)
  if (!window.APP_CONFIG) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  // Validate config is available
  validateConfig();
}

// Start app
initApp().then(() => {
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <NotificationsProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </NotificationsProvider>
    </React.StrictMode>
  );
});
