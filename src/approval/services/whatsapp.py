"""WhatsApp Business Cloud API service for the client approval portal.

Sends template-based notifications for new assets, reminders, and decision
confirmations via the Meta Graph API.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

TEMPLATE_LANGUAGE = "pt_BR"


class WhatsAppService:
    """Sends approval notifications via WhatsApp Business Cloud API."""

    GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

    def __init__(self, phone_number_id: str, access_token: str, portal_domain: str):
        self._portal_domain = portal_domain
        self._client = httpx.AsyncClient(
            base_url=f"{self.GRAPH_API_BASE}/{phone_number_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Review URL builder
    # ------------------------------------------------------------------
    def _build_review_url(self, token: str) -> str:
        """Build the magic-link review URL from portal domain and token."""
        domain = self._portal_domain.rstrip("/")
        return f"{domain}/review?token={token}"

    # ------------------------------------------------------------------
    # Public send methods
    # ------------------------------------------------------------------
    async def send_new_asset_message(
        self,
        *,
        to_phone: str,
        client_name: str,
        asset_title: str,
        thumbnail_url: str,
        magic_link_token: str,
        version_number: int = 1,
    ) -> dict:
        """Send a 'new asset for review' notification via WhatsApp.

        Uses template ``aprovacao_nova_arte`` with header image, body params,
        and a CTA URL button pointing to the review portal.
        """
        components = []

        if thumbnail_url:
            components.append({
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": thumbnail_url}}],
            })

        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": client_name},
                {"type": "text", "text": asset_title},
                {"type": "text", "text": str(version_number)},
            ],
        })

        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": f"/review?token={magic_link_token}"}],
        })

        return await self._send_template(
            to_phone=to_phone,
            template_name="aprovacao_nova_arte",
            language=TEMPLATE_LANGUAGE,
            components=components,
        )

    async def send_reminder_message(
        self,
        *,
        to_phone: str,
        client_name: str,
        asset_title: str,
        thumbnail_url: str,
        magic_link_token: str,
        days_pending: int,
    ) -> dict:
        """Send a reminder notification for a pending approval.

        Uses template ``aprovacao_lembrete`` with header image, body params,
        and a CTA URL button.
        """
        components = []

        if thumbnail_url:
            components.append({
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": thumbnail_url}}],
            })

        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": client_name},
                {"type": "text", "text": asset_title},
                {"type": "text", "text": str(days_pending)},
            ],
        })

        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": f"/review?token={magic_link_token}"}],
        })

        return await self._send_template(
            to_phone=to_phone,
            template_name="aprovacao_lembrete",
            language=TEMPLATE_LANGUAGE,
            components=components,
        )

    async def send_confirmation_message(
        self,
        *,
        to_phone: str,
        client_name: str,
        asset_title: str,
        decision: str,
    ) -> dict:
        """Send a confirmation message after the client records a decision.

        Uses template ``aprovacao_confirmada`` (body only, no header or button).

        Args:
            decision: Either "approved" or "changes_requested".
        """
        decision_text = "Aprovado" if decision == "approved" else "Alteracao solicitada"

        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": client_name},
                    {"type": "text", "text": asset_title},
                    {"type": "text", "text": decision_text},
                ],
            }
        ]

        return await self._send_template(
            to_phone=to_phone,
            template_name="aprovacao_confirmada",
            language=TEMPLATE_LANGUAGE,
            components=components,
        )

    # ------------------------------------------------------------------
    # Internal template sender
    # ------------------------------------------------------------------
    async def _send_template(
        self,
        *,
        to_phone: str,
        template_name: str,
        language: str,
        components: list[dict],
    ) -> dict:
        """Send a WhatsApp template message via the Graph API.

        Raises on HTTP errors after logging the failure.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }

        try:
            response = await self._client.post("/messages", json=payload)
            response.raise_for_status()
            data = response.json()
            wamid = data.get("messages", [{}])[0].get("id", "unknown")
            logger.info(
                "WhatsApp sent to %s — template: %s, wamid: %s",
                to_phone,
                template_name,
                wamid,
            )
            return data
        except Exception:
            logger.error(
                "Failed to send WhatsApp to %s — template: %s",
                to_phone,
                template_name,
            )
            raise
