import { getConfig } from "../config";

const levels = {
  silent: 50,
  error: 40,
  warn: 30,
  info: 20,
  debug: 10
};

function getCurrentLevel() {
  const config = getConfig();
  const currentLevelName = (config.logLevel || "info").toLowerCase();
  return levels[currentLevelName] ?? levels.info;
}

function shouldLog(levelName) {
  return levels[levelName] >= getCurrentLevel();
}

export function debug(...args) {
  if (shouldLog("debug")) {
    console.debug("[frontend]", ...args);
  }
}

export function info(...args) {
  if (shouldLog("info")) {
    console.info("[frontend]", ...args);
  }
}

export function warn(...args) {
  if (shouldLog("warn")) {
    console.warn("[frontend]", ...args);
  }
}

export function error(...args) {
  if (shouldLog("error")) {
    console.error("[frontend]", ...args);
  }
}
