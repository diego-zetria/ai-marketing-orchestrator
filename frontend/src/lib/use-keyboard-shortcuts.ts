import { useEffect, useState } from "react";

export function useKeyboardShortcuts(callbacks: {
  onToggleSidebar?: () => void;
  onOpenCommandPalette?: () => void;
  onNavigate?: (to: string) => void;
}) {
  const [showHelp, setShowHelp] = useState(false);
  const [gPending, setGPending] = useState(false);

  useEffect(() => {
    let gTimer: ReturnType<typeof setTimeout>;

    function isInputFocused() {
      const el = document.activeElement;
      if (!el) return false;
      const tag = el.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
      if ((el as HTMLElement).isContentEditable) return true;
      return false;
    }

    function onKeyDown(e: KeyboardEvent) {
      if (isInputFocused()) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // ? — show shortcuts help
      if (e.key === "?") {
        e.preventDefault();
        setShowHelp(true);
        return;
      }

      // G + second key — navigation chords
      if (gPending) {
        setGPending(false);
        clearTimeout(gTimer);
        const map: Record<string, string> = {
          d: "/",
          a: "/approvals",
          e: "/team",
          c: "/clients",
        };
        const to = map[e.key.toLowerCase()];
        if (to) {
          e.preventDefault();
          callbacks.onNavigate?.(to);
        }
        return;
      }

      if (e.key.toLowerCase() === "g") {
        setGPending(true);
        gTimer = setTimeout(() => setGPending(false), 800);
        return;
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      clearTimeout(gTimer);
    };
  }, [gPending, callbacks]);

  return { showHelp, setShowHelp };
}
