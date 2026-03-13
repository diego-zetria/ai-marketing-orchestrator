/**
 * API client for the Agency client approval portal.
 *
 * Every request (except token validation) automatically attaches the JWT
 * stored by the auth module.  All endpoints return typed responses matching
 * the Python Pydantic schemas.
 */

import { getToken } from "@/lib/auth";
import type {
  AddCommentRequest,
  ApproveRequest,
  AssetDetailResponse,
  AuthValidateResponse,
  CommentResponse,
  DecisionResultResponse,
  RequestChangesRequest,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Base URL for all API calls.  Set via the `NEXT_PUBLIC_API_URL` environment
 * variable at build time.  Falls back to an empty string (same-origin) so
 * local development "just works" when proxied.
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "";

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

/**
 * Typed error thrown for any non-2xx API response.
 */
export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    // Restore prototype chain (required when extending built-ins in TS)
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    // Strip trailing slash to avoid double slashes in URL construction
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  // -----------------------------------------------------------------------
  // Internal fetch wrapper
  // -----------------------------------------------------------------------

  /**
   * Execute a fetch request with automatic auth headers, JSON parsing,
   * and structured error handling.
   *
   * @param path    - API path (e.g. "/api/assets/123")
   * @param options - Standard RequestInit overrides
   * @returns Parsed JSON body of type T
   * @throws {ApiError} on any non-2xx response
   */
  private async _fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string> | undefined),
    };

    // Attach bearer token if available
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let message = `Request failed: ${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (body.error) {
          message = body.error;
        }
      } catch {
        // Response body was not JSON -- keep the default message
      }
      throw new ApiError(response.status, message);
    }

    return (await response.json()) as T;
  }

  // -----------------------------------------------------------------------
  // Public API methods
  // -----------------------------------------------------------------------

  /**
   * Validate a magic-link token and receive a JWT + asset detail.
   *
   * GET /api/auth/validate?token=...
   *
   * Note: this endpoint does NOT require a pre-existing JWT.
   */
  async validateToken(token: string): Promise<AuthValidateResponse> {
    const encoded = encodeURIComponent(token);
    return this._fetch<AuthValidateResponse>(
      `/api/auth/validate?token=${encoded}`,
    );
  }

  /**
   * Fetch full asset detail including versions, comments, and decisions.
   *
   * GET /api/assets/{assetId}
   */
  async getAsset(assetId: string): Promise<AssetDetailResponse> {
    return this._fetch<AssetDetailResponse>(`/api/assets/${assetId}`);
  }

  /**
   * Record an approval decision for the asset.
   *
   * POST /api/assets/{assetId}/approve
   */
  async approveAsset(
    assetId: string,
    comment?: string,
  ): Promise<DecisionResultResponse> {
    const body: ApproveRequest = { comment: comment ?? null };
    return this._fetch<DecisionResultResponse>(
      `/api/assets/${assetId}/approve`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  }

  /**
   * Record a change-request decision for the asset.
   *
   * POST /api/assets/{assetId}/request-changes
   */
  async requestChanges(
    assetId: string,
    comment: string,
  ): Promise<DecisionResultResponse> {
    const body: RequestChangesRequest = { comment };
    return this._fetch<DecisionResultResponse>(
      `/api/assets/${assetId}/request-changes`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  }

  /**
   * Add a client comment to the asset.
   *
   * POST /api/assets/{assetId}/comments
   */
  async addComment(
    assetId: string,
    content: string,
  ): Promise<CommentResponse> {
    const body: AddCommentRequest = { content };
    return this._fetch<CommentResponse>(
      `/api/assets/${assetId}/comments`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Default singleton
// ---------------------------------------------------------------------------

export const api = new ApiClient();
