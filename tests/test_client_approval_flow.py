"""Tests for client approval comment patterns and EventBridge trigger."""
from unittest.mock import MagicMock, patch

from src.bot.comment_patterns import detect_intent

# ===================================================================
# Client approval comment patterns (Lacuna 1)
# ===================================================================


class TestClientApprovalPatterns:
    """Detect 'send to client' intent from Account manager comments."""

    def test_aprovacao_do_cliente(self):
        result = detect_intent(
            "segue para aprovacao do cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"
        assert result.target_status == ""

    def test_aprovacao_do_cliente_no_cedilha(self):
        result = detect_intent(
            "aprovacao do cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_enviar_para_cliente(self):
        result = detect_intent(
            "enviar para cliente aprovar", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_enviar_para_o_cliente(self):
        result = detect_intent(
            "vou enviar para o cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_mandar_para_cliente(self):
        result = detect_intent(
            "mandar para cliente ver", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_mandar_para_o_cliente(self):
        result = detect_intent(
            "vou mandar para o cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_segue_para_cliente(self):
        # "segue para cliente" now matches internal_approved (higher priority)
        # which triggers status change to revisao_cliente (Path B)
        result = detect_intent(
            "segue para o cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "internal_approved"
        assert result.target_status == "revisao_cliente"

    def test_segue_para_cliente_without_article(self):
        result = detect_intent(
            "segue para cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "internal_approved"
        assert result.target_status == "revisao_cliente"

    def test_cliente_aprovar(self):
        result = detect_intent(
            "material pronto, cliente aprovar", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_encaminhar_para_cliente(self):
        result = detect_intent(
            "encaminhar para o cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"

    def test_enviar_ao_cliente(self):
        result = detect_intent(
            "enviar ao cliente para aprovacao", "account", "aprovado",
        )
        assert result is not None
        assert result.intent_type == "client_approval"


class TestClientApprovalRoleValidation:
    """Only Account managers can trigger client approval."""

    def test_rejects_designer(self):
        result = detect_intent(
            "enviar para cliente", "designer", "aprovado",
        )
        assert result is None

    def test_rejects_reviewer(self):
        result = detect_intent(
            "enviar para cliente", "strategy_reviewer", "aprovado",
        )
        assert result is None


class TestClientApprovalStatusValidation:
    """Client approval only valid from 'aprovado' status."""

    def test_rejects_from_revisao(self):
        result = detect_intent(
            "enviar para cliente", "account", "revisao",
        )
        assert result is None

    def test_rejects_from_em_criacao(self):
        result = detect_intent(
            "enviar para cliente", "account", "em criacao",
        )
        assert result is None

    def test_rejects_from_desenvolvimento(self):
        result = detect_intent(
            "enviar para cliente", "account", "desenvolvimento",
        )
        assert result is None


class TestClientApprovalPriority:
    """client_approval is checked before generic approval patterns."""

    def test_aprovacao_do_cliente_not_matched_as_internal(self):
        """'aprovacao do cliente' should match client_approval, not approval."""
        result = detect_intent(
            "aprovacao do cliente", "account", "aprovado",
        )
        assert result is not None
        # Should be client_approval, not internal approval
        assert result.intent_type == "client_approval"


class TestClientApprovalTargetStatus:
    """client_approval intent has empty target_status (no status change)."""

    def test_target_status_is_empty(self):
        result = detect_intent(
            "enviar para cliente", "account", "aprovado",
        )
        assert result is not None
        assert result.target_status == ""


# ===================================================================
# EventBridge send function (unit tests)
# ===================================================================


class TestSendTaskStatusEvent:
    """Unit tests for the EventBridge send function."""

    def test_sends_event_successfully(self):
        from src.integrations.eventbridge import send_task_status_event

        mock_client = MagicMock()
        mock_client.put_events.return_value = {
            "FailedEntryCount": 0,
            "Entries": [{"EventId": "123"}],
        }

        with patch("boto3.client", return_value=mock_client):
            result = send_task_status_event(
                bus_name="approval-events",
                task_id="t1",
            )
            assert result is True
            mock_client.put_events.assert_called_once()
            call_args = mock_client.put_events.call_args[1]
            entry = call_args["Entries"][0]
            assert entry["Source"] == "app.clickup"
            assert entry["DetailType"] == "task_status_changed"
            assert '"task_id": "t1"' in entry["Detail"]
            assert entry["EventBusName"] == "approval-events"

    def test_returns_false_on_failed_entry(self):
        from src.integrations.eventbridge import send_task_status_event

        mock_client = MagicMock()
        mock_client.put_events.return_value = {
            "FailedEntryCount": 1,
            "Entries": [{"ErrorCode": "InternalFailure"}],
        }

        with patch("boto3.client", return_value=mock_client):
            result = send_task_status_event(
                bus_name="approval-events",
                task_id="t1",
            )
            assert result is False

    def test_returns_false_on_exception(self):
        from src.integrations.eventbridge import send_task_status_event

        with patch("boto3.client", side_effect=Exception("No credentials")):
            result = send_task_status_event(
                bus_name="approval-events",
                task_id="t1",
            )
            assert result is False

    def test_custom_status_and_region(self):
        from src.integrations.eventbridge import send_task_status_event

        mock_client = MagicMock()
        mock_client.put_events.return_value = {
            "FailedEntryCount": 0,
            "Entries": [{"EventId": "456"}],
        }

        with patch("boto3.client", return_value=mock_client) as mock_boto:
            send_task_status_event(
                bus_name="app-approval-prod",
                task_id="t2",
                status="custom_status",
                region="sa-east-1",
            )
            mock_boto.assert_called_with("events", region_name="sa-east-1")
            entry = mock_client.put_events.call_args[1]["Entries"][0]
            assert '"custom_status"' in entry["Detail"]
            assert entry["EventBusName"] == "app-approval-prod"
