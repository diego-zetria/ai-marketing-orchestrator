"""Tests for the WhatsApp Business Cloud API service.

Uses respx to mock httpx async requests.
"""

import logging

import httpx
import pytest
import respx

from src.approval.services.whatsapp import WhatsAppService

PHONE_NUMBER_ID = "123456789"
ACCESS_TOKEN = "test-access-token"
PORTAL_DOMAIN = "https://approvals.example.com"
GRAPH_API_BASE = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}"


@pytest.fixture()
def wa_service():
    """Create a WhatsAppService instance for testing."""
    return WhatsAppService(
        phone_number_id=PHONE_NUMBER_ID,
        access_token=ACCESS_TOKEN,
        portal_domain=PORTAL_DOMAIN,
    )


# ---------------------------------------------------------------------------
# 1. test_init_configures_client
# ---------------------------------------------------------------------------
class TestInitConfiguresClient:
    def test_init_configures_client(self, wa_service):
        """Client is configured with correct base_url and auth header."""
        assert str(wa_service._client.base_url) == f"{GRAPH_API_BASE}/"
        assert wa_service._client.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert wa_service._client.headers["content-type"] == "application/json"
        assert wa_service._client.timeout.read == 30.0


# ---------------------------------------------------------------------------
# 2. test_build_review_url
# ---------------------------------------------------------------------------
class TestBuildReviewUrl:
    def test_build_review_url(self, wa_service):
        """Review URL is correctly constructed from portal domain and token."""
        url = wa_service._build_review_url("abc123")
        assert url == "https://approvals.example.com/review?token=abc123"

    def test_build_review_url_strips_trailing_slash(self):
        """Trailing slashes in portal domain are stripped."""
        svc = WhatsAppService(
            phone_number_id="1",
            access_token="t",
            portal_domain="https://example.com/",
        )
        url = svc._build_review_url("tok")
        assert url == "https://example.com/review?token=tok"


# ---------------------------------------------------------------------------
# 3. test_send_new_asset_message
# ---------------------------------------------------------------------------
class TestSendNewAssetMessage:
    @respx.mock
    async def test_send_new_asset_message(self, wa_service):
        """Sends aprovacao_nova_arte template with header, body, and button."""
        route = respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(
                200,
                json={"messages": [{"id": "wamid.abc123"}]},
            )
        )

        result = await wa_service.send_new_asset_message(
            to_phone="5541999887766",
            client_name="ClientAlpha",
            asset_title="Post Instagram",
            thumbnail_url="https://cdn.example.com/thumb.webp",
            magic_link_token="token123",
            version_number=1,
        )

        assert route.called
        payload = route.calls[0].request.content
        import json

        body = json.loads(payload)
        assert body["messaging_product"] == "whatsapp"
        assert body["to"] == "5541999887766"
        assert body["template"]["name"] == "aprovacao_nova_arte"
        assert body["template"]["language"]["code"] == "pt_BR"

        components = body["template"]["components"]
        # header with image
        header = next(c for c in components if c["type"] == "header")
        assert header["parameters"][0]["image"]["link"] == "https://cdn.example.com/thumb.webp"
        # body params
        body_comp = next(c for c in components if c["type"] == "body")
        assert body_comp["parameters"][0]["text"] == "ClientAlpha"
        assert body_comp["parameters"][1]["text"] == "Post Instagram"
        assert body_comp["parameters"][2]["text"] == "1"
        # button with URL suffix
        button = next(c for c in components if c["type"] == "button")
        assert button["parameters"][0]["text"] == "/review?token=token123"

        assert result["messages"][0]["id"] == "wamid.abc123"


# ---------------------------------------------------------------------------
# 4. test_send_new_asset_version_gt_1
# ---------------------------------------------------------------------------
class TestSendNewAssetVersionGt1:
    @respx.mock
    async def test_send_new_asset_version_gt_1(self, wa_service):
        """Version number > 1 is passed correctly in body params."""
        respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.v2"}]})
        )

        await wa_service.send_new_asset_message(
            to_phone="5541999887766",
            client_name="ClientDelta",
            asset_title="Banner LinkedIn",
            thumbnail_url="https://cdn.example.com/thumb2.webp",
            magic_link_token="tok456",
            version_number=3,
        )

        import json

        body = json.loads(respx.calls[0].request.content)
        body_comp = next(c for c in body["template"]["components"] if c["type"] == "body")
        assert body_comp["parameters"][2]["text"] == "3"


