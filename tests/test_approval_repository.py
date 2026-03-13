"""Tests for the approval portal repository layer.

Uses mock AsyncSession to verify query construction, object creation,
and session interactions without needing a real database connection.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.approval.models import (
    ApprovalAsset,
    ApprovalComment,
    ApprovalDecision,
    ApprovalEvent,
    AssetVersion,
    Client,
    MagicLink,
)
from src.approval.repository import (
    MAGIC_LINK_TTL_DAYS,
    add_comment,
    create_asset,
    create_magic_link,
    create_version,
    deactivate_magic_links,
    get_asset_by_task_id,
    get_asset_with_relations,
    get_client_by_list_id,
    get_client_by_slug,
    get_pending_assets_older_than,
    log_event,
    save_decision,
    update_asset_status,
    validate_magic_link,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_session():
    """Create a mock AsyncSession with common methods pre-configured."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture()
def sample_client():
    """Create a sample Client instance."""
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
def sample_asset():
    """Create a sample ApprovalAsset instance."""
    asset = ApprovalAsset(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        clickup_task_id="task_abc123",
        title="Instagram Post - ClientAlpha - Mar 2026",
        description="Post for social media campaign",
        status="pending_review",
        current_version=1,
    )
    return asset


@pytest.fixture()
def sample_version(sample_asset):
    """Create a sample AssetVersion instance."""
    return AssetVersion(
        id=uuid.uuid4(),
        asset_id=sample_asset.id,
        version_number=1,
        file_type="image",
        file_format="png",
        original_url="https://s3.example.com/image.png",
    )


@pytest.fixture()
def sample_magic_link(sample_asset, sample_client):
    """Create a sample MagicLink instance."""
    return MagicLink(
        id=uuid.uuid4(),
        token="valid-token-abc123",
        asset_id=sample_asset.id,
        client_id=sample_client.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=True,
        access_count=0,
    )


def _mock_scalar_result(value):
    """Helper: make session.execute return a result whose scalar_one_or_none() gives *value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values):
    """Helper: make session.execute return a result whose scalars().all() gives *values*."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    return result


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class TestGetClientByListId:
    async def test_found(self, mock_session, sample_client):
        mock_session.execute.return_value = _mock_scalar_result(sample_client)

        result = await get_client_by_list_id(mock_session, "901234567")

        assert result is sample_client
        mock_session.execute.assert_awaited_once()

    async def test_not_found(self, mock_session):
        mock_session.execute.return_value = _mock_scalar_result(None)

        result = await get_client_by_list_id(mock_session, "nonexistent")

        assert result is None
        mock_session.execute.assert_awaited_once()


class TestGetClientBySlug:
    async def test_found(self, mock_session, sample_client):
        mock_session.execute.return_value = _mock_scalar_result(sample_client)

        result = await get_client_by_slug(mock_session, "client_alpha")

        assert result is sample_client
        mock_session.execute.assert_awaited_once()

    async def test_not_found(self, mock_session):
        mock_session.execute.return_value = _mock_scalar_result(None)

        result = await get_client_by_slug(mock_session, "nonexistent")

        assert result is None
        mock_session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
class TestCreateAsset:
    async def test_create_asset(self, mock_session):
        client_id = uuid.uuid4()

        asset = await create_asset(
            mock_session,
            client_id=client_id,
            clickup_task_id="task_xyz",
            title="Instagram Post - ClientDelta",
            description="Campaign post",
        )

        assert isinstance(asset, ApprovalAsset)
        assert asset.client_id == client_id
        assert asset.clickup_task_id == "task_xyz"
        assert asset.title == "Instagram Post - ClientDelta"
        assert asset.description == "Campaign post"
        mock_session.add.assert_called_once_with(asset)
        mock_session.flush.assert_awaited_once()

    async def test_create_asset_no_description(self, mock_session):
        asset = await create_asset(
            mock_session,
            client_id=uuid.uuid4(),
            clickup_task_id="task_123",
            title="Post without desc",
        )

        assert asset.description is None
        mock_session.add.assert_called_once()


