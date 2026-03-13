/**
 * TypeScript interfaces matching the Python Pydantic schemas in
 * src/approval/schemas.py.
 *
 * All UUIDs and datetimes are represented as strings (their JSON
 * serialization form).
 */

// ---------------------------------------------------------------------------
// Type literals
// ---------------------------------------------------------------------------

/** Asset workflow status. */
export type AssetStatus = "pending" | "pending_review" | "approved" | "changes_requested";

/** Media file type discriminator. */
export type FileType = "image" | "video" | "link";

/** Approval decision type. */
export type DecisionType = "approved" | "changes_requested";

/** Comment author origin. */
export type AuthorType = "client" | "team";

// ---------------------------------------------------------------------------
// Request schemas
// ---------------------------------------------------------------------------

/** Body for POST /api/assets/{assetId}/approve */
export interface ApproveRequest {
  comment?: string | null;
}

/** Body for POST /api/assets/{assetId}/request-changes */
export interface RequestChangesRequest {
  /** Detailed description of the changes needed (10-2000 chars). */
  comment: string;
}

/** Body for POST /api/assets/{assetId}/comments */
export interface AddCommentRequest {
  /** Comment text (1-5000 chars). */
  content: string;
}

// ---------------------------------------------------------------------------
// Response schemas
// ---------------------------------------------------------------------------

export interface ClientResponse {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
}

export interface VersionResponse {
  id: string;
  version_number: number;
  file_type: FileType;
  file_format: string;
  media_url: string | null;
  thumbnail_url: string | null;
  file_size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  uploaded_by: string | null;
  created_at: string;
}

export interface CommentResponse {
  id: string;
  author_type: AuthorType;
  author_name: string;
  content: string;
  created_at: string;
}

export interface DecisionResponse {
  id: string;
  decision: DecisionType;
  comment: string | null;
  decided_by: string;
  decided_at: string;
}

export interface AssetResponse {
  id: string;
  title: string;
  description: string | null;
  status: AssetStatus;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface AssetDetailResponse {
  asset: AssetResponse;
  client: ClientResponse;
  current_version: VersionResponse | null;
  versions: VersionResponse[];
  comments: CommentResponse[];
  decisions: DecisionResponse[];
}

export interface AuthValidateResponse {
  jwt: string;
  asset: AssetDetailResponse;
}

export interface DecisionResultResponse {
  decision: DecisionResponse;
  asset: AssetResponse;
}
