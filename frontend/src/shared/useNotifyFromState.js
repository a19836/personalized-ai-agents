import { useEffect, useRef } from "react";
import { useNotifications } from "./notifications";

export function useNotifyFromState(error, success) {
  const { notifyError, notifySuccess } = useNotifications();
  const lastErrorRef = useRef("");
  const lastSuccessRef = useRef("");

  useEffect(() => {
    const text = typeof error === "string" ? error.trim() : "";
    if (!text) {
      lastErrorRef.current = "";
      return;
    }
    if (lastErrorRef.current === text) return;
    lastErrorRef.current = text;
    notifyError(text);
  }, [error, notifyError]);

  useEffect(() => {
    const text = typeof success === "string" ? success.trim() : "";
    if (!text) {
      lastSuccessRef.current = "";
      return;
    }
    if (lastSuccessRef.current === text) return;
    lastSuccessRef.current = text;
    notifySuccess(text);
  }, [success, notifySuccess]);
}

