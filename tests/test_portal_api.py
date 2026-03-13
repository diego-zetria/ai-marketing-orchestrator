"""Tests for the Portal API Lambda handler.

All external dependencies (S3, DB, ClickUp, JWT) are mocked.
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.approval.models import (
    ApprovalAsset,
    ApprovalComment,
    ApprovalDecision,
    AssetVersion,
    Client,
    MagicLink,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before each test."""
    import lambdas.portal_api.handler as h

    h._engine = None
    h._session_factory = None
    h._media_service = None
    yield
    h._engine = None
    h._session_factory = None
    h._media_service = None


@pytest.fixture()
def env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    monkeypatch.setenv("MEDIA_BUCKET", "test-bucket")
    monkeypatch.setenv("CLICKUP_API_TOKEN", "pk_test_token")
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@test.com")
    monkeypatch.setenv("PORTAL_DOMAIN", "portal.test.com")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-jwt")


@pytest.fixture()
def sample_client():
    """Create a sample Client."""
    return Client(
        id=uuid.uuid4(),
        name="client_alpha",
        display_name="ClientAlpha",
        clickup_list_id="901234567",
        slug="client_alpha",
        email="contato@client_alpha.com",
        logo_url=None,
        is_active=True,
    )


@pytest.fixture()
def now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def sample_version(sample_asset, now):
    """Create a sample AssetVersion."""
    return AssetVersion(
        id=uuid.uuid4(),
        asset_id=sample_asset.id,
        version_number=1,
        file_type="image",
        file_format="png",
        original_url="s3://test-bucket/originals/client_alpha/asset1/v1/banner.png",
        thumbnail_url="s3://test-bucket/thumbnails/client_alpha/asset1/v1/400.webp",
        file_size_bytes=50000,
        width=1080,
        height=1080,
        duration_seconds=None,
        uploaded_by="system",
        created_at=now,
    )


@pytest.fixture()
def sample_asset(sample_client, now):
    """Create a sample ApprovalAsset with loaded relations."""
    asset = ApprovalAsset(
        id=uuid.uuid4(),
        client_id=sample_client.id,
        clickup_task_id="task_abc123",
        title="Instagram Post - ClientAlpha - Mar 2026",
        description="Campaign post",
        status="pending_review",
        current_version=1,
        created_at=now,
        updated_at=now,
    )
    # Attach relations for _build_asset_detail
    asset.client = sample_client
    asset.versions = []
    asset.comments = []
    asset.decisions = []
    return asset


@pytest.fixture()
def sample_asset_with_version(sample_asset, sample_version):
    """Asset with a version attached."""
    sample_asset.versions = [sample_version]
    return sample_asset


@pytest.fixture()
def sample_magic_link(sample_asset, sample_client):
    """Create a sample MagicLink."""
    return MagicLink(
        id=uuid.uuid4(),
        token="test-magic-link-token-abc123",
        asset_id=sample_asset.id,
        client_id=sample_client.id,
        is_active=True,
        access_count=0,
    )


@pytest.fixture()
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture()
def mock_session_factory(mock_session):
    """Create a mock sessionmaker returning the mock session as async context manager."""
    factory = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = ctx
    return factory


@pytest.fixture()
def mock_media_service():
    """Create a mock MediaService."""
    svc = MagicMock()
    svc.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned-url"
    return svc


@pytest.fixture()
def valid_jwt_claims(sample_asset, sample_client):
    """Return valid JWT claims matching the sample asset."""
    return {
        "sub": "client:client_alpha",
        "asset_id": str(sample_asset.id),
        "client_id": str(sample_client.id),
        "scope": "review",
    }


def _make_event(
    method: str = "GET",
    path: str = "/api/health",
    body: dict | None = None,
    headers: dict | None = None,
    query: dict | None = None,
) -> dict:
    """Build an API Gateway proxy event."""
    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else None,
        "headers": headers or {},
        "queryStringParameters": query or {},
    }


