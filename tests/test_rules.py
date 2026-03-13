
import pytest
import yaml

from src.engine.rules import RulesEngine

SAMPLE_RULES = {
    "assignment_rules": {
        "design": {
            "default_assignees": ["user_designer1"],
            "tags": ["design"],
        },
        "copy": {
            "default_assignees": ["user_redator1"],
            "tags": ["copy", "redacao"],
        },
        "design+copy": {
            "default_assignees": ["user_designer1", "user_redator1"],
            "tags": ["design", "copy"],
        },
    },
    "reviewers": {
        "strategy": "user_luis",
        "content": "user_luiza",
    },
    "client_overrides": {
        "Cliente X": {
            "designer": "user_ana",
            "list_id": "list_special",
        },
    },
    "default_config": {
        "list_id": "list_planejamento",
        "initial_status": "planejamento",
    },
    "team_mapping": {
        "user_designer1": {"telegram_chat_id": 111111, "name": "Designer 1", "role": "designer"},
        "user_luis": {"telegram_chat_id": 222222, "name": "Luis", "role": "strategy_reviewer"},
        "user_luiza": {"telegram_chat_id": 333333, "name": "Content Lead", "role": "content_reviewer"},
    },
    "notification_rules": {
        "revisao": {
            "notify_roles": ["strategy_reviewer", "content_reviewer"],
            "message": "precisa de revisao",
        },
        "alteracao": {
            "notify_roles": ["designer"],
            "message": "voltou para alteracao",
        },
        "aprovado": {
            "notify_roles": ["designer", "account"],
            "message": "foi aprovada!",
        },
        "pronto": {
            "notify": "group",
            "message": "esta pronta",
        },
    },
}


@pytest.fixture
def rules_engine(tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml.dump(SAMPLE_RULES))
    return RulesEngine(rules_file)


def test_get_assignees_for_service_type(rules_engine):
    result = rules_engine.get_assignment("design", client_name="Qualquer")
    assert result.assignees == ["user_designer1"]
    assert result.tags == ["design"]


def test_get_assignees_for_combined_type(rules_engine):
    result = rules_engine.get_assignment("design+copy", client_name="Qualquer")
    assert "user_designer1" in result.assignees
    assert "user_redator1" in result.assignees


def test_client_override_replaces_designer(rules_engine):
    result = rules_engine.get_assignment("design", client_name="Cliente X")
    assert "user_ana" in result.assignees


def test_get_list_id_default(rules_engine):
    result = rules_engine.get_assignment("design", client_name="Qualquer")
    assert result.list_id == "list_planejamento"


def test_get_list_id_client_override(rules_engine):
    result = rules_engine.get_assignment("design", client_name="Cliente X")
    assert result.list_id == "list_special"


def test_unknown_service_type_returns_empty(rules_engine):
    result = rules_engine.get_assignment("unknown_type", client_name="Qualquer")
    assert result.assignees == []
    assert result.tags == []


def test_get_client_config_known_client(rules_engine):
    config = rules_engine.get_client_config("Cliente X")
    assert config["designer"] == "user_ana"
    assert config["list_id"] == "list_special"


def test_get_client_config_unknown_client(rules_engine):
    config = rules_engine.get_client_config("Unknown")
    assert config == {}


def test_get_client_designer(rules_engine):
    designer = rules_engine.get_client_designer("Cliente X")
    assert designer == "user_ana"


def test_get_client_designer_unknown_returns_none(rules_engine):
    designer = rules_engine.get_client_designer("Unknown")
    assert designer is None


def test_get_telegram_chat_id_known_user(rules_engine):
    chat_id = rules_engine.get_telegram_chat_id("user_designer1")
    assert chat_id == 111111


def test_get_telegram_chat_id_unknown_user(rules_engine):
    chat_id = rules_engine.get_telegram_chat_id("unknown_user")
    assert chat_id is None


def test_get_clickup_user_id_by_telegram(rules_engine):
    clickup_id = rules_engine.get_clickup_user_id(111111)
    assert clickup_id == "user_designer1"


