from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AssignmentResult:
    assignees: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    list_id: str = ""


class RulesEngine:
    def __init__(self, rules_path: Path):
        with open(rules_path) as f:
            self._rules = yaml.safe_load(f)

    def get_assignment(self, service_type: str, client_name: str) -> AssignmentResult:
        assignment_rules = self._rules.get("assignment_rules", {})
        default_config = self._rules.get("default_config", {})
        client_overrides = self._rules.get("client_overrides", {})

        rule = assignment_rules.get(service_type)
        if not rule:
            return AssignmentResult(list_id=default_config.get("list_id", ""))

        assignees = list(rule.get("default_assignees", []))
        tags = list(rule.get("tags", []))
        list_id = default_config.get("list_id", "")

        # Apply client overrides
        override = client_overrides.get(client_name)
        if override:
            if "designer" in override and "design" in service_type:
                assignees = [
                    override["designer"] if a in self._get_all_designers() else a
                    for a in assignees
                ]
                if override["designer"] not in assignees:
                    assignees = [override["designer"]] + [
                        a for a in assignees if a not in self._get_all_designers()
                    ]
            if "list_id" in override:
                list_id = override["list_id"]

        return AssignmentResult(assignees=assignees, tags=tags, list_id=list_id)

    def _get_all_designers(self) -> set[str]:
        rules = self._rules.get("assignment_rules", {})
        designers = set()
        for key in ("design", "design+copy"):
            if key in rules:
                designers.update(rules[key].get("default_assignees", []))
        return designers

    def get_reviewers(self) -> dict[str, str]:
        return self._rules.get("reviewers", {})

    def get_client_config(self, client_name: str) -> dict:
        """Get client-specific overrides (designer, list_id, etc.)."""
        return dict(self._rules.get("client_overrides", {}).get(client_name, {}))

    def get_client_designer(self, client_name: str) -> str | None:
        """Get the designer ID assigned to a client, or None."""
        config = self.get_client_config(client_name)
        return config.get("designer")

    def get_telegram_chat_id(self, clickup_user_id: str) -> int | None:
        """Get Telegram chat ID for a ClickUp user ID."""
        mapping = self._rules.get("team_mapping", {})
        user = mapping.get(clickup_user_id)
        return user["telegram_chat_id"] if user else None

    def get_clickup_user_id(self, telegram_chat_id: int) -> str | None:
        """Get ClickUp user ID for a Telegram chat ID."""
        mapping = self._rules.get("team_mapping", {})
        for clickup_id, info in mapping.items():
            if info.get("telegram_chat_id") == telegram_chat_id:
                return clickup_id
        return None

    def get_all_mapped_users(self) -> dict:
        """Get all user mappings {clickup_id: {telegram_chat_id, name}}."""
        return dict(self._rules.get("team_mapping", {}))

    def get_users_by_role(self, role: str) -> list[dict]:
        """Get all users with a specific role from team_mapping."""
        mapping = self._rules.get("team_mapping", {})
        users = []
        for clickup_id, info in mapping.items():
            if info.get("role") == role:
                users.append({"clickup_id": clickup_id, **info})
        return users

    def get_client_by_list_id(self, list_id: str) -> str:
        """Reverse lookup: given a list_id, return client name from client_overrides."""
        for client, config in self._rules.get("client_overrides", {}).items():
            if config.get("list_id") == list_id:
                return client
        return "default"

    def get_notification_rules(self, status: str) -> dict:
        """Get notification rules for a status transition."""
        return dict(self._rules.get("notification_rules", {}).get(status, {}))

    def get_all_clients(self) -> dict:
        """Return the full client_overrides dict.

        Replaces direct ``_rules.get("client_overrides", {})`` access.
        """
        return dict(self._rules.get("client_overrides", {}))

    def get_default_list_id(self) -> str:
        """Return default list_id from default_config.

        Replaces direct ``_rules.get("default_config", {}).get("list_id")`` access.
        """
        return self._rules.get("default_config", {}).get("list_id", "")

    def get_user_info(self, clickup_user_id: str) -> dict | None:
        """Get full user info from team_mapping.

        Returns dict with name, role, telegram_chat_id, clickup_id.
        Returns None if user not found.
        """
        info = self._rules.get("team_mapping", {}).get(str(clickup_user_id))
        if info:
            return {**info, "clickup_id": clickup_user_id}
        return None

    def get_auto_status_config(self) -> dict:
        """Return the auto_status configuration block."""
        return dict(self._rules.get("auto_status", {}))

    def get_user_role_by_clickup_id(self, clickup_user_id: str) -> str | None:
        """Get a user's role from team_mapping by ClickUp user ID."""
        mapping = self._rules.get("team_mapping", {})
        user = mapping.get(str(clickup_user_id))
        if user:
            return user.get("role")
        return None

    def get_client_topic_id(self, client_name: str) -> int | None:
        """Get Telegram forum topic ID for a client.

        Returns None (not 0) when no topic is configured or value is placeholder 0.
        """
        topics = self._rules.get("telegram_topics", {})
        entry = topics.get(client_name)
        if entry:
            tid = entry.get("topic_id", 0)
            return tid if tid else None
        return None

    def get_topic_id(self, topic_name: str) -> int | None:
        """Get Telegram forum topic ID by topic name (e.g. 'geral').

        Returns None when topic not configured or value is placeholder 0.
        """
        topics = self._rules.get("telegram_topics", {})
        entry = topics.get(topic_name)
        if entry:
            tid = entry.get("topic_id", 0)
            return tid if tid else None
        return None

    def get_user_name_by_clickup_id(self, clickup_user_id: str) -> str | None:
        """Get a user's name from team_mapping by ClickUp user ID."""
        mapping = self._rules.get("team_mapping", {})
        user = mapping.get(str(clickup_user_id))
        if user:
            return user.get("name")
        return None