# ---------------------------------------------------------------------------
# 5. test_send_reminder_message
# ---------------------------------------------------------------------------
class TestSendReminderMessage:
    @respx.mock
    async def test_send_reminder_message(self, wa_service):
        """Sends aprovacao_lembrete template with correct params."""
        route = respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.rem1"}]})
        )

        result = await wa_service.send_reminder_message(
            to_phone="5541999887766",
            client_name="ClientAlpha",
            asset_title="Post Instagram",
            thumbnail_url="https://cdn.example.com/thumb.webp",
            magic_link_token="reminder-tok",
            days_pending=2,
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["template"]["name"] == "aprovacao_lembrete"
        body_comp = next(c for c in body["template"]["components"] if c["type"] == "body")
        assert body_comp["parameters"][2]["text"] == "2"
        assert result["messages"][0]["id"] == "wamid.rem1"


# ---------------------------------------------------------------------------
# 6. test_send_confirmation_approved
# ---------------------------------------------------------------------------
class TestSendConfirmationApproved:
    @respx.mock
    async def test_send_confirmation_approved(self, wa_service):
        """Sends aprovacao_confirmada with 'Aprovado' decision."""
        route = respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.conf1"}]})
        )

        await wa_service.send_confirmation_message(
            to_phone="5541999887766",
            client_name="ClientAlpha",
            asset_title="Post Instagram",
            decision="approved",
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["template"]["name"] == "aprovacao_confirmada"
        components = body["template"]["components"]
        # No header or button for confirmation
        assert all(c["type"] == "body" for c in components)
        body_comp = components[0]
        assert body_comp["parameters"][2]["text"] == "Aprovado"


# ---------------------------------------------------------------------------
# 7. test_send_confirmation_changes
# ---------------------------------------------------------------------------
class TestSendConfirmationChanges:
    @respx.mock
    async def test_send_confirmation_changes(self, wa_service):
        """Sends aprovacao_confirmada with 'Alteracao solicitada' decision."""
        respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.conf2"}]})
        )

        await wa_service.send_confirmation_message(
            to_phone="5541999887766",
            client_name="ClientDelta",
            asset_title="Banner",
            decision="changes_requested",
        )

        import json

        body = json.loads(respx.calls[0].request.content)
        body_comp = body["template"]["components"][0]
        assert body_comp["parameters"][2]["text"] == "Alteracao solicitada"


# ---------------------------------------------------------------------------
# 8. test_send_template_api_error
# ---------------------------------------------------------------------------
class TestSendTemplateApiError:
    @respx.mock
    async def test_send_template_api_error(self, wa_service):
        """HTTP 400 from Graph API raises httpx.HTTPStatusError."""
        respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(400, json={"error": {"message": "Invalid template"}})
        )

        with pytest.raises(httpx.HTTPStatusError):
            await wa_service.send_new_asset_message(
                to_phone="5541999887766",
                client_name="Test",
                asset_title="Test",
                thumbnail_url="",
                magic_link_token="tok",
            )


# ---------------------------------------------------------------------------
# 9. test_send_template_network_error
# ---------------------------------------------------------------------------
class TestSendTemplateNetworkError:
    @respx.mock
    async def test_send_template_network_error(self, wa_service):
        """Network connectivity error raises."""
        respx.post(f"{GRAPH_API_BASE}/messages").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.ConnectError):
            await wa_service.send_reminder_message(
                to_phone="5541999887766",
                client_name="Test",
                asset_title="Test",
                thumbnail_url="",
                magic_link_token="tok",
                days_pending=2,
            )


# ---------------------------------------------------------------------------
# 10. test_send_template_logs_success
# ---------------------------------------------------------------------------
class TestSendTemplateLogsSuccess:
    @respx.mock
    async def test_send_template_logs_success(self, wa_service, caplog):
        """Successful send logs the wamid."""
        respx.post(f"{GRAPH_API_BASE}/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.log123"}]})
        )

        with caplog.at_level(logging.INFO, logger="src.approval.services.whatsapp"):
            await wa_service.send_confirmation_message(
                to_phone="5541999887766",
                client_name="ClientAlpha",
                asset_title="Post",
                decision="approved",
            )

        assert "wamid.log123" in caplog.text
        assert "aprovacao_confirmada" in caplog.text