class TestGetAssetByTaskId:
    async def test_found(self, mock_session, sample_asset):
        mock_session.execute.return_value = _mock_scalar_result(sample_asset)

        result = await get_asset_by_task_id(mock_session, "task_abc123")

        assert result is sample_asset
        mock_session.execute.assert_awaited_once()

    async def test_not_found(self, mock_session):
        mock_session.execute.return_value = _mock_scalar_result(None)

        result = await get_asset_by_task_id(mock_session, "nonexistent_task")

        assert result is None


class TestGetAssetWithRelations:
    async def test_found_with_relations(self, mock_session, sample_asset):
        mock_session.execute.return_value = _mock_scalar_result(sample_asset)

        result = await get_asset_with_relations(mock_session, sample_asset.id)

        assert result is sample_asset
        mock_session.execute.assert_awaited_once()
        # Verify selectinload was used (the statement is constructed with options)
        executed_stmt = mock_session.execute.call_args[0][0]
        assert executed_stmt is not None

    async def test_not_found(self, mock_session):
        mock_session.execute.return_value = _mock_scalar_result(None)
        asset_id = uuid.uuid4()

        result = await get_asset_with_relations(mock_session, asset_id)

        assert result is None


class TestUpdateAssetStatus:
    async def test_update_status_only(self, mock_session):
        asset_id = uuid.uuid4()

        await update_asset_status(mock_session, asset_id, "approved")

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_update_status_with_version(self, mock_session):
        asset_id = uuid.uuid4()

        await update_asset_status(mock_session, asset_id, "changes_requested", version=2)

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
class TestCreateVersion:
    async def test_create_version_required_fields(self, mock_session):
        asset_id = uuid.uuid4()

        version = await create_version(
            mock_session,
            asset_id=asset_id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="https://s3.example.com/v1.png",
        )

        assert isinstance(version, AssetVersion)
        assert version.asset_id == asset_id
        assert version.version_number == 1
        assert version.file_type == "image"
        assert version.file_format == "png"
        assert version.original_url == "https://s3.example.com/v1.png"
        assert version.thumbnail_url is None
        assert version.file_size_bytes is None
        assert version.width is None
        assert version.height is None
        assert version.duration_seconds is None
        assert version.uploaded_by is None
        mock_session.add.assert_called_once_with(version)
        mock_session.flush.assert_awaited_once()

    async def test_create_version_all_fields(self, mock_session):
        asset_id = uuid.uuid4()

        version = await create_version(
            mock_session,
            asset_id=asset_id,
            version_number=2,
            file_type="video",
            file_format="mp4",
            original_url="https://s3.example.com/v2.mp4",
            thumbnail_url="https://s3.example.com/v2_thumb.jpg",
            file_size_bytes=10485760,
            width=1920,
            height=1080,
            duration_seconds=30.5,
            uploaded_by="Pedro H. Eger",
        )

        assert version.thumbnail_url == "https://s3.example.com/v2_thumb.jpg"
        assert version.file_size_bytes == 10485760
        assert version.width == 1920
        assert version.height == 1080
        assert version.duration_seconds == 30.5
        assert version.uploaded_by == "Pedro H. Eger"


