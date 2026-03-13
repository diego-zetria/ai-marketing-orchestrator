"""RulesEngine backed by PostgreSQL.

Loads all configuration from the database into memory at startup,
then serves it synchronously -- same interface as the YAML-based RulesEngine.
Call ``reload()`` (async) to refresh after config changes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.engine.rules import AssignmentResult


class DbRulesEngine:
    """Drop-in replacement for RulesEngine, backed by database tables."""

    def __init__(self) -> None:
        # In-memory caches populated by reload()
        self._team_mapping: dict[str, dict] = {}
        self._client_overrides: dict[str, dict] = {}
        self._assignment_rules: dict[str, dict] = {}
        self._notification_rules: dict[str, dict] = {}
        self._default_config: dict[str, str] = {}
        self._reviewers: dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Async loader
    # ------------------------------------------------------------------

    async def reload(self, session_factory: async_sessionmaker) -> None:
        """Load all config from DB into memory.  Call at startup and after changes."""
        async with session_factory() as session:
            await self._load_team_members(session)
            await self._load_clients(session)
            await self._load_assignment_rules(session)
            await self._load_notification_rules(session)
            await self._load_system_config(session)
        self._loaded = True

    async def _load_team_members(self, session: AsyncSession) -> None:
        from src.db.models import TeamMember

        result = await session.execute(
            select(TeamMember).where(TeamMember.active.is_(True))
        )
        self._team_mapping = {}
        self._reviewers = {}
        for m in result.scalars().all():
            if not m.clickup_user_id:
                continue
            self._team_mapping[m.clickup_user_id] = {
                "name": m.name,
                "role": m.role or "",
                "telegram_chat_id": m.telegram_chat_id or 0,
            }
            # Build reviewers dict (same format as YAML reviewers section)
            if m.role == "strategy_reviewer":
                self._reviewers["strategy"] = m.clickup_user_id
            elif m.role == "content_reviewer":
                self._reviewers["content"] = m.clickup_user_id

    async def _load_clients(self, session: AsyncSession) -> None:
        from src.db.admin_models import Client
        from src.db.models import TeamMember

        result = await session.execute(
            select(Client).where(Client.is_active.is_(True))
        )
        self._client_overrides = {}
        for c in result.scalars().all():
            override: dict[str, str] = {"list_id": c.clickup_list_id or ""}
            if c.designer_id:
                designer = await session.get(TeamMember, c.designer_id)
                if designer and designer.clickup_user_id:
                    override["designer"] = designer.clickup_user_id
            if c.account_id:
                account = await session.get(TeamMember, c.account_id)
                if account and account.clickup_user_id:
                    override["account"] = account.clickup_user_id
            self._client_overrides[c.name] = override

    async def _load_assignment_rules(self, session: AsyncSession) -> None:
        from src.db.admin_models import AssignmentRule

        result = await session.execute(select(AssignmentRule))
        self._assignment_rules = {}
        for r in result.scalars().all():
            self._assignment_rules[r.service_type] = {
                "default_assignees": list(r.default_assignee_ids or []),
                "tags": list(r.tags or []),
            }

    async def _load_notification_rules(self, session: AsyncSession) -> None:
        from src.db.admin_models import NotificationRule

        result = await session.execute(
            select(NotificationRule).where(NotificationRule.is_active.is_(True))
        )
        self._notification_rules = {}
        for r in result.scalars().all():
            self._notification_rules[r.status] = {
                "notify_roles": list(r.notify_roles or []),
                "message": r.message_template,
            }

    async def _load_system_config(self, session: AsyncSession) -> None:
        from src.db.admin_models import SystemConfig

        result = await session.execute(select(SystemConfig))
        configs: dict[str, object] = {r.key: r.value for r in result.scalars().all()}

        self._default_config = {
            "list_id": self._extract_config_value(configs, "default_list_id", ""),
            "initial_status": self._extract_config_value(
                configs, "initial_status", "planejamento"
            ),
        }

    # ------------------------------------------------------------------
    # Synchronous public interface (identical to RulesEngine)
    # ------------------------------------------------------------------

    def get_assignment(self, service_type: str, client_name: str) -> AssignmentResult:
        rule = self._assignment_rules.get(service_type)
        if not rule:
            return AssignmentResult(list_id=self._default_config.get("list_id", ""))

        assignees = list(rule.get("default_assignees", []))
        tags = list(rule.get("tags", []))
        list_id = self._default_config.get("list_id", "")

        override = self._client_overrides.get(client_name)
        if override:
            if "designer" in override and "design" in service_type:
                all_designers = self._get_all_designers()
                assignees = [
                    override["designer"] if a in all_designers else a
                    for a in assignees
                ]
                if override["designer"] not in assignees:
                    assignees = [override["designer"]] + [
                        a for a in assignees if a not in all_designers
                    ]
            if "list_id" in override:
                list_id = override["list_id"]

        return AssignmentResult(assignees=assignees, tags=tags, list_id=list_id)

    def _get_all_designers(self) -> set[str]:
        designers: set[str] = set()
        for key in ("design", "design+copy"):
            rule = self._assignment_rules.get(key)
            if rule:
                designers.update(rule.get("default_assignees", []))
        return designers

    def get_reviewers(self) -> dict[str, str]:
        return dict(self._reviewers)

    def get_client_config(self, client_name: str) -> dict:
        """Get client-specific overrides (designer, list_id, etc.)."""
        return dict(self._client_overrides.get(client_name, {}))

    def get_client_designer(self, client_name: str) -> str | None:
        """Get the designer ID assigned to a client, or None."""
        config = self.get_client_config(client_name)
        return config.get("designer")

    def get_telegram_chat_id(self, clickup_user_id: str) -> int | None:
        """Get Telegram chat ID for a ClickUp user ID."""
        user = self._team_mapping.get(clickup_user_id)
        return user["telegram_chat_id"] if user else None

    def get_clickup_user_id(self, telegram_chat_id: int) -> str | None:
        """Get ClickUp user ID for a Telegram chat ID."""
        for clickup_id, info in self._team_mapping.items():
            if info.get("telegram_chat_id") == telegram_chat_id:
                return clickup_id
        return None

    def get_all_mapped_users(self) -> dict:
        """Get all user mappings {clickup_id: {telegram_chat_id, name}}."""
        return dict(self._team_mapping)

    def get_users_by_role(self, role: str) -> list[dict]:
        """Get all users with a specific role from team_mapping."""
        users = []
        for clickup_id, info in self._team_mapping.items():
            if info.get("role") == role:
                users.append({"clickup_id": clickup_id, **info})
        return users

    def get_client_by_list_id(self, list_id: str) -> str:
        """Reverse lookup: given a list_id, return client name."""
        for client, config in self._client_overrides.items():
            if config.get("list_id") == list_id:
                return client
        return "default"

    def get_notification_rules(self, status: str) -> dict:
        """Get notification rules for a status transition."""
        return dict(self._notification_rules.get(status, {}))

    # ------------------------------------------------------------------
    # Convenience methods (replace direct _rules access)
    # ------------------------------------------------------------------

    def get_all_clients(self) -> dict:
        """Return the full client_overrides dict.

        Replaces ``rules_engine._rules.get("client_overrides", {})``.
        """
        return dict(self._client_overrides)

    def get_default_list_id(self) -> str:
        """Return default list_id from system config.

        Replaces ``rules_engine._rules.get("default_config", {}).get("list_id")``.
        """
        return self._default_config.get("list_id", "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_config_value(
        configs: dict[str, object], key: str, default: str
    ) -> str:
        """Extract a scalar value from system_config.

        system_config.value is JSONB, so it could be stored as
        ``{"value": "xxx"}`` or as a bare string.
        """
        val = configs.get(key)
        if val is None:
            return default
        if isinstance(val, dict):
            return str(val.get("value", default))
        return str(val)
