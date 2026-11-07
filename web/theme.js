(() => {
  const KEY = "vanguard-theme";
  const MODES = ["system", "light", "dark"];
  let mode = "system";
  try {
    const stored = localStorage.getItem(KEY);
    if (MODES.includes(stored)) mode = stored;
  } catch {
    // Storage can be unavailable (private mode); fall back to the system preference.
  }
  document.documentElement.dataset.theme = mode;
})();
