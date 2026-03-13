import { useState, useCallback } from "react";

const STORAGE_KEY = "app-sidebar-collapsed";

export function useSidebarState() {
  const [collapsed, setCollapsedRaw] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedRaw(next);
    try {
      localStorage.setItem(STORAGE_KEY, String(next));
    } catch {
      // localStorage unavailable
    }
  }, []);

  const toggle = useCallback(() => {
    setCollapsed(!collapsed);
  }, [collapsed, setCollapsed]);

  return { collapsed, setCollapsed, toggle } as const;
}
