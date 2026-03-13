"""Tests for the Approval Reminder Lambda handler.

All external dependencies (DB, SES, S3) are mocked.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.approval.models import ApprovalAsset, AssetVersion, Client, MagicLink


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons before each test."""
    import lambdas.approval_reminder.handler as h

    h._engine = None
    h._session_factory = None
    h._email_service = None
    h._media_service = None
    h._whatsapp_service = None
    yield
    h._engine = None
    h._session_factory = None
    h._email_service = None
    h._media_service = None
    h._whatsapp_service = None


@pytest.fixture()
def env_vars(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    monkeypatch.setenv("MEDIA_BUCKET", "test-bucket")
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
    """Create a sample ApprovalAsset with a client relationship."""
    asset = ApprovalAsset(
        id=uuid.uuid4(),
        client_id=sample_client.id,
        clickup_task_id="task_abc123",
        title="Instagram Post - ClientAlpha - Mar 2026",
        description="Campaign post",
        status="pending_review",
        current_version=1,
    )
    # Wire up the relationship manually for tests (no DB)
    asset.client = sample_client
    return asset


@pytest.fixture()
def sample_magic_link(sample_asset, sample_client):
    """Create a sample active MagicLink."""
    return MagicLink(
        id=uuid.uuid4(),
        token="test-reminder-token-xyz",
        asset_id=sample_asset.id,
        client_id=sample_client.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=5),
        is_active=True,
        access_count=0,
    )


@pytest.fixture()
def sample_version(sample_asset):
    """Create a sample AssetVersion with thumbnail."""
    return AssetVersion(
        id=uuid.uuid4(),
        asset_id=sample_asset.id,
        version_number=1,
        file_type="image",
        file_format="png",
        original_url="s3://test-bucket/originals/client_alpha/asset1/v1/banner.png",
        thumbnail_url="s3://test-bucket/thumbnails/client_alpha/asset1/v1/400.webp",
    )


