"""Tests for the Approval Processor Lambda handler.

Updated for Drive-link flow: Lambda extracts Google Drive link from
task custom field (populated by A3) instead of downloading attachments to S3.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.approval.models import ApprovalAsset, AssetVersion, Client, MagicLink


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before each test."""
    import lambdas.approval_processor.handler as h

    h._engine = None
    h._session_factory = None
    h._email_service = None
    h._whatsapp_service = None
    yield
    h._engine = None
    h._session_factory = None
    h._email_service = None
    h._whatsapp_service = None


@pytest.fixture()
def env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    monkeypatch.setenv("CLICKUP_API_TOKEN", "pk_test_token")
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@test.com")
    monkeypatch.setenv("PORTAL_DOMAIN", "https://portal.test.com")


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
        is_active=True,
    )


@pytest.fixture()
def sample_asset(sample_client):
    """Create a sample ApprovalAsset."""
    return ApprovalAsset(
        id=uuid.uuid4(),
        client_id=sample_client.id,
        clickup_task_id="task_abc123",
        title="Instagram Post - ClientAlpha - Mar 2026",
        description="Campaign post",
        status="pending_review",
        current_version=1,
    )


@pytest.fixture()
def sample_magic_link(sample_asset, sample_client):
    """Create a sample MagicLink."""
    return MagicLink(
        id=uuid.uuid4(),
        token="test-token-abc123xyz",
        asset_id=sample_asset.id,
        client_id=sample_client.id,
        is_active=True,
        access_count=0,
    )


@pytest.fixture()
def clickup_task_with_drive_link():
    """ClickUp task with Drive link in custom field."""
    return {
        "id": "task_abc123",
        "name": "Instagram Post - ClientAlpha - Mar 2026",
        "description": "Campaign post",
        "list": {"id": "901234567"},
        "custom_fields": [
            {
                "id": "cf_drive",
                "name": "Link Entrega",
                "value": "https://drive.google.com/drive/folders/abc123",
            },
        ],
    }


@pytest.fixture()
def clickup_task_no_drive_link():
    """ClickUp task without Drive link."""
    return {
        "id": "task_abc123",
        "name": "Task without Drive link",
        "description": "",
        "list": {"id": "901234567"},
        "custom_fields": [],
    }


@pytest.fixture()
def clickup_task_drive_in_description():
    """ClickUp task with Drive link only in description."""
    return {
        "id": "task_abc123",
        "name": "Task with Drive in description",
        "description": "Files at https://drive.google.com/drive/folders/xyz789",
        "list": {"id": "901234567"},
        "custom_fields": [],
    }


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
    """Create a mock sessionmaker that returns the mock session."""
    factory = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = ctx
    return factory


def _make_event(task_id: str = "task_abc123") -> dict:
    """Build an EventBridge event."""
    return {"detail": {"task_id": task_id}}


