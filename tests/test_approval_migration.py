"""Tests for the approval portal migration (c1a2b3d4e5f6).

Validates that upgrade/downgrade operations are correct by inspecting
the migration's op directives without requiring a live database.
"""
import importlib
import importlib.util
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def migration_module():
    """Load the migration module dynamically."""
    spec = importlib.util.spec_from_file_location(
        "c1a2b3d4e5f6_add_approval_portal_tables",
        "alembic/versions/c1a2b3d4e5f6_add_approval_portal_tables.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mock_op():
    return MagicMock()


@pytest.fixture
def upgrade_ops(migration_module, mock_op):
    """Run upgrade() with mocked op, return the mock for inspection."""
    with patch.object(migration_module, "op", mock_op):
        migration_module.upgrade()
    return mock_op


@pytest.fixture
def downgrade_ops(migration_module, mock_op):
    """Run downgrade() with mocked op, return the mock for inspection."""
    with patch.object(migration_module, "op", mock_op):
        migration_module.downgrade()
    return mock_op


# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

SCHEMA = "marketing_bot"

# The 6 new tables created
CREATED_TABLES = [
    "approval_assets",
    "asset_versions",
    "magic_links",
    "approval_comments",
    "approval_decisions",
    "approval_events",
]


class TestMigrationMetadata:
    def test_revision_id(self, migration_module):
        assert migration_module.revision == "c1a2b3d4e5f6"

    def test_down_revision_points_to_head(self, migration_module):
        assert migration_module.down_revision == "b4d8e2f1a390"

    def test_branch_labels_is_none(self, migration_module):
        assert migration_module.branch_labels is None

    def test_depends_on_is_none(self, migration_module):
        assert migration_module.depends_on is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_create_table_call(mock_op, table_name):
    for c in mock_op.create_table.call_args_list:
        if c[0][0] == table_name:
            return c
    raise AssertionError(f"create_table({table_name}) not found")


def _extract_columns(table_call):
    import sqlalchemy as sa

    return [a for a in table_call[0] if isinstance(a, sa.Column)]


def _extract_fk_targets(table_call):
    """Extract FK target column specs (e.g. 'marketing_bot.clients.id') from create_table call."""
    import sqlalchemy as sa

    targets = []
    for a in table_call[0]:
        if isinstance(a, sa.ForeignKeyConstraint):
            for elem in a.elements:
                targets.append(elem.target_fullname)
    return targets


def _extract_unique_constraint_names(table_call):
    import sqlalchemy as sa

    names = []
    for a in table_call[0]:
        if isinstance(a, sa.UniqueConstraint) and a.name:
            names.append(a.name)
    return names


def _get_index_names(mock_op):
    return [c[0][0] for c in mock_op.create_index.call_args_list]


# ---------------------------------------------------------------------------
# Upgrade — table creation
# ---------------------------------------------------------------------------


class TestUpgradeClientColumns:
    """Validate portal columns added to existing clients table."""

    def test_adds_slug_column(self, upgrade_ops):
        add_col_calls = [
            c for c in upgrade_ops.add_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1].name for c in add_col_calls]
        assert "slug" in col_names

    def test_adds_email_column(self, upgrade_ops):
        add_col_calls = [
            c for c in upgrade_ops.add_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1].name for c in add_col_calls]
        assert "email" in col_names

    def test_adds_logo_url_column(self, upgrade_ops):
        add_col_calls = [
            c for c in upgrade_ops.add_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1].name for c in add_col_calls]
        assert "logo_url" in col_names

    def test_slug_unique_constraint(self, upgrade_ops):
        create_uq_calls = upgrade_ops.create_unique_constraint.call_args_list
        uq_names = [c[0][0] for c in create_uq_calls]
        assert "uq_clients_slug" in uq_names

    def test_all_client_columns_use_schema(self, upgrade_ops):
        add_col_calls = [
            c for c in upgrade_ops.add_column.call_args_list if c[0][0] == "clients"
        ]
        for c in add_col_calls:
            assert c[1].get("schema") == SCHEMA, (
                f"add_column for clients.{c[0][1].name} missing schema={SCHEMA}"
            )


class TestUpgradeNewTables:
    """Validate 6 new tables are created properly."""

    def test_creates_all_six_tables(self, upgrade_ops):
        created = [c[0][0] for c in upgrade_ops.create_table.call_args_list]
        for table in CREATED_TABLES:
            assert table in created, f"Table {table} not created"

    def test_total_create_table_count(self, upgrade_ops):
        assert upgrade_ops.create_table.call_count == 6

    def test_all_tables_use_schema(self, upgrade_ops):
        for c in upgrade_ops.create_table.call_args_list:
            assert c[1].get("schema") == SCHEMA, (
                f"create_table({c[0][0]}) missing schema={SCHEMA}"
            )


