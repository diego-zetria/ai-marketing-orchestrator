"""Tests for the approval portal ORM models.

Verifies all 7 models: Client (extended), ApprovalAsset, AssetVersion,
MagicLink, ApprovalComment, ApprovalDecision, ApprovalEvent.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import inspect

from src.approval.models import (
    ApprovalAsset,
    ApprovalComment,
    ApprovalDecision,
    ApprovalEvent,
    AssetVersion,
    Client,
    MagicLink,
)


# ---------------------------------------------------------------------------
# Client (extended with portal columns)
# ---------------------------------------------------------------------------
class TestClientPortalColumns:
    """Verify the 3 portal-specific columns added to Client."""

    def test_slug_column_exists(self):
        mapper = inspect(Client)
        col_names = [col.name for col in mapper.columns]
        assert "slug" in col_names

    def test_email_column_exists(self):
        mapper = inspect(Client)
        col_names = [col.name for col in mapper.columns]
        assert "email" in col_names

    def test_logo_url_column_exists(self):
        mapper = inspect(Client)
        col_names = [col.name for col in mapper.columns]
        assert "logo_url" in col_names

    def test_slug_is_unique(self):
        mapper = inspect(Client)
        col = mapper.columns["slug"]
        assert col.unique is True

    def test_slug_is_nullable(self):
        mapper = inspect(Client)
        col = mapper.columns["slug"]
        assert col.nullable is True

    def test_email_is_nullable(self):
        mapper = inspect(Client)
        col = mapper.columns["email"]
        assert col.nullable is True

    def test_logo_url_is_nullable(self):
        mapper = inspect(Client)
        col = mapper.columns["logo_url"]
        assert col.nullable is True

    def test_client_with_portal_columns(self):
        client = Client(
            name="client_alpha",
            display_name="ClientAlpha",
            slug="client_alpha",
            email="contato@client_alpha.com",
            logo_url="https://example.com/client_alpha.png",
        )
        assert client.slug == "client_alpha"
        assert client.email == "contato@client_alpha.com"
        assert client.logo_url == "https://example.com/client_alpha.png"

    def test_client_portal_columns_default_none(self):
        client = Client(name="test", display_name="Test")
        assert client.slug is None
        assert client.email is None
        assert client.logo_url is None

    def test_client_tablename(self):
        assert Client.__tablename__ == "clients"

    def test_client_schema(self):
        assert Client.__table__.schema == "marketing_bot"


# ---------------------------------------------------------------------------
# ApprovalAsset
# ---------------------------------------------------------------------------
class TestApprovalAsset:
    def test_tablename(self):
        assert ApprovalAsset.__tablename__ == "approval_assets"

    def test_schema(self):
        assert ApprovalAsset.__table__.schema == "marketing_bot"

    def test_creation_with_required_fields(self):
        client_id = uuid.uuid4()
        asset = ApprovalAsset(
            client_id=client_id,
            clickup_task_id="abc123",
            title="Instagram Post - ClientAlpha",
        )
        assert asset.client_id == client_id
        assert asset.clickup_task_id == "abc123"
        assert asset.title == "Instagram Post - ClientAlpha"

    def test_status_default(self):
        mapper = inspect(ApprovalAsset)
        col = mapper.columns["status"]
        assert col.default.arg == "pending_review"

    def test_current_version_default(self):
        mapper = inspect(ApprovalAsset)
        col = mapper.columns["current_version"]
        assert col.default.arg == 1

    def test_nullable_description(self):
        asset = ApprovalAsset(
            client_id=uuid.uuid4(),
            clickup_task_id="abc123",
            title="Test",
        )
        assert asset.description is None

    def test_uuid_primary_key(self):
        explicit_id = uuid.uuid4()
        asset = ApprovalAsset(
            id=explicit_id,
            client_id=uuid.uuid4(),
            clickup_task_id="abc123",
            title="Test",
        )
        assert asset.id == explicit_id

    def test_client_id_indexed(self):
        mapper = inspect(ApprovalAsset)
        col = mapper.columns["client_id"]
        assert col.index is True

    def test_clickup_task_id_indexed(self):
        mapper = inspect(ApprovalAsset)
        col = mapper.columns["clickup_task_id"]
        assert col.index is True

    def test_foreign_key_to_clients(self):
        mapper = inspect(ApprovalAsset)
        col = mapper.columns["client_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.clients.id"

    def test_relationships_defined(self):
        mapper = inspect(ApprovalAsset)
        rel_names = {r.key for r in mapper.relationships}
        assert "client" in rel_names
        assert "versions" in rel_names
        assert "comments" in rel_names
        assert "decisions" in rel_names
        assert "events" in rel_names
        assert "magic_links" in rel_names


# ---------------------------------------------------------------------------
# AssetVersion
# ---------------------------------------------------------------------------
class TestAssetVersion:
    def test_tablename(self):
        assert AssetVersion.__tablename__ == "asset_versions"

    def test_schema(self):
        assert AssetVersion.__table__.schema == "marketing_bot"

    def test_creation_with_required_fields(self):
        asset_id = uuid.uuid4()
        version = AssetVersion(
            asset_id=asset_id,
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="https://s3.example.com/image.png",
        )
        assert version.asset_id == asset_id
        assert version.version_number == 1
        assert version.file_type == "image"
        assert version.file_format == "png"
        assert version.original_url == "https://s3.example.com/image.png"

    def test_nullable_optional_fields(self):
        version = AssetVersion(
            asset_id=uuid.uuid4(),
            version_number=1,
            file_type="image",
            file_format="png",
            original_url="https://example.com/img.png",
        )
        assert version.thumbnail_url is None
        assert version.file_size_bytes is None
        assert version.width is None
        assert version.height is None
        assert version.duration_seconds is None
        assert version.uploaded_by is None

    def test_with_media_dimensions(self):
        version = AssetVersion(
            asset_id=uuid.uuid4(),
            version_number=1,
            file_type="image",
            file_format="jpg",
            original_url="https://example.com/photo.jpg",
            file_size_bytes=2048576,
            width=1920,
            height=1080,
        )
        assert version.file_size_bytes == 2048576
        assert version.width == 1920
        assert version.height == 1080

    def test_with_video_duration(self):
        version = AssetVersion(
            asset_id=uuid.uuid4(),
            version_number=1,
            file_type="video",
            file_format="mp4",
            original_url="https://example.com/video.mp4",
            duration_seconds=30.5,
        )
        assert version.duration_seconds == 30.5

    def test_foreign_key_to_approval_assets(self):
        mapper = inspect(AssetVersion)
        col = mapper.columns["asset_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.approval_assets.id"

    def test_unique_constraint_asset_version(self):
        """Verify the unique constraint on (asset_id, version_number)."""
        table = AssetVersion.__table__
        unique_constraints = [
            c for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1
        ]
        col_sets = [
            {col.name for col in c.columns} for c in unique_constraints
        ]
        assert {"asset_id", "version_number"} in col_sets

    def test_relationships_defined(self):
        mapper = inspect(AssetVersion)
        rel_names = {r.key for r in mapper.relationships}
        assert "asset" in rel_names
        assert "comments" in rel_names
        assert "decisions" in rel_names


# ---------------------------------------------------------------------------
# MagicLink
# ---------------------------------------------------------------------------
class TestMagicLink:
    def test_tablename(self):
        assert MagicLink.__tablename__ == "magic_links"

    def test_schema(self):
        assert MagicLink.__table__.schema == "marketing_bot"

    def test_creation_with_required_fields(self):
        asset_id = uuid.uuid4()
        client_id = uuid.uuid4()
        expires = datetime.now(timezone.utc)
        link = MagicLink(
            token="abc-def-123",
            asset_id=asset_id,
            client_id=client_id,
            expires_at=expires,
        )
        assert link.token == "abc-def-123"
        assert link.asset_id == asset_id
        assert link.client_id == client_id
        assert link.expires_at == expires

    def test_token_is_unique(self):
        mapper = inspect(MagicLink)
        col = mapper.columns["token"]
        assert col.unique is True

    def test_access_count_default(self):
        mapper = inspect(MagicLink)
        col = mapper.columns["access_count"]
        assert col.default.arg == 0

    def test_is_active_default(self):
        mapper = inspect(MagicLink)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_accessed_at_nullable(self):
        link = MagicLink(
            token="tok-1",
            asset_id=uuid.uuid4(),
            client_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc),
        )
        assert link.accessed_at is None

    def test_foreign_key_to_approval_assets(self):
        mapper = inspect(MagicLink)
        col = mapper.columns["asset_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.approval_assets.id"

    def test_foreign_key_to_clients(self):
        mapper = inspect(MagicLink)
        col = mapper.columns["client_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.clients.id"

    def test_relationships_defined(self):
        mapper = inspect(MagicLink)
        rel_names = {r.key for r in mapper.relationships}
        assert "asset" in rel_names
        assert "client" in rel_names


# ---------------------------------------------------------------------------
# ApprovalComment
# ---------------------------------------------------------------------------
class TestApprovalComment:
    def test_tablename(self):
        assert ApprovalComment.__tablename__ == "approval_comments"

    def test_schema(self):
        assert ApprovalComment.__table__.schema == "marketing_bot"

    def test_creation_with_required_fields(self):
        asset_id = uuid.uuid4()
        comment = ApprovalComment(
            asset_id=asset_id,
            author_type="client",
            author_name="Maria Souza",
            content="Precisa ajustar as cores",
        )
        assert comment.asset_id == asset_id
        assert comment.author_type == "client"
        assert comment.author_name == "Maria Souza"
        assert comment.content == "Precisa ajustar as cores"

    def test_version_id_nullable(self):
        comment = ApprovalComment(
            asset_id=uuid.uuid4(),
            author_type="client",
            author_name="Test",
            content="Test comment",
        )
        assert comment.version_id is None

    def test_with_version_id(self):
        version_id = uuid.uuid4()
        comment = ApprovalComment(
            asset_id=uuid.uuid4(),
            version_id=version_id,
            author_type="team",
            author_name="Pedro",
            content="Updated design",
        )
        assert comment.version_id == version_id

    def test_foreign_key_to_approval_assets(self):
        mapper = inspect(ApprovalComment)
        col = mapper.columns["asset_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.approval_assets.id"

    def test_foreign_key_to_asset_versions(self):
        mapper = inspect(ApprovalComment)
        col = mapper.columns["version_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.asset_versions.id"

    def test_asset_id_indexed(self):
        mapper = inspect(ApprovalComment)
        col = mapper.columns["asset_id"]
        assert col.index is True

    def test_relationships_defined(self):
        mapper = inspect(ApprovalComment)
        rel_names = {r.key for r in mapper.relationships}
        assert "asset" in rel_names
        assert "version" in rel_names


# ---------------------------------------------------------------------------
# ApprovalDecision
# ---------------------------------------------------------------------------
class TestApprovalDecision:
    def test_tablename(self):
        assert ApprovalDecision.__tablename__ == "approval_decisions"

    def test_schema(self):
        assert ApprovalDecision.__table__.schema == "marketing_bot"

    def test_creation_approved(self):
        asset_id = uuid.uuid4()
        version_id = uuid.uuid4()
        decision = ApprovalDecision(
            asset_id=asset_id,
            version_id=version_id,
            decision="approved",
            decided_by="Maria Souza",
        )
        assert decision.asset_id == asset_id
        assert decision.version_id == version_id
        assert decision.decision == "approved"
        assert decision.decided_by == "Maria Souza"

    def test_creation_changes_requested(self):
        decision = ApprovalDecision(
            asset_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            decision="changes_requested",
            comment="Preciso de alteracoes no texto",
            decided_by="Cliente ClientAlpha",
        )
        assert decision.decision == "changes_requested"
        assert decision.comment == "Preciso de alteracoes no texto"

    def test_comment_nullable(self):
        decision = ApprovalDecision(
            asset_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            decision="approved",
            decided_by="Test",
        )
        assert decision.comment is None

    def test_foreign_key_to_approval_assets(self):
        mapper = inspect(ApprovalDecision)
        col = mapper.columns["asset_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.approval_assets.id"

    def test_foreign_key_to_asset_versions(self):
        mapper = inspect(ApprovalDecision)
        col = mapper.columns["version_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.asset_versions.id"

    def test_asset_id_indexed(self):
        mapper = inspect(ApprovalDecision)
        col = mapper.columns["asset_id"]
        assert col.index is True

    def test_relationships_defined(self):
        mapper = inspect(ApprovalDecision)
        rel_names = {r.key for r in mapper.relationships}
        assert "asset" in rel_names
        assert "version" in rel_names


# ---------------------------------------------------------------------------
# ApprovalEvent
# ---------------------------------------------------------------------------
class TestApprovalEvent:
    def test_tablename(self):
        assert ApprovalEvent.__tablename__ == "approval_events"

    def test_schema(self):
        assert ApprovalEvent.__table__.schema == "marketing_bot"

    def test_creation_with_required_fields(self):
        asset_id = uuid.uuid4()
        event = ApprovalEvent(
            asset_id=asset_id,
            event_type="asset_created",
            actor="system",
        )
        assert event.asset_id == asset_id
        assert event.event_type == "asset_created"
        assert event.actor == "system"

    def test_metadata_jsonb_column(self):
        event = ApprovalEvent(
            asset_id=uuid.uuid4(),
            event_type="status_changed",
            actor="client@email.com",
            metadata_={"old_status": "pending_review", "new_status": "approved"},
        )
        assert event.metadata_["old_status"] == "pending_review"
        assert event.metadata_["new_status"] == "approved"

    def test_metadata_nullable(self):
        event = ApprovalEvent(
            asset_id=uuid.uuid4(),
            event_type="link_accessed",
            actor="client",
        )
        assert event.metadata_ is None

    def test_metadata_column_name_in_db(self):
        """The column is named 'metadata' in the DB but 'metadata_' in Python."""
        mapper = inspect(ApprovalEvent)
        col = mapper.columns["metadata_"]
        assert col.name == "metadata"

    def test_event_type_indexed(self):
        mapper = inspect(ApprovalEvent)
        col = mapper.columns["event_type"]
        assert col.index is True

    def test_asset_id_indexed(self):
        mapper = inspect(ApprovalEvent)
        col = mapper.columns["asset_id"]
        assert col.index is True

    def test_foreign_key_to_approval_assets(self):
        mapper = inspect(ApprovalEvent)
        col = mapper.columns["asset_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.target_fullname == "marketing_bot.approval_assets.id"

    def test_relationships_defined(self):
        mapper = inspect(ApprovalEvent)
        rel_names = {r.key for r in mapper.relationships}
        assert "asset" in rel_names


# ---------------------------------------------------------------------------
# Cross-model relationship consistency
# ---------------------------------------------------------------------------
class TestRelationshipConsistency:
    """Verify back_populates relationships are wired correctly across models."""

    def test_client_has_approval_assets_backref(self):
        """Client gets 'approval_assets' via backref from ApprovalAsset."""
        mapper = inspect(Client)
        rel_names = {r.key for r in mapper.relationships}
        assert "approval_assets" in rel_names

    def test_client_has_magic_links_backref(self):
        """Client gets 'magic_links' via backref from MagicLink."""
        mapper = inspect(Client)
        rel_names = {r.key for r in mapper.relationships}
        assert "magic_links" in rel_names

    def test_approval_asset_versions_back_populates(self):
        mapper = inspect(ApprovalAsset)
        versions_rel = next(r for r in mapper.relationships if r.key == "versions")
        assert versions_rel.back_populates == "asset"

    def test_asset_version_asset_back_populates(self):
        mapper = inspect(AssetVersion)
        asset_rel = next(r for r in mapper.relationships if r.key == "asset")
        assert asset_rel.back_populates == "versions"

    def test_approval_asset_comments_back_populates(self):
        mapper = inspect(ApprovalAsset)
        comments_rel = next(r for r in mapper.relationships if r.key == "comments")
        assert comments_rel.back_populates == "asset"

    def test_approval_comment_asset_back_populates(self):
        mapper = inspect(ApprovalComment)
        asset_rel = next(r for r in mapper.relationships if r.key == "asset")
        assert asset_rel.back_populates == "comments"

    def test_approval_asset_decisions_back_populates(self):
        mapper = inspect(ApprovalAsset)
        decisions_rel = next(r for r in mapper.relationships if r.key == "decisions")
        assert decisions_rel.back_populates == "asset"

    def test_approval_asset_events_back_populates(self):
        mapper = inspect(ApprovalAsset)
        events_rel = next(r for r in mapper.relationships if r.key == "events")
        assert events_rel.back_populates == "asset"

    def test_approval_asset_magic_links_back_populates(self):
        mapper = inspect(ApprovalAsset)
        ml_rel = next(r for r in mapper.relationships if r.key == "magic_links")
        assert ml_rel.back_populates == "asset"


# ---------------------------------------------------------------------------
# All models share the marketing_bot schema
# ---------------------------------------------------------------------------
class TestAllModelsSchema:
    """Every approval model must use the marketing_bot schema."""

    def test_all_tables_use_marketing_bot_schema(self):
        models = [
            Client,
            ApprovalAsset,
            AssetVersion,
            MagicLink,
            ApprovalComment,
            ApprovalDecision,
            ApprovalEvent,
        ]
        for model in models:
            assert model.__table__.schema == "marketing_bot", (
                f"{model.__name__}.__table__.schema = {model.__table__.schema!r}, "
                f"expected 'marketing_bot'"
            )

    def test_all_models_have_uuid_primary_key(self):
        """All approval models use UUID primary keys."""
        models = [
            ApprovalAsset,
            AssetVersion,
            MagicLink,
            ApprovalComment,
            ApprovalDecision,
            ApprovalEvent,
        ]
        for model in models:
            mapper = inspect(model)
            pk_cols = list(mapper.primary_key)
            assert len(pk_cols) == 1, f"{model.__name__} should have exactly 1 PK column"
            pk_col = pk_cols[0]
            assert "UUID" in str(pk_col.type), (
                f"{model.__name__} PK type is {pk_col.type}, expected UUID"
            )