# ---------------------------------------------------------------------------
# 1. test_auth_validate_success
# ---------------------------------------------------------------------------
class TestAuthValidateSuccess:
    async def test_auth_validate_success(
        self,
        env_vars,
        sample_client,
        sample_asset_with_version,
        sample_magic_link,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        event = _make_event(
            method="GET",
            path="/api/auth/validate",
            query={"token": "test-magic-link-token-abc123"},
        )

        with (
            patch.object(
                h,
                "validate_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "get_asset_with_relations",
                new_callable=AsyncMock,
                return_value=sample_asset_with_version,
            ),
            patch.object(
                h, "log_event", new_callable=AsyncMock
            ),
            patch.object(
                h,
                "create_jwt",
                return_value="mock-jwt-token",
            ),
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["jwt"] == "mock-jwt-token"
        assert "asset" in body
        assert body["asset"]["asset"]["id"] == str(sample_asset_with_version.id)


# ---------------------------------------------------------------------------
# 2. test_auth_validate_missing_token
# ---------------------------------------------------------------------------
class TestAuthValidateMissingToken:
    async def test_auth_validate_missing_token(
        self,
        env_vars,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        event = _make_event(
            method="GET",
            path="/api/auth/validate",
            query={},
        )

        result = await h._route(event)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "Missing token" in body["error"]


# ---------------------------------------------------------------------------
# 3. test_auth_validate_invalid_token
# ---------------------------------------------------------------------------
class TestAuthValidateInvalidToken:
    async def test_auth_validate_invalid_token(
        self,
        env_vars,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        event = _make_event(
            method="GET",
            path="/api/auth/validate",
            query={"token": "invalid-token-xyz"},
        )

        with patch.object(
            h,
            "validate_magic_link",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await h._route(event)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert "Invalid or expired" in body["error"]


# ---------------------------------------------------------------------------
# 4. test_approve_success
# ---------------------------------------------------------------------------
class TestApproveSuccess:
    async def test_approve_success(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        decision_record = ApprovalDecision(
            id=uuid.uuid4(),
            asset_id=sample_asset_with_version.id,
            version_id=sample_asset_with_version.versions[0].id,
            decision="approved",
            decided_by="client:client_alpha",
            decided_at=datetime.now(timezone.utc),
        )

        # After approval, asset status changes
        approved_asset = sample_asset_with_version
        approved_asset.status = "approved"

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/approve",
            headers={"Authorization": "Bearer mock-jwt"},
            body={"comment": "Looks great!"},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h,
                "get_asset_with_relations",
                new_callable=AsyncMock,
                side_effect=[sample_asset_with_version, approved_asset],
            ),
            patch.object(
                h,
                "save_decision",
                new_callable=AsyncMock,
                return_value=decision_record,
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "log_event", new_callable=AsyncMock),
            patch.object(h, "_sync_clickup_decision", new_callable=AsyncMock) as mock_sync,
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["decision"]["decision"] == "approved"
        assert body["asset"]["status"] == "approved"
        mock_sync.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. test_approve_unauthorized
# ---------------------------------------------------------------------------
class TestApproveUnauthorized:
    async def test_approve_unauthorized(
        self,
        env_vars,
        sample_asset_with_version,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/approve",
            headers={},  # No auth header
            body={"comment": "Approve"},
        )

        result = await h._route(event)
        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"] == "Unauthorized"


# ---------------------------------------------------------------------------
# 6. test_request_changes_success
# ---------------------------------------------------------------------------
class TestRequestChangesSuccess:
    async def test_request_changes_success(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        decision_record = ApprovalDecision(
            id=uuid.uuid4(),
            asset_id=sample_asset_with_version.id,
            version_id=sample_asset_with_version.versions[0].id,
            decision="changes_requested",
            decided_by="client:client_alpha",
            decided_at=datetime.now(timezone.utc),
        )

        changed_asset = sample_asset_with_version
        changed_asset.status = "changes_requested"

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/request-changes",
            headers={"Authorization": "Bearer mock-jwt"},
            body={"comment": "Please adjust the colors to match brand guidelines"},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h,
                "get_asset_with_relations",
                new_callable=AsyncMock,
                side_effect=[sample_asset_with_version, changed_asset],
            ),
            patch.object(
                h,
                "save_decision",
                new_callable=AsyncMock,
                return_value=decision_record,
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "log_event", new_callable=AsyncMock),
            patch.object(h, "_sync_clickup_decision", new_callable=AsyncMock) as mock_sync,
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["decision"]["decision"] == "changes_requested"
        mock_sync.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. test_request_changes_validation_error (comment too short)
# ---------------------------------------------------------------------------
class TestRequestChangesValidationError:
    async def test_request_changes_comment_too_short(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/request-changes",
            headers={"Authorization": "Bearer mock-jwt"},
            body={"comment": "short"},  # Less than 10 chars -> validation error
        )

        with patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims):
            result = await h._route(event)

        assert result["statusCode"] == 422
        body = json.loads(result["body"])
        assert body["error"] == "Validation error"


# ---------------------------------------------------------------------------
# 8. test_add_comment_success
# ---------------------------------------------------------------------------
class TestAddCommentSuccess:
    async def test_add_comment_success(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
        now,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        comment_record = ApprovalComment(
            id=uuid.uuid4(),
            asset_id=sample_asset_with_version.id,
            version_id=None,
            author_type="client",
            author_name="client:client_alpha",
            content="Can we add the brand logo?",
            created_at=now,
        )

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/comments",
            headers={"Authorization": "Bearer mock-jwt"},
            body={"content": "Can we add the brand logo?"},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h,
                "get_asset_with_relations",
                new_callable=AsyncMock,
                return_value=sample_asset_with_version,
            ),
            patch.object(
                h,
                "add_comment",
                new_callable=AsyncMock,
                return_value=comment_record,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._route(event)

        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["content"] == "Can we add the brand logo?"
        assert body["author_type"] == "client"


# ---------------------------------------------------------------------------
# 9. test_get_asset_success
# ---------------------------------------------------------------------------
class TestGetAssetSuccess:
    async def test_get_asset_success(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        event = _make_event(
            method="GET",
            path=f"/api/assets/{asset_id}",
            headers={"Authorization": "Bearer mock-jwt"},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h,
                "get_asset_with_relations",
                new_callable=AsyncMock,
                return_value=sample_asset_with_version,
            ),
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["asset"]["id"] == asset_id
        assert body["client"]["slug"] == "client_alpha"
        assert len(body["versions"]) == 1


# ---------------------------------------------------------------------------
# 10. test_cors_preflight
# ---------------------------------------------------------------------------
class TestCorsPreflight:
    async def test_cors_preflight(self, env_vars):
        import lambdas.portal_api.handler as h

        event = _make_event(method="OPTIONS", path="/api/assets/anything")
        result = await h._route(event)

        assert result["statusCode"] == 200
        assert result["headers"]["Access-Control-Allow-Origin"] == "https://portal.test.com"
        assert "POST" in result["headers"]["Access-Control-Allow-Methods"]
        assert "Authorization" in result["headers"]["Access-Control-Allow-Headers"]
        assert result["headers"]["Vary"] == "Origin"


# ---------------------------------------------------------------------------
# 11. test_health_endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    async def test_health_endpoint(self, env_vars):
        import lambdas.portal_api.handler as h

        event = _make_event(method="GET", path="/api/health")
        result = await h._route(event)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# 12. test_route_not_found
# ---------------------------------------------------------------------------
class TestRouteNotFound:
    async def test_route_not_found(self, env_vars):
        import lambdas.portal_api.handler as h

        event = _make_event(method="GET", path="/api/nonexistent")
        result = await h._route(event)

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "Not found"


# ---------------------------------------------------------------------------
# 13. test_api_handler entry point
# ---------------------------------------------------------------------------
class TestApiHandlerEntryPoint:
    def test_api_handler_entry_point(self, env_vars):
        import lambdas.portal_api.handler as h

        expected = {"statusCode": 200, "headers": {}, "body": "{}"}
        with patch.object(h, "_route", new_callable=AsyncMock, return_value=expected):
            result = h.api_handler({"httpMethod": "GET", "path": "/api/health"}, context=None)
        assert result == expected


# ---------------------------------------------------------------------------
# 14. test_build_version_response_presigned_urls
# ---------------------------------------------------------------------------
class TestBuildVersionResponse:
    def test_build_version_response_generates_presigned_urls(
        self, sample_version, mock_media_service
    ):
        import lambdas.portal_api.handler as h

        resp = h._build_version_response(sample_version, mock_media_service)

        assert resp.media_url == "https://s3.amazonaws.com/presigned-url"
        assert resp.thumbnail_url == "https://s3.amazonaws.com/presigned-url"
        assert mock_media_service.generate_presigned_url.call_count == 2

    def test_build_version_response_external_url_passthrough(
        self, sample_version, mock_media_service,
    ):
        """External URLs (e.g. Drive links) are passed through as-is."""
        import lambdas.portal_api.handler as h

        sample_version.original_url = "https://drive.google.com/drive/folders/abc"
        sample_version.thumbnail_url = None

        resp = h._build_version_response(sample_version, mock_media_service)

        assert resp.media_url == "https://drive.google.com/drive/folders/abc"
        assert resp.thumbnail_url is None
        mock_media_service.generate_presigned_url.assert_not_called()


# ---------------------------------------------------------------------------
# 15. test_sync_clickup_decision
# ---------------------------------------------------------------------------
class TestSyncClickupDecision:
    async def test_sync_clickup_logs_error_on_failure(self, env_vars):
        import lambdas.portal_api.handler as h

        with patch("lambdas.portal_api.handler.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.put = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should NOT raise
            await h._sync_clickup_decision(
                "task123", status="aprovado", message="Approved"
            )

    async def test_sync_clickup_skips_without_token(self, monkeypatch):
        import lambdas.portal_api.handler as h

        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)

        # Should not raise, just log warning
        await h._sync_clickup_decision(
            "task123", status="aprovado", message="Approved"
        )


# ---------------------------------------------------------------------------
# A8: Client feedback uses correct ClickUp statuses
# ---------------------------------------------------------------------------
class TestA8ClientFeedbackStatuses:
    async def test_request_changes_uses_alteracao_status(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        """A8: request-changes syncs to ClickUp with alteracao."""
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        decision_record = ApprovalDecision(
            id=uuid.uuid4(),
            asset_id=sample_asset_with_version.id,
            version_id=sample_asset_with_version.versions[0].id,
            decision="changes_requested",
            decided_by="client:client_alpha",
            decided_at=datetime.now(timezone.utc),
        )
        changed_asset = sample_asset_with_version
        changed_asset.status = "changes_requested"

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/request-changes",
            headers={"Authorization": "Bearer mock-jwt"},
            body={"comment": "As cores nao combinam com a marca"},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h, "get_asset_with_relations", new_callable=AsyncMock,
                side_effect=[sample_asset_with_version, changed_asset],
            ),
            patch.object(
                h, "save_decision", new_callable=AsyncMock,
                return_value=decision_record,
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "log_event", new_callable=AsyncMock),
            patch.object(
                h, "_sync_clickup_decision", new_callable=AsyncMock,
            ) as mock_sync,
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        mock_sync.assert_awaited_once()
        call_kwargs = mock_sync.call_args
        assert call_kwargs[1]["status"] == "alteracao_cliente"
        assert "FEEDBACK DO CLIENTE" in call_kwargs[1]["message"]
        assert "Alteracoes solicitadas" in call_kwargs[1]["message"]
        assert "As cores nao combinam" in call_kwargs[1]["message"]
        assert "Portal de Aprovacao" in call_kwargs[1]["message"]

    async def test_approve_uses_pronto_status(
        self,
        env_vars,
        sample_asset_with_version,
        valid_jwt_claims,
        mock_session_factory,
        mock_media_service,
    ):
        """A8: approve syncs to ClickUp with pronto."""
        import lambdas.portal_api.handler as h

        h._session_factory = mock_session_factory
        h._media_service = mock_media_service

        asset_id = str(sample_asset_with_version.id)

        decision_record = ApprovalDecision(
            id=uuid.uuid4(),
            asset_id=sample_asset_with_version.id,
            version_id=sample_asset_with_version.versions[0].id,
            decision="approved",
            decided_by="client:client_alpha",
            decided_at=datetime.now(timezone.utc),
        )
        approved_asset = sample_asset_with_version
        approved_asset.status = "approved"

        event = _make_event(
            method="POST",
            path=f"/api/assets/{asset_id}/approve",
            headers={"Authorization": "Bearer mock-jwt"},
            body={},
        )

        with (
            patch.object(h, "_get_jwt_claims", return_value=valid_jwt_claims),
            patch.object(
                h, "get_asset_with_relations", new_callable=AsyncMock,
                side_effect=[sample_asset_with_version, approved_asset],
            ),
            patch.object(
                h, "save_decision", new_callable=AsyncMock,
                return_value=decision_record,
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "log_event", new_callable=AsyncMock),
            patch.object(
                h, "_sync_clickup_decision", new_callable=AsyncMock,
            ) as mock_sync,
        ):
            result = await h._route(event)

        assert result["statusCode"] == 200
        mock_sync.assert_awaited_once()
        assert mock_sync.call_args[1]["status"] == "aprovado_cliente"
        assert "APROVADO PELO CLIENTE" in mock_sync.call_args[1]["message"]
        assert "Portal de Aprovacao" in mock_sync.call_args[1]["message"]
