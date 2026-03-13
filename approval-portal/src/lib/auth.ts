/**
 * JWT token management for the client approval portal.
 *
 * Tokens are stored in localStorage so they survive page refreshes within
 * the same browser session. The static-export Next.js app runs entirely on
 * the client, so localStorage is always available when these helpers run.
 */

const AUTH_TOKEN_KEY = "app_approval_jwt";

/**
 * Read the stored JWT, or return null if none exists.
 */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

/**
 * Persist a JWT to localStorage.
 */
export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

/**
 * Remove the stored JWT from localStorage.
 */
export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

/**
 * Check whether a JWT is present in localStorage.
 *
 * Note: this only checks for existence, not token validity or expiration.
 * The API will return 401 if the token is actually expired.
 */
export function isAuthenticated(): boolean {
  const token = getToken();
  return token !== null && token.length > 0;
}
