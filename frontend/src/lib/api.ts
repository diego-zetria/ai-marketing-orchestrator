const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/admin";

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) {
      this.token = null;
      localStorage.removeItem("admin_token");
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || res.statusText);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return res.json();
  }

  get<T>(path: string) {
    return this.request<T>("GET", path);
  }
  post<T>(path: string, body: unknown) {
    return this.request<T>("POST", path, body);
  }
  put<T>(path: string, body: unknown) {
    return this.request<T>("PUT", path, body);
  }
  patch<T = void>(path: string, body?: unknown) {
    return this.request<T>("PATCH", path, body);
  }
  delete<T>(path: string) {
    return this.request<T>("DELETE", path);
  }

  upload<T>(path: string, formData: FormData): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: formData,
    }).then(async (res) => {
      if (res.status === 401) {
        this.token = null;
        localStorage.removeItem("admin_token");
        window.location.href = "/login";
        throw new Error("Unauthorized");
      }
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || res.statusText);
      }
      return res.json();
    });
  }
}

export const api = new ApiClient();
