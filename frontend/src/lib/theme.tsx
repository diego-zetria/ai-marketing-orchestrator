import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
}

const STORAGE_KEY = "app-theme";

function getSystemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function resolveTheme(theme: Theme): "light" | "dark" {
  return theme === "system" ? getSystemTheme() : theme;
}

/** Apply the dark class to <html> — pure DOM side-effect, no React state. */
function applyToDom(resolved: "light" | "dark") {
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeRaw] = useState<Theme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system")
      return stored;
    return "system";
  });

  // Derive resolved from theme — no separate state needed
  const resolved = resolveTheme(theme);

  // Track previous resolved to avoid redundant DOM writes
  const prevRef = useRef(resolved);

  // Apply to DOM on mount and when resolved changes
  useEffect(() => {
    applyToDom(resolved);
    prevRef.current = resolved;
  }, [resolved]);

  const setTheme = useCallback((t: Theme) => {
    setThemeRaw(t);
    localStorage.setItem(STORAGE_KEY, t);
    // Eagerly apply to DOM so there's no flash
    applyToDom(resolveTheme(t));
  }, []);

  // Listen for OS theme changes when mode is "system"
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      applyToDom(getSystemTheme());
      // Force re-render so resolvedTheme updates
      setThemeRaw("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme: resolved, setTheme }),
    [theme, resolved, setTheme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