@pytest.fixture()
def sample_version_no_thumbnail(sample_asset):
    """Create a sample AssetVersion without thumbnail."""
    return AssetVersion(
        id=uuid.uuid4(),
        asset_id=sample_asset.id,
        version_number=1,
        file_type="video",
        file_format="mp4",
        original_url="s3://test-bucket/videos/client_alpha/asset1/v1/video.mp4",
        thumbnail_url=None,
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
    """Create a mock sessionmaker that returns the mock session as async context manager."""
    factory = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = ctx
    return factory


# ---------------------------------------------------------------------------
# 1. test_check_reminders_sends_emails
# ---------------------------------------------------------------------------
class TestCheckRemindersSendsEmails:
    async def test_check_reminders_sends_emails(
        self,
        env_vars,
        sample_asset,
        sample_magic_link,
        sample_version,
        mock_session,
        mock_session_factory,
    ):
        """Assets older than threshold get reminder emails."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock(
            return_value={"MessageId": "reminder1"}
        )
        h._media_service.generate_presigned_url = MagicMock(
            return_value="https://presigned.url/thumb"
        )

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                return_value=[sample_asset],
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "_get_latest_version",
                new_callable=AsyncMock,
                return_value=sample_version,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["status"] == "ok"
        # 2 thresholds, same asset each time -> 2 reminders
        # But the second call to _was_reminded_today is mocked to False,
        # so it sends for both thresholds
        assert result["reminders_sent"] == 2
        assert h._email_service.send_reminder_email.await_count == 2


# ---------------------------------------------------------------------------
# 2. test_check_reminders_skips_already_reminded_today
# ---------------------------------------------------------------------------
class TestCheckRemindersSkipsAlreadyRemindedToday:
    async def test_check_reminders_skips_already_reminded_today(
        self,
        env_vars,
        sample_asset,
        mock_session,
        mock_session_factory,
    ):
        """Assets that already got a reminder today are skipped."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock()

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                return_value=[sample_asset],
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=True
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["status"] == "ok"
        assert result["reminders_sent"] == 0
        h._email_service.send_reminder_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. test_check_reminders_skips_no_active_magic_link
# ---------------------------------------------------------------------------
class TestCheckRemindersSkipsNoActiveMagicLink:
    async def test_check_reminders_skips_no_active_magic_link(
        self,
        env_vars,
        sample_asset,
        mock_session,
        mock_session_factory,
    ):
        """Assets with no active magic link are skipped."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock()

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                return_value=[sample_asset],
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["status"] == "ok"
        assert result["reminders_sent"] == 0
        h._email_service.send_reminder_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 4. test_check_reminders_no_pending_assets
# ---------------------------------------------------------------------------
class TestCheckRemindersNoPendingAssets:
    async def test_check_reminders_no_pending_assets(
        self,
        env_vars,
        mock_session,
        mock_session_factory,
    ):
        """No pending assets returns zero count."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock()

        with patch.object(
            h,
            "get_pending_assets_older_than",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await h._check_reminders({})

        assert result["status"] == "ok"
        assert result["reminders_sent"] == 0
        h._email_service.send_reminder_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. test_check_reminders_with_thumbnail
# ---------------------------------------------------------------------------
class TestCheckRemindersWithThumbnail:
    async def test_check_reminders_with_thumbnail(
        self,
        env_vars,
        sample_asset,
        sample_magic_link,
        sample_version,
        mock_session,
        mock_session_factory,
    ):
        """When a version has a thumbnail, a presigned URL is generated."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock(
            return_value={"MessageId": "msg_thumb"}
        )
        h._media_service.generate_presigned_url = MagicMock(
            return_value="https://presigned.url/thumb"
        )

        # Only return asset for the first threshold to keep assertions simple
        call_count = 0

        async def _pending_side_effect(session, days):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [sample_asset]
            return []

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                side_effect=_pending_side_effect,
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "_get_latest_version",
                new_callable=AsyncMock,
                return_value=sample_version,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["reminders_sent"] == 1
        # Presigned URL should be used as thumbnail_url
        h._media_service.generate_presigned_url.assert_called_once_with(
            "thumbnails/client_alpha/asset1/v1/400.webp"
        )
        call_kwargs = h._email_service.send_reminder_email.call_args
        assert call_kwargs.kwargs["thumbnail_url"] == "https://presigned.url/thumb"


# ---------------------------------------------------------------------------
# 6. test_check_reminders_without_thumbnail
# ---------------------------------------------------------------------------
class TestCheckRemindersWithoutThumbnail:
    async def test_check_reminders_without_thumbnail(
        self,
        env_vars,
        sample_asset,
        sample_magic_link,
        sample_version_no_thumbnail,
        mock_session,
        mock_session_factory,
    ):
        """When a version has no thumbnail, an empty string is passed."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        h._email_service.send_reminder_email = AsyncMock(
            return_value={"MessageId": "msg_no_thumb"}
        )

        call_count = 0

        async def _pending_side_effect(session, days):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [sample_asset]
            return []

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                side_effect=_pending_side_effect,
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "_get_latest_version",
                new_callable=AsyncMock,
                return_value=sample_version_no_thumbnail,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["reminders_sent"] == 1
        # No presigned URL should be generated
        h._media_service.generate_presigned_url.assert_not_called()
        call_kwargs = h._email_service.send_reminder_email.call_args
        assert call_kwargs.kwargs["thumbnail_url"] == ""


# ---------------------------------------------------------------------------
# 7. test_entry_point_returns_count
# ---------------------------------------------------------------------------
class TestEntryPointReturnsCount:
    def test_entry_point_returns_count(self, env_vars, mock_session_factory):
        """check_reminders() entry point delegates to _check_reminders and returns result."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()

        expected_result = {"status": "ok", "reminders_sent": 3}

        with patch.object(
            h, "_check_reminders", new_callable=AsyncMock, return_value=expected_result
        ):
            result = h.check_reminders({}, context=None)

        assert result == expected_result
        assert result["reminders_sent"] == 3


# ---------------------------------------------------------------------------
# 8. test_reminder_sends_whatsapp
# ---------------------------------------------------------------------------
class TestReminderSendsWhatsApp:
    async def test_reminder_sends_whatsapp(
        self,
        env_vars,
        sample_asset,
        sample_magic_link,
        sample_version,
        mock_session,
        mock_session_factory,
    ):
        """WhatsApp reminder is sent alongside email when client has phone."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()
        h._whatsapp_service = MagicMock()

        sample_asset.client.whatsapp_phone = "5541999887766"

        h._email_service.send_reminder_email = AsyncMock(
            return_value={"MessageId": "reminder_wa"}
        )
        h._whatsapp_service.send_reminder_message = AsyncMock(
            return_value={"messages": [{"id": "wamid.rem"}]}
        )
        h._media_service.generate_presigned_url = MagicMock(
            return_value="https://presigned.url/thumb"
        )

        # Only return asset for first threshold
        call_count = 0

        async def _pending_side_effect(session, days):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [sample_asset]
            return []

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                side_effect=_pending_side_effect,
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "_get_latest_version",
                new_callable=AsyncMock,
                return_value=sample_version,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        assert result["status"] == "ok"
        assert result["reminders_sent"] == 1
        h._email_service.send_reminder_email.assert_awaited_once()
        h._whatsapp_service.send_reminder_message.assert_awaited_once()


# ---------------------------------------------------------------------------
# 9. test_reminder_whatsapp_failure_continues
# ---------------------------------------------------------------------------
class TestReminderWhatsAppFailureContinues:
    async def test_reminder_whatsapp_failure_continues(
        self,
        env_vars,
        sample_asset,
        sample_magic_link,
        sample_version,
        mock_session,
        mock_session_factory,
    ):
        """WhatsApp failure does not prevent email or break the loop."""
        import lambdas.approval_reminder.handler as h

        h._session_factory = mock_session_factory
        h._email_service = MagicMock()
        h._media_service = MagicMock()
        h._whatsapp_service = MagicMock()

        sample_asset.client.whatsapp_phone = "5541999887766"

        h._email_service.send_reminder_email = AsyncMock(
            return_value={"MessageId": "reminder_ok"}
        )
        h._whatsapp_service.send_reminder_message = AsyncMock(
            side_effect=Exception("WhatsApp API down")
        )
        h._media_service.generate_presigned_url = MagicMock(
            return_value="https://presigned.url/thumb"
        )

        call_count = 0

        async def _pending_side_effect(session, days):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [sample_asset]
            return []

        with (
            patch.object(
                h,
                "get_pending_assets_older_than",
                new_callable=AsyncMock,
                side_effect=_pending_side_effect,
            ),
            patch.object(
                h, "_was_reminded_today", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                h,
                "_find_active_magic_link",
                new_callable=AsyncMock,
                return_value=sample_magic_link,
            ),
            patch.object(
                h,
                "_get_latest_version",
                new_callable=AsyncMock,
                return_value=sample_version,
            ),
            patch.object(h, "log_event", new_callable=AsyncMock),
        ):
            result = await h._check_reminders({})

        # Still succeeds despite WhatsApp failure
        assert result["status"] == "ok"
        assert result["reminders_sent"] == 1
        h._email_service.send_reminder_email.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