# ---------------------------------------------------------------------------
# Magic Links
# ---------------------------------------------------------------------------
class TestCreateMagicLink:
    async def test_create_magic_link(self, mock_session):
        asset_id = uuid.uuid4()
        client_id = uuid.uuid4()

        link = await create_magic_link(
            mock_session, asset_id=asset_id, client_id=client_id
        )

        assert isinstance(link, MagicLink)
        assert link.asset_id == asset_id
        assert link.client_id == client_id
        # Token should be non-empty and URL-safe
        assert isinstance(link.token, str)
        assert len(link.token) > 0
        # Expires at should be approximately 7 days in the future
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(days=MAGIC_LINK_TTL_DAYS)
        assert abs((link.expires_at - expected_expiry).total_seconds()) < 5
        mock_session.add.assert_called_once_with(link)
        mock_session.flush.assert_awaited_once()

    async def test_create_magic_link_unique_tokens(self, mock_session):
        """Each call generates a different token."""
        asset_id = uuid.uuid4()
        client_id = uuid.uuid4()

        link1 = await create_magic_link(mock_session, asset_id=asset_id, client_id=client_id)
        link2 = await create_magic_link(mock_session, asset_id=asset_id, client_id=client_id)

        assert link1.token != link2.token


class TestValidateMagicLink:
    async def test_valid_link(self, mock_session, sample_magic_link):
        mock_session.execute.return_value = _mock_scalar_result(sample_magic_link)

        result = await validate_magic_link(mock_session, "valid-token-abc123")

        assert result is sample_magic_link
        assert sample_magic_link.access_count == 1
        assert sample_magic_link.accessed_at is not None
        mock_session.flush.assert_awaited_once()

    async def test_valid_link_increments_access_count(self, mock_session, sample_magic_link):
        sample_magic_link.access_count = 3
        mock_session.execute.return_value = _mock_scalar_result(sample_magic_link)

        result = await validate_magic_link(mock_session, "valid-token-abc123")

        assert result.access_count == 4

    async def test_expired_link(self, mock_session):
        """Expired link returns None (filtered by query)."""
        mock_session.execute.return_value = _mock_scalar_result(None)

        result = await validate_magic_link(mock_session, "expired-token")

        assert result is None
        mock_session.flush.assert_not_awaited()

    async def test_inactive_link(self, mock_session):
        """Inactive link returns None (filtered by query)."""
        mock_session.execute.return_value = _mock_scalar_result(None)

        result = await validate_magic_link(mock_session, "deactivated-token")

        assert result is None
        mock_session.flush.assert_not_awaited()


class TestDeactivateMagicLinks:
    async def test_deactivate(self, mock_session):
        asset_id = uuid.uuid4()

        await deactivate_magic_links(mock_session, asset_id)

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class TestAddComment:
    async def test_add_comment(self, mock_session):
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()

        comment = await add_comment(
            mock_session,
            asset_id=asset_id,
            version_id=version_id,
            author_type="client",
            author_name="Maria Souza",
            content="Precisa ajustar as cores do logo",
        )

        assert isinstance(comment, ApprovalComment)
        assert comment.asset_id == asset_id
        assert comment.version_id == version_id
        assert comment.author_type == "client"
        assert comment.author_name == "Maria Souza"
        assert comment.content == "Precisa ajustar as cores do logo"
        mock_session.add.assert_called_once_with(comment)
        mock_session.flush.assert_awaited_once()

    async def test_add_comment_without_version(self, mock_session):
        comment = await add_comment(
            mock_session,
            asset_id=uuid.uuid4(),
            version_id=None,
            author_type="team",
            author_name="Pedro",
            content="General feedback",
        )

        assert comment.version_id is None


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
class TestSaveDecision:
    async def test_save_approved_decision(self, mock_session):
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()

        decision = await save_decision(
            mock_session,
            asset_id=asset_id,
            version_id=version_id,
            decision="approved",
            decided_by="Cliente ClientAlpha",
        )

        assert isinstance(decision, ApprovalDecision)
        assert decision.asset_id == asset_id
        assert decision.version_id == version_id
        assert decision.decision == "approved"
        assert decision.decided_by == "Cliente ClientAlpha"
        assert decision.comment is None
        mock_session.add.assert_called_once_with(decision)
        mock_session.flush.assert_awaited_once()

    async def test_save_changes_requested_with_comment(self, mock_session):
        decision = await save_decision(
            mock_session,
            asset_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            decision="changes_requested",
            decided_by="Account Manager B",
            comment="Preciso de alteracoes no texto do banner",
        )

        assert decision.decision == "changes_requested"
        assert decision.comment == "Preciso de alteracoes no texto do banner"


