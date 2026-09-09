import { createContext, useCallback, useContext, useMemo, useState } from "react";

const NotificationsContext = createContext(null);
let notificationId = 0;

export function NotificationsProvider({ children }) {
  const [items, setItems] = useState([]);

  const dismiss = useCallback((id) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback((type, message, ttl = 4500) => {
    const text = typeof message === "string" ? message.trim() : "";
    if (!text) return;
    notificationId += 1;
    const id = notificationId;
    setItems((prev) => [...prev, { id, type, message: text }]);
    window.setTimeout(() => {
      dismiss(id);
    }, ttl);
  }, [dismiss]);

  const notifySuccess = useCallback((message, ttl) => notify("success", message, ttl), [notify]);
  const notifyError = useCallback((message, ttl) => notify("error", message, ttl), [notify]);

  const value = useMemo(() => ({
    items,
    dismiss,
    notifySuccess,
    notifyError
  }), [items, dismiss, notifySuccess, notifyError]);

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error("useNotifications must be used within NotificationsProvider");
  }
  return context;
}

