"""DynamicRulesEngine: extends DbRulesEngine with workflows and automation rules."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.bot.comment_patterns import CommentIntent
from src.engine.db_rules import DbRulesEngine

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DynamicRulesEngine(DbRulesEngine):
    """Full-featured rules engine backed by database with dynamic workflows."""

    def __init__(self) -> None:
        super().__init__()
        self._workflows: dict[str, dict] = {}
        self._default_workflow_name: str = ""
        self._automation_rules_list: list[dict] = []  # ordered by priority
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}  # rule name -> compiled
        self._telegram_topics_map: dict[str, dict] = {}  # name -> {topic_id, label, client_id}
        self._cache_ttl: float = 300.0  # 5 min
        self._last_reload: float = 0.0
        self._cache_version: str = ""

    # ------------------------------------------------------------------
    # Async loader (override)
    # ------------------------------------------------------------------

    async def reload(self, session_factory: async_sessionmaker) -> None:
        """Load all config from DB including workflows, automation rules, and topics."""
        async with session_factory() as session:
            await self._load_team_members(session)
            await self._load_clients(session)
            await self._load_assignment_rules(session)
            await self._load_notification_rules(session)
            await self._load_system_config(session)
            await self._load_workflows(session)
            await self._load_automation_rules(session)
            await self._load_telegram_topics(session)
            self._cache_version = await self._get_cache_version(session)
        self._loaded = True
        self._last_reload = time.monotonic()

    async def maybe_reload(self, session_factory: async_sessionmaker) -> None:
        """Reload if TTL expired or cache version changed."""
        if not self._loaded:
            await self.reload(session_factory)
            return

        elapsed = time.monotonic() - self._last_reload
        if elapsed < self._cache_ttl:
            return

        # Check if cache version changed
        async with session_factory() as session:
            current_version = await self._get_cache_version(session)

        if current_version != self._cache_version:
            await self.reload(session_factory)

    async def _load_workflows(self, session: AsyncSession) -> None:
        from src.db.workflow_models import WorkflowDefinition

        result = await session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.is_active.is_(True))
        )
        self._workflows = {}
        self._default_workflow_name = ""
        for wf in result.scalars().all():
            self._workflows[wf.name] = {
                "display_name": wf.display_name,
                "description": wf.description,
                "statuses": list(wf.statuses or []),
                "transitions": dict(wf.transitions or {}),
                "transition_actions": dict(wf.transition_actions or {}),
                "is_default": wf.is_default,
            }
            if wf.is_default:
                self._default_workflow_name = wf.name

    async def _load_automation_rules(self, session: AsyncSession) -> None:
        from src.db.workflow_models import AutomationRule

        result = await session.execute(
            select(AutomationRule)
            .where(AutomationRule.is_active.is_(True))
            .order_by(AutomationRule.priority)
        )
        self._automation_rules_list = []
        self._compiled_patterns = {}
        for rule in result.scalars().all():
            rule_dict = {
                "name": rule.name,
                "intent_type": rule.intent_type,
                "patterns": list(rule.patterns or []),
                "allowed_roles": set(rule.allowed_roles or []),
                "valid_from_statuses": set(rule.valid_from_statuses or []),
                "target_status": rule.target_status or "",
                "mode": rule.mode or "confirm",
                "special_action": rule.special_action,
                "priority": rule.priority,
            }
            self._automation_rules_list.append(rule_dict)

            # Pre-compile patterns, skip invalid regex
            compiled = []
            for p in rule_dict["patterns"]:
                try:
                    compiled.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    logger.warning(
                        "Skipping invalid regex in rule '%s': %s", rule.name, p,
                    )
            self._compiled_patterns[rule.name] = compiled

    async def _load_telegram_topics(self, session: AsyncSession) -> None:
        from src.db.workflow_models import TelegramTopic

        result = await session.execute(
            select(TelegramTopic).where(TelegramTopic.is_active.is_(True))
        )
        self._telegram_topics_map = {}
        for t in result.scalars().all():
            self._telegram_topics_map[t.name] = {
                "topic_id": t.topic_id,
                "label": t.label,
                "client_id": str(t.client_id) if t.client_id else None,
            }

    async def _get_cache_version(self, session: AsyncSession) -> str:
        from src.db.admin_models import SystemConfig

        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == "rules_cache_version")
        )
        config = result.scalar_one_or_none()
        if config and isinstance(config.value, dict):
            return config.value.get("version", "")
        return ""

    # ------------------------------------------------------------------
    # Workflow methods
    # ------------------------------------------------------------------

    def get_workflow(self, name: str | None = None) -> dict | None:
        """Get workflow by name, or default workflow if name is None."""
        if name:
            return self._workflows.get(name)
        if self._default_workflow_name:
            return self._workflows.get(self._default_workflow_name)
        return None

    def get_client_workflow(self, client_name: str) -> dict | None:
        """Get workflow for a client (falls back to default)."""
        override = self._client_overrides.get(client_name, {})
        workflow_name = override.get("workflow_name")
        if workflow_name and workflow_name in self._workflows:
            return self._workflows[workflow_name]
        return self.get_workflow()

    def is_valid_transition(
        self,
        from_status: str,
        to_status: str,
        role: str,
        workflow_name: str | None = None,
    ) -> bool:
        """Check if a status transition is valid for a given role."""
        wf = self.get_workflow(workflow_name)
        if not wf:
            return False

        transitions = wf.get("transitions", {})
        allowed = transitions.get(from_status, [])
        for t in allowed:
            if t.get("to") == to_status:
                roles = t.get("roles", [])
                if not roles or role in roles:
                    return True
        return False

    def get_all_statuses(self, workflow_name: str | None = None) -> list[str]:
        """Get ordered list of statuses for a workflow."""
        wf = self.get_workflow(workflow_name)
        if not wf:
            return []
        return list(wf.get("statuses", []))

    # ------------------------------------------------------------------
    # Intent detection from DB rules
    # ------------------------------------------------------------------

    def detect_intent(
        self,
        comment_text: str,
        user_role: str | None,
        current_status: str | None,
    ) -> CommentIntent | None:
        """Detect intent using automation rules from DB."""
        if not comment_text or not comment_text.strip():
            return None

        for rule in self._automation_rules_list:
            patterns = self._compiled_patterns.get(rule["name"], [])
            matched_text = None
            for pattern in patterns:
                match = pattern.search(comment_text)
                if match:
                    matched_text = match.group(0)
                    break

            if matched_text is None:
                continue

            # Validate role
            allowed_roles = rule["allowed_roles"]
            if user_role and allowed_roles and user_role not in allowed_roles:
                continue

            # Validate current status
            valid_from = rule["valid_from_statuses"]
            if current_status and valid_from and current_status not in valid_from:
                continue

            return CommentIntent(
                intent_type=rule["intent_type"],
                target_status=rule["target_status"],
                matched_pattern=matched_text,
                confidence=1.0,
            )

        return None

    # ------------------------------------------------------------------
    # Missing methods from DbRulesEngine (5 methods)
    # ------------------------------------------------------------------

    def get_auto_status_config(self) -> dict:
        """Reconstruct auto_status config format from automation rules."""
        config: dict = {}
        for rule in self._automation_rules_list:
            if rule["target_status"] or rule.get("special_action"):
                config[rule["intent_type"]] = {
                    "allowed_roles": list(rule["allowed_roles"]),
                    "valid_from": list(rule["valid_from_statuses"]),
                    "target_status": rule["target_status"],
                }
        return config

    def get_user_role_by_clickup_id(self, clickup_user_id: str) -> str | None:
        """Get a user's role from team_mapping by ClickUp user ID."""
        user = self._team_mapping.get(str(clickup_user_id))
        if user:
            return user.get("role")
        return None

    def get_user_name_by_clickup_id(self, clickup_user_id: str) -> str | None:
        """Get a user's name from team_mapping by ClickUp user ID."""
        user = self._team_mapping.get(str(clickup_user_id))
        if user:
            return user.get("name")
        return None

    def get_client_topic_id(self, client_name: str) -> int | None:
        """Get Telegram forum topic ID for a client."""
        entry = self._telegram_topics_map.get(client_name)
        if entry:
            tid = entry.get("topic_id", 0)
            return tid if tid else None
        return None

    def get_topic_id(self, topic_name: str) -> int | None:
        """Get Telegram forum topic ID by topic name."""
        entry = self._telegram_topics_map.get(topic_name)
        if entry:
            tid = entry.get("topic_id", 0)
            return tid if tid else None
        return None