# ---------------------------------------------------------------------------
# 1. Happy path: creates asset with Drive link
# ---------------------------------------------------------------------------
class TestProcessCreatesAssetWithDriveLink:
    async def test_process_creates_asset_and_version(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_with_drive_link,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._email_service.send_new_asset_email = AsyncMock(
            return_value={"MessageId": "msg123"},
        )

        with (
            patch.object(
                h, "_fetch_task", new_callable=AsyncMock,
                return_value=clickup_task_with_drive_link,
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock,
                return_value=sample_client,
            ),
            patch.object(
                h, "get_asset_by_task_id", new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                h, "create_asset", new_callable=AsyncMock,
                return_value=sample_asset,
            ) as mock_create_asset,
            patch.object(
                h, "create_version", new_callable=AsyncMock,
            ) as mock_create_version,
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        assert result["version"] == 1
        mock_create_asset.assert_awaited_once()
        mock_create_version.assert_awaited_once()

        # Verify Drive link is stored as original_url
        version_kwargs = mock_create_version.call_args[1]
        assert version_kwargs["original_url"] == (
            "https://drive.google.com/drive/folders/abc123"
        )
        assert version_kwargs["file_type"] == "link"
        assert version_kwargs["file_format"] == "drive"

        # Verify email sent with Drive link
        h._email_service.send_new_asset_email.assert_awaited_once()
        email_kwargs = h._email_service.send_new_asset_email.call_args[1]
        assert email_kwargs["thumbnail_url"] == (
            "https://drive.google.com/drive/folders/abc123"
        )


# ---------------------------------------------------------------------------
# 2. No Drive link — returns early
# ---------------------------------------------------------------------------
class TestProcessNoDriveLink:
    async def test_process_no_drive_link_returns_early(
        self,
        env_vars,
        clickup_task_no_drive_link,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()

        with patch.object(
            h, "_fetch_task", new_callable=AsyncMock,
            return_value=clickup_task_no_drive_link,
        ):
            result = await h._process(_make_event())

        assert result["status"] == "skipped"
        assert result["reason"] == "no_drive_link"


# ---------------------------------------------------------------------------
# 3. Client not found
# ---------------------------------------------------------------------------
class TestProcessClientNotFound:
    async def test_process_client_not_found(
        self,
        env_vars,
        clickup_task_with_drive_link,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()

        with (
            patch.object(
                h, "_fetch_task", new_callable=AsyncMock,
                return_value=clickup_task_with_drive_link,
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "skipped"
        assert result["reason"] == "client_not_found"


# ---------------------------------------------------------------------------
# 4. Updates existing asset (version increment)
# ---------------------------------------------------------------------------
class TestProcessUpdatesExistingAsset:
    async def test_process_updates_existing_asset(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_with_drive_link,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._email_service.send_new_asset_email = AsyncMock(
            return_value={"MessageId": "msg2"},
        )

        # Existing asset with version 2 -> new version should be 3
        sample_asset.current_version = 2

        with (
            patch.object(
                h, "_fetch_task", new_callable=AsyncMock,
                return_value=clickup_task_with_drive_link,
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock,
                return_value=sample_client,
            ),
            patch.object(
                h, "get_asset_by_task_id", new_callable=AsyncMock,
                return_value=sample_asset,
            ),
            patch.object(h, "create_asset", new_callable=AsyncMock) as mock_create,
            patch.object(h, "create_version", new_callable=AsyncMock),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        assert result["version"] == 3
        mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Drive link extracted from description (fallback)
# ---------------------------------------------------------------------------
class TestProcessDriveLinkFromDescription:
    async def test_extracts_drive_link_from_description(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_drive_in_description,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._email_service.send_new_asset_email = AsyncMock(
            return_value={"MessageId": "msg3"},
        )

        with (
            patch.object(
                h, "_fetch_task", new_callable=AsyncMock,
                return_value=clickup_task_drive_in_description,
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock,
                return_value=sample_client,
            ),
            patch.object(
                h, "get_asset_by_task_id", new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                h, "create_asset", new_callable=AsyncMock,
                return_value=sample_asset,
            ),
            patch.object(h, "create_version", new_callable=AsyncMock) as mock_ver,
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        ver_kwargs = mock_ver.call_args[1]
        assert "drive.google.com" in ver_kwargs["original_url"]


# ---------------------------------------------------------------------------
# 6. Sends email with Drive link
# ---------------------------------------------------------------------------
class TestProcessSendsEmail:
    async def test_process_sends_email_with_drive_link(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_with_drive_link,
        mock_session_factory,
    ):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._email_service.send_new_asset_email = AsyncMock(
            return_value={"MessageId": "msg4"},
        )

        with (
            patch.object(
                h, "_fetch_task", new_callable=AsyncMock,
                return_value=clickup_task_with_drive_link,
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock,
                return_value=sample_client,
            ),
            patch.object(
                h, "get_asset_by_task_id", new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                h, "create_asset", new_callable=AsyncMock,
                return_value=sample_asset,
            ),
            patch.object(h, "create_version", new_callable=AsyncMock),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            await h._process(_make_event())

        h._email_service.send_new_asset_email.assert_awaited_once_with(
            to_email="contato@client_alpha.com",
            client_name="ClientAlpha",
            asset_title="Instagram Post - ClientAlpha - Mar 2026",
            thumbnail_url="https://drive.google.com/drive/folders/abc123",
            magic_link_token="test-token-abc123xyz",
            version_number=1,
        )


# ---------------------------------------------------------------------------
# 7. _init_services creates singletons (no MediaService needed)
# ---------------------------------------------------------------------------
class TestInitServicesCreatesSingletons:
    def test_init_services_creates_singletons(self, env_vars):
        import lambdas.approval_processor.handler as h

        with (
            patch("lambdas.approval_processor.handler.create_async_engine") as mock_eng,
            patch("lambdas.approval_processor.handler.sessionmaker") as mock_sm,
            patch("lambdas.approval_processor.handler.EmailService") as mock_email,
        ):
            mock_eng.return_value = MagicMock()
            mock_sm.return_value = MagicMock()
            mock_email.return_value = MagicMock()

            h._init_services()

            mock_eng.assert_called_once()
            mock_email.assert_called_once_with(
                from_email="noreply@test.com",
                portal_domain="https://portal.test.com",
            )
            assert h._engine is not None
            assert h._session_factory is not None
            assert h._email_service is not None

    def test_init_services_idempotent(self, env_vars):
        """Calling _init_services twice only creates singletons once."""
        import lambdas.approval_processor.handler as h

        with (
            patch("lambdas.approval_processor.handler.create_async_engine") as mock_eng,
            patch("lambdas.approval_processor.handler.sessionmaker") as mock_sm,
            patch("lambdas.approval_processor.handler.EmailService") as mock_email,
        ):
            mock_eng.return_value = MagicMock()
            mock_sm.return_value = MagicMock()
            mock_email.return_value = MagicMock()

            h._init_services()
            h._init_services()

            mock_eng.assert_called_once()
            mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# 8. _extract_drive_link helper
# ---------------------------------------------------------------------------
class TestExtractDriveLink:
    def test_extracts_from_custom_field(self):
        from lambdas.approval_processor.handler import _extract_drive_link

        task = {
            "custom_fields": [
                {"id": "cf1", "value": "https://drive.google.com/drive/folders/abc"},
            ],
            "description": "",
        }
        assert _extract_drive_link(task) == (
            "https://drive.google.com/drive/folders/abc"
        )

    def test_extracts_from_description_fallback(self):
        from lambdas.approval_processor.handler import _extract_drive_link

        task = {
            "custom_fields": [],
            "description": "Files at https://drive.google.com/file/d/xyz end",
        }
        assert "drive.google.com" in _extract_drive_link(task)

    def test_returns_empty_when_no_link(self):
        from lambdas.approval_processor.handler import _extract_drive_link

        task = {"custom_fields": [], "description": "No links here"}
        assert _extract_drive_link(task) == ""

    def test_custom_field_priority_over_description(self):
        from lambdas.approval_processor.handler import _extract_drive_link

        task = {
            "custom_fields": [
                {"id": "cf1", "value": "https://drive.google.com/custom_field"},
            ],
            "description": "https://drive.google.com/description",
        }
        assert _extract_drive_link(task) == (
            "https://drive.google.com/custom_field"
        )

    def test_ignores_non_drive_custom_fields(self):
        from lambdas.approval_processor.handler import _extract_drive_link

        task = {
            "custom_fields": [
                {"id": "cf1", "value": "some text"},
                {"id": "cf2", "value": 42},
                {"id": "cf3", "value": None},
            ],
            "description": "",
        }
        assert _extract_drive_link(task) == ""


# ---------------------------------------------------------------------------
# 9. process_webhook entry point
# ---------------------------------------------------------------------------
class TestProcessWebhookEntryPoint:
    def test_process_webhook_entry_point(self, env_vars, mock_session_factory):
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()

        expected = {"status": "skipped", "reason": "no_drive_link", "task_id": "t1"}

        with patch.object(h, "_process", new_callable=AsyncMock, return_value=expected):
            result = h.process_webhook({"detail": {"task_id": "t1"}}, context=None)

        assert result == expected


# ---------------------------------------------------------------------------
# 9. WhatsApp sends when phone + service available
# ---------------------------------------------------------------------------
class TestProcessSendsWhatsApp:
    async def test_process_sends_whatsapp(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_data,
        mock_session,
        mock_session_factory,
    ):
        """WhatsApp is called when client has whatsapp_phone and service is available."""
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._media_service = MagicMock()
        h._email_service = MagicMock()
        h._whatsapp_service = MagicMock()

        sample_client.whatsapp_phone = "5541999887766"

        h._media_service.detect_file_type.return_value = ("image", "png")
        h._media_service.upload_image = AsyncMock(
            return_value={
                "original_url": "s3://bucket/banner.png",
                "thumbnail_url": "s3://bucket/400.webp",
                "width": 1080,
                "height": 1080,
                "file_size_bytes": 50000,
            }
        )
        h._email_service.send_new_asset_email = AsyncMock(return_value={"MessageId": "msg"})
        h._whatsapp_service.send_new_asset_message = AsyncMock(
            return_value={"messages": [{"id": "wamid.test"}]}
        )

        version_record = AssetVersion(
            id=uuid.uuid4(),
            asset_id=sample_asset.id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="s3://bucket/banner.png",
            thumbnail_url="s3://bucket/400.webp",
        )

        with (
            patch.object(h, "_fetch_task", new_callable=AsyncMock, return_value=clickup_task_data),
            patch.object(
                h, "_download_attachment", new_callable=AsyncMock, return_value=b"img"
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock, return_value=sample_client
            ),
            patch.object(h, "get_asset_by_task_id", new_callable=AsyncMock, return_value=None),
            patch.object(
                h, "create_asset", new_callable=AsyncMock, return_value=sample_asset
            ),
            patch.object(
                h, "create_version", new_callable=AsyncMock, return_value=version_record
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock, return_value=sample_magic_link
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        h._whatsapp_service.send_new_asset_message.assert_awaited_once()


# ---------------------------------------------------------------------------
# 10. WhatsApp failure is non-fatal
# ---------------------------------------------------------------------------
class TestProcessWhatsAppFailureNonFatal:
    async def test_process_whatsapp_failure_nonfatal(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_data,
        mock_session,
        mock_session_factory,
    ):
        """WhatsApp failure does not block email, DB commit, or result."""
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._media_service = MagicMock()
        h._email_service = MagicMock()
        h._whatsapp_service = MagicMock()

        sample_client.whatsapp_phone = "5541999887766"

        h._media_service.detect_file_type.return_value = ("image", "png")
        h._media_service.upload_image = AsyncMock(
            return_value={
                "original_url": "s3://bucket/banner.png",
                "thumbnail_url": "s3://bucket/400.webp",
                "width": 1080,
                "height": 1080,
                "file_size_bytes": 50000,
            }
        )
        h._email_service.send_new_asset_email = AsyncMock(return_value={"MessageId": "msg"})
        h._whatsapp_service.send_new_asset_message = AsyncMock(
            side_effect=Exception("WhatsApp API down")
        )

        version_record = AssetVersion(
            id=uuid.uuid4(),
            asset_id=sample_asset.id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="s3://bucket/banner.png",
            thumbnail_url="s3://bucket/400.webp",
        )

        with (
            patch.object(h, "_fetch_task", new_callable=AsyncMock, return_value=clickup_task_data),
            patch.object(
                h, "_download_attachment", new_callable=AsyncMock, return_value=b"img"
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock, return_value=sample_client
            ),
            patch.object(h, "get_asset_by_task_id", new_callable=AsyncMock, return_value=None),
            patch.object(
                h, "create_asset", new_callable=AsyncMock, return_value=sample_asset
            ),
            patch.object(
                h, "create_version", new_callable=AsyncMock, return_value=version_record
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock, return_value=sample_magic_link
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        # Still returns ok despite WhatsApp failure
        assert result["status"] == "ok"
        h._email_service.send_new_asset_email.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 11. Skips WhatsApp when client has no phone
# ---------------------------------------------------------------------------
class TestProcessSkipsWhatsAppNoPhone:
    async def test_process_skips_whatsapp_no_phone(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_data,
        mock_session,
        mock_session_factory,
    ):
        """WhatsApp is not called when client.whatsapp_phone is None."""
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._media_service = MagicMock()
        h._email_service = MagicMock()
        h._whatsapp_service = MagicMock()

        sample_client.whatsapp_phone = None

        h._media_service.detect_file_type.return_value = ("image", "png")
        h._media_service.upload_image = AsyncMock(
            return_value={
                "original_url": "s3://bucket/banner.png",
                "thumbnail_url": "s3://bucket/400.webp",
                "width": 1080,
                "height": 1080,
                "file_size_bytes": 50000,
            }
        )
        h._email_service.send_new_asset_email = AsyncMock(return_value={"MessageId": "msg"})

        version_record = AssetVersion(
            id=uuid.uuid4(),
            asset_id=sample_asset.id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="s3://bucket/banner.png",
            thumbnail_url="s3://bucket/400.webp",
        )

        with (
            patch.object(h, "_fetch_task", new_callable=AsyncMock, return_value=clickup_task_data),
            patch.object(
                h, "_download_attachment", new_callable=AsyncMock, return_value=b"img"
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock, return_value=sample_client
            ),
            patch.object(h, "get_asset_by_task_id", new_callable=AsyncMock, return_value=None),
            patch.object(
                h, "create_asset", new_callable=AsyncMock, return_value=sample_asset
            ),
            patch.object(
                h, "create_version", new_callable=AsyncMock, return_value=version_record
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock, return_value=sample_magic_link
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        h._whatsapp_service.send_new_asset_message.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Skips WhatsApp when service is None
# ---------------------------------------------------------------------------
class TestProcessSkipsWhatsAppNoService:
    async def test_process_skips_whatsapp_no_service(
        self,
        env_vars,
        sample_client,
        sample_asset,
        sample_magic_link,
        clickup_task_data,
        mock_session,
        mock_session_factory,
    ):
        """No error when _whatsapp_service is None."""
        import lambdas.approval_processor.handler as h

        h._session_factory = mock_session_factory
        h._media_service = MagicMock()
        h._email_service = MagicMock()
        h._whatsapp_service = None

        sample_client.whatsapp_phone = "5541999887766"

        h._media_service.detect_file_type.return_value = ("image", "png")
        h._media_service.upload_image = AsyncMock(
            return_value={
                "original_url": "s3://bucket/banner.png",
                "thumbnail_url": "s3://bucket/400.webp",
                "width": 1080,
                "height": 1080,
                "file_size_bytes": 50000,
            }
        )
        h._email_service.send_new_asset_email = AsyncMock(return_value={"MessageId": "msg"})

        version_record = AssetVersion(
            id=uuid.uuid4(),
            asset_id=sample_asset.id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="s3://bucket/banner.png",
            thumbnail_url="s3://bucket/400.webp",
        )

        with (
            patch.object(h, "_fetch_task", new_callable=AsyncMock, return_value=clickup_task_data),
            patch.object(
                h, "_download_attachment", new_callable=AsyncMock, return_value=b"img"
            ),
            patch.object(
                h, "get_client_by_list_id", new_callable=AsyncMock, return_value=sample_client
            ),
            patch.object(h, "get_asset_by_task_id", new_callable=AsyncMock, return_value=None),
            patch.object(
                h, "create_asset", new_callable=AsyncMock, return_value=sample_asset
            ),
            patch.object(
                h, "create_version", new_callable=AsyncMock, return_value=version_record
            ),
            patch.object(h, "update_asset_status", new_callable=AsyncMock),
            patch.object(h, "deactivate_magic_links", new_callable=AsyncMock),
            patch.object(
                h, "create_magic_link", new_callable=AsyncMock, return_value=sample_magic_link
            ),
            patch.object(h, "log_event", AsyncMock()),
        ):
            result = await h._process(_make_event())

        assert result["status"] == "ok"
        h._email_service.send_new_asset_email.assert_awaited_once()
