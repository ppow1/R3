/*
R3 CONTROLLED SOURCE
File: web/browser-preferences.js
Component: R3A-WEBSITE-BROWSER-PREFERENCES
File Revision: 1.0.0
Purpose: Keep non-sensitive presentation preferences usable when browser storage is denied.
Execution Model: Same-origin classic script; session-memory fallback only.
Observability: Exposes whether durable browser storage is currently available.
Dependencies: Browser localStorage API.
Authority: Issue #51 Website usability regression correction.
Tests: tests/test_browser_preferences.mjs
Security: This store is for UI preferences only; never use for credentials, sessions, or institutional records.
*/
(() => {
  const memory = new Map();
  let storage = null;
  let durable = false;
  try {
    storage = window.localStorage;
    durable = Boolean(storage);
  } catch {
    // Storage access is optional for presentation-only preferences.
  }

  const preferences = {
    getItem(key) {
      if (durable) {
        try {
          const value = storage.getItem(key);
          if (value !== null) memory.set(key, value);
          return value;
        } catch {
          durable = false;
        }
      }
      return memory.get(key) ?? null;
    },
    setItem(key, value) {
      const normalized = String(value);
      memory.set(key, normalized);
      if (durable) {
        try {
          storage.setItem(key, normalized);
        } catch {
          durable = false;
        }
      }
      return durable;
    },
    removeItem(key) {
      memory.delete(key);
      if (durable) {
        try {
          storage.removeItem(key);
        } catch {
          durable = false;
        }
      }
      return durable;
    },
    isPersistent() {
      return durable;
    },
  };

  Object.defineProperty(window, 'r3aBrowserPreferences', {
    configurable: false, enumerable: false, writable: false, value: Object.freeze(preferences),
  });
})();