# ---------------------------------------------------------------------------
# Events (Audit Log)
# ---------------------------------------------------------------------------
class TestLogEvent:
    async def test_log_event_with_actor_and_metadata(self, mock_session):
        asset_id = uuid.uuid4()
        meta = {"old_status": "pending_review", "new_status": "approved"}

        event = await log_event(
            mock_session,
            asset_id=asset_id,
            event_type="status_changed",
            actor="client@client_alpha.com",
            metadata=meta,
        )

        assert isinstance(event, ApprovalEvent)
        assert event.asset_id == asset_id
        assert event.event_type == "status_changed"
        assert event.actor == "client@client_alpha.com"
        # Verify metadata_ (underscore) attribute is set correctly
        assert event.metadata_ == meta
        assert event.metadata_["old_status"] == "pending_review"
        assert event.metadata_["new_status"] == "approved"
        mock_session.add.assert_called_once_with(event)
        mock_session.flush.assert_awaited_once()

    async def test_log_event_actor_defaults_to_system(self, mock_session):
        """When actor is None, it defaults to 'system'."""
        event = await log_event(
            mock_session,
            asset_id=uuid.uuid4(),
            event_type="asset_created",
            actor=None,
        )

        assert event.actor == "system"

    async def test_log_event_no_actor_kwarg_defaults_to_system(self, mock_session):
        """When actor kwarg is omitted entirely, it defaults to 'system'."""
        event = await log_event(
            mock_session,
            asset_id=uuid.uuid4(),
            event_type="link_generated",
        )

        assert event.actor == "system"

    async def test_log_event_no_metadata(self, mock_session):
        event = await log_event(
            mock_session,
            asset_id=uuid.uuid4(),
            event_type="link_accessed",
            actor="visitor",
        )

        assert event.metadata_ is None

    async def test_log_event_metadata_uses_underscore_attribute(self, mock_session):
        """Ensure we use metadata_ (Python attr) not metadata (which would be lost)."""
        meta = {"key": "value"}

        event = await log_event(
            mock_session,
            asset_id=uuid.uuid4(),
            event_type="test",
            metadata=meta,
        )

        # The attribute in Python is metadata_ — verify it's set
        assert hasattr(event, "metadata_")
        assert event.metadata_ == {"key": "value"}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
class TestGetPendingAssetsOlderThan:
    async def test_returns_old_pending_assets(self, mock_session):
        old_asset = ApprovalAsset(
            id=uuid.uuid4(),
            client_id=uuid.uuid4(),
            clickup_task_id="old_task",
            title="Old pending asset",
            status="pending_review",
        )
        mock_session.execute.return_value = _mock_scalars_result([old_asset])

        result = await get_pending_assets_older_than(mock_session, 3)

        assert len(result) == 1
        assert result[0] is old_asset
        mock_session.execute.assert_awaited_once()

    async def test_returns_empty_when_none_match(self, mock_session):
        mock_session.execute.return_value = _mock_scalars_result([])

        result = await get_pending_assets_older_than(mock_session, 3)

        assert result == []

    async def test_returns_multiple_assets(self, mock_session):
        assets = [
            ApprovalAsset(
                id=uuid.uuid4(),
                client_id=uuid.uuid4(),
                clickup_task_id=f"task_{i}",
                title=f"Asset {i}",
                status="pending_review",
            )
            for i in range(3)
        ]
        mock_session.execute.return_value = _mock_scalars_result(assets)

        result = await get_pending_assets_older_than(mock_session, 5)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
class TestConstants:
    def test_magic_link_ttl_days(self):
        assert MAGIC_LINK_TTL_DAYS == 7