def test_get_clickup_user_id_unknown_telegram(rules_engine):
    clickup_id = rules_engine.get_clickup_user_id(999999)
    assert clickup_id is None


def test_get_all_mapped_users(rules_engine):
    users = rules_engine.get_all_mapped_users()
    assert len(users) == 3
    assert "user_designer1" in users


def test_get_users_by_role(rules_engine):
    designers = rules_engine.get_users_by_role("designer")
    assert len(designers) == 1
    assert designers[0]["telegram_chat_id"] == 111111


def test_get_users_by_role_multiple_reviewers(rules_engine):
    # strategy_reviewer and content_reviewer are different roles
    strat = rules_engine.get_users_by_role("strategy_reviewer")
    assert len(strat) == 1
    assert strat[0]["name"] == "Luis"


def test_get_users_by_role_nonexistent(rules_engine):
    users = rules_engine.get_users_by_role("nonexistent_role")
    assert users == []


def test_get_notification_rules_existing(rules_engine):
    rules = rules_engine.get_notification_rules("revisao")
    assert "notify_roles" in rules


def test_get_notification_rules_nonexistent(rules_engine):
    rules = rules_engine.get_notification_rules("nonexistent")
    assert rules == {}


# === Convenience methods ===


def test_get_all_clients(rules_engine):
    clients = rules_engine.get_all_clients()
    assert "Cliente X" in clients
    assert clients["Cliente X"]["list_id"] == "list_special"


def test_get_all_clients_returns_copy(rules_engine):
    clients = rules_engine.get_all_clients()
    clients["NewClient"] = {"list_id": "new"}
    assert "NewClient" not in rules_engine.get_all_clients()


def test_get_default_list_id(rules_engine):
    assert rules_engine.get_default_list_id() == "list_planejamento"


def test_get_default_list_id_missing(tmp_path):
    import yaml
    rules_file = tmp_path / "empty_rules.yaml"
    rules_file.write_text(yaml.dump({"assignment_rules": {}}))
    from src.engine.rules import RulesEngine
    engine = RulesEngine(rules_file)
    assert engine.get_default_list_id() == ""


# === get_user_info ===


def test_get_user_info_known_user(rules_engine):
    info = rules_engine.get_user_info("user_designer1")
    assert info is not None
    assert info["name"] == "Designer 1"
    assert info["role"] == "designer"
    assert info["telegram_chat_id"] == 111111
    assert info["clickup_id"] == "user_designer1"


def test_get_user_info_unknown_user(rules_engine):
    info = rules_engine.get_user_info("unknown_user_id")
    assert info is None


def test_get_user_info_includes_clickup_id(rules_engine):
    """Verify that clickup_id is injected into the returned dict."""
    info = rules_engine.get_user_info("user_luis")
    assert info is not None
    assert info["clickup_id"] == "user_luis"
    assert info["role"] == "strategy_reviewer"


# === get_auto_status_config ===


def test_get_auto_status_config_with_data(tmp_path):
    rules_data = {
        "auto_status": {
            "enabled": True,
            "mode": "confirm",
            "delivery": {
                "patterns": ["finalizado"],
                "allowed_roles": ["designer"],
                "target_status": "revisao",
                "valid_from": ["desenvolvimento"],
            },
        },
    }
    rules_file = tmp_path / "rules_auto.yaml"
    rules_file.write_text(yaml.dump(rules_data))
    engine = RulesEngine(rules_file)
    config = engine.get_auto_status_config()
    assert config["enabled"] is True
    assert config["mode"] == "confirm"
    assert "delivery" in config
    assert config["delivery"]["patterns"] == ["finalizado"]


def test_get_auto_status_config_empty(tmp_path):
    rules_file = tmp_path / "empty.yaml"
    rules_file.write_text(yaml.dump({"assignment_rules": {}}))
    engine = RulesEngine(rules_file)
    assert engine.get_auto_status_config() == {}