class TestUpgradeApprovalAssets:
    def test_has_client_id_fk(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_assets")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.clients.id" in fk_args

    def test_indices(self, upgrade_ops):
        idx_names = _get_index_names(upgrade_ops)
        assert "ix_approval_assets_client_id" in idx_names
        assert "ix_approval_assets_status" in idx_names
        assert "ix_approval_assets_clickup_task_id" in idx_names


class TestUpgradeAssetVersions:
    def test_has_asset_id_fk(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "asset_versions")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.approval_assets.id" in fk_args

    def test_unique_constraint(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "asset_versions")
        uq_names = _extract_unique_constraint_names(table_call)
        assert "uq_asset_version" in uq_names


class TestUpgradeMagicLinks:
    def test_has_asset_and_client_app(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "magic_links")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.approval_assets.id" in fk_args
        assert f"{SCHEMA}.clients.id" in fk_args

    def test_token_unique(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "magic_links")
        uq_names = _extract_unique_constraint_names(table_call)
        assert "uq_magic_links_token" in uq_names

    def test_indices(self, upgrade_ops):
        idx_names = _get_index_names(upgrade_ops)
        assert "ix_magic_links_token" in idx_names
        assert "ix_magic_links_active_expires" in idx_names


class TestUpgradeApprovalComments:
    def test_has_asset_fk(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_comments")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.approval_assets.id" in fk_args

    def test_version_id_nullable(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_comments")
        cols = _extract_columns(table_call)
        version_col = next(c for c in cols if c.name == "version_id")
        assert version_col.nullable is True

    def test_index(self, upgrade_ops):
        idx_names = _get_index_names(upgrade_ops)
        assert "ix_approval_comments_asset_id" in idx_names


class TestUpgradeApprovalDecisions:
    def test_has_asset_and_version_app(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_decisions")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.approval_assets.id" in fk_args
        assert f"{SCHEMA}.asset_versions.id" in fk_args

    def test_index(self, upgrade_ops):
        idx_names = _get_index_names(upgrade_ops)
        assert "ix_approval_decisions_asset_id" in idx_names


class TestUpgradeApprovalEvents:
    def test_has_asset_fk(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_events")
        fk_args = _extract_fk_targets(table_call)
        assert f"{SCHEMA}.approval_assets.id" in fk_args

    def test_has_jsonb_metadata(self, upgrade_ops):
        table_call = _get_create_table_call(upgrade_ops, "approval_events")
        cols = _extract_columns(table_call)
        meta_col = next(c for c in cols if c.name == "metadata")
        from sqlalchemy.dialects.postgresql import JSONB

        assert isinstance(meta_col.type, JSONB)

    def test_indices(self, upgrade_ops):
        idx_names = _get_index_names(upgrade_ops)
        assert "ix_approval_events_asset_id" in idx_names
        assert "ix_approval_events_event_type" in idx_names


class TestUpgradeServerDefaults:
    """All 6 tables have id with gen_random_uuid() and timestamps with now()."""

    def test_all_tables_use_gen_random_uuid(self, upgrade_ops):
        for table_name in CREATED_TABLES:
            table_call = _get_create_table_call(upgrade_ops, table_name)
            cols = _extract_columns(table_call)
            id_col = next((c for c in cols if c.name == "id"), None)
            assert id_col is not None, f"{table_name} missing id column"
            assert id_col.server_default is not None, f"{table_name}.id missing server_default"
            sd_text = str(id_col.server_default.arg)
            assert "gen_random_uuid()" in sd_text, (
                f"{table_name}.id server_default is {sd_text}, expected gen_random_uuid()"
            )

    def test_created_at_uses_now(self, upgrade_ops):
        for table_name in CREATED_TABLES:
            table_call = _get_create_table_call(upgrade_ops, table_name)
            cols = _extract_columns(table_call)
            # approval_decisions uses decided_at, others use created_at
            ts_col_name = "decided_at" if table_name == "approval_decisions" else "created_at"
            ts_col = next((c for c in cols if c.name == ts_col_name), None)
            assert ts_col is not None, f"{table_name} missing {ts_col_name}"
            assert ts_col.server_default is not None
            sd_text = str(ts_col.server_default.arg)
            assert "now()" in sd_text, f"{table_name}.{ts_col_name} server_default is {sd_text}"

    def test_total_index_count(self, upgrade_ops):
        """Exactly 9 indices should be created across all 6 tables."""
        # approval_assets: 3 (client_id, status, clickup_task_id)
        # asset_versions: 1 (asset_id)
        # magic_links: 2 (token, active+expires)
        # approval_comments: 1 (asset_id)
        # approval_decisions: 1 (asset_id)
        # approval_events: 2 (asset_id, event_type)
        assert upgrade_ops.create_index.call_count == 10


# ---------------------------------------------------------------------------
# Downgrade — tables dropped in correct order
# ---------------------------------------------------------------------------


class TestDowngrade:
    """Validate that downgrade() drops tables in correct reverse order."""

    def test_drops_six_tables(self, downgrade_ops):
        assert downgrade_ops.drop_table.call_count == 6

    def test_drop_order_is_reverse_dependency(self, downgrade_ops):
        expected_order = [
            "approval_events",
            "approval_decisions",
            "approval_comments",
            "magic_links",
            "asset_versions",
            "approval_assets",
        ]
        actual = [c[0][0] for c in downgrade_ops.drop_table.call_args_list]
        assert actual == expected_order

    def test_all_drops_use_schema(self, downgrade_ops):
        for c in downgrade_ops.drop_table.call_args_list:
            assert c[1].get("schema") == SCHEMA

    def test_removes_slug_column(self, downgrade_ops):
        drop_col_calls = [
            c for c in downgrade_ops.drop_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1] for c in drop_col_calls]
        assert "slug" in col_names

    def test_removes_email_column(self, downgrade_ops):
        drop_col_calls = [
            c for c in downgrade_ops.drop_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1] for c in drop_col_calls]
        assert "email" in col_names

    def test_removes_logo_url_column(self, downgrade_ops):
        drop_col_calls = [
            c for c in downgrade_ops.drop_column.call_args_list if c[0][0] == "clients"
        ]
        col_names = [c[0][1] for c in drop_col_calls]
        assert "logo_url" in col_names

    def test_drops_slug_unique_constraint(self, downgrade_ops):
        drop_constraint_calls = downgrade_ops.drop_constraint.call_args_list
        names = [c[0][0] for c in drop_constraint_calls]
        assert "uq_clients_slug" in names

    def test_drop_columns_use_schema(self, downgrade_ops):
        drop_col_calls = [
            c for c in downgrade_ops.drop_column.call_args_list if c[0][0] == "clients"
        ]
        for c in drop_col_calls:
            assert c[1].get("schema") == SCHEMA


# ---------------------------------------------------------------------------
# Column detail validation
# ---------------------------------------------------------------------------


class TestColumnDetails:
    """Deeper checks on specific column properties."""

    def test_approval_assets_status_default(self, upgrade_ops):
        cols = _extract_columns(_get_create_table_call(upgrade_ops, "approval_assets"))
        status_col = next(c for c in cols if c.name == "status")
        assert str(status_col.server_default.arg) == "pending_review"

    def test_approval_assets_current_version_default(self, upgrade_ops):
        cols = _extract_columns(_get_create_table_call(upgrade_ops, "approval_assets"))
        ver_col = next(c for c in cols if c.name == "current_version")
        assert str(ver_col.server_default.arg) == "1"

    def test_magic_links_access_count_default(self, upgrade_ops):
        cols = _extract_columns(_get_create_table_call(upgrade_ops, "magic_links"))
        cnt_col = next(c for c in cols if c.name == "access_count")
        assert str(cnt_col.server_default.arg) == "0"

    def test_magic_links_is_active_default(self, upgrade_ops):
        cols = _extract_columns(_get_create_table_call(upgrade_ops, "magic_links"))
        active_col = next(c for c in cols if c.name == "is_active")
        assert str(active_col.server_default.arg) == "true"

    def test_asset_versions_file_size_is_biginteger(self, upgrade_ops):
        import sqlalchemy as sa

        cols = _extract_columns(_get_create_table_call(upgrade_ops, "asset_versions"))
        fs_col = next(c for c in cols if c.name == "file_size_bytes")
        assert isinstance(fs_col.type, sa.BigInteger)

    def test_asset_versions_duration_is_float(self, upgrade_ops):
        import sqlalchemy as sa

        cols = _extract_columns(_get_create_table_call(upgrade_ops, "asset_versions"))
        dur_col = next(c for c in cols if c.name == "duration_seconds")
        assert isinstance(dur_col.type, sa.Float)
