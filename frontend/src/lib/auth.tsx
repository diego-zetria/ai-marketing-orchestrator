import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UserInfo {
  id: string;
  email: string;
  name: string;
  role: string;
  permissions: Record<string, string[]>;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserInfo | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (resource: string, action: string) => boolean;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextType | null>(null);

function getStoredUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("admin_user");
    return raw ? (JSON.parse(raw) as UserInfo) : null;
  } catch {
    return null;
  }
}

function getInitialAuth(): boolean {
  const token = localStorage.getItem("admin_token");
  if (token) {
    api.setToken(token);
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(getInitialAuth);
  const [user, setUser] = useState<UserInfo | null>(getStoredUser);

  const login = async (email: string, password: string) => {
    const res = await api.post<{ token: string; user: UserInfo }>(
      "/auth/login",
      { email, password },
    );
    api.setToken(res.token);
    localStorage.setItem("admin_token", res.token);
    localStorage.setItem("admin_user", JSON.stringify(res.user));
    setUser(res.user);
    setIsAuthenticated(true);
  };

  const logout = () => {
    api.setToken(null);
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    setUser(null);
    setIsAuthenticated(false);
  };

  const hasPermission = useCallback(
    (resource: string, action: string): boolean => {
      if (!user) return false;
      const actions = user.permissions[resource];
      return Array.isArray(actions) && actions.includes(action);
    },
    [user],
  );

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, user, login, logout, hasPermission }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/**
 * Hook to check permissions in components.
 * Usage: const canEdit = usePermission("clients", "update");
 */
export function usePermission(resource: string, action: string): boolean {
  const { hasPermission } = useAuth();
  return hasPermission(resource, action);
}
