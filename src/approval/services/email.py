"""SES email service for the client approval portal.

Sends transactional emails for new assets, reminders, and decision confirmations
using Jinja2 HTML templates and AWS SES.
"""

import asyncio
import logging
from functools import partial
from pathlib import Path

import boto3
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class EmailService:
    """Sends approval-portal emails via Amazon SES with Jinja2 templates."""

    def __init__(self, from_email: str, portal_domain: str, region: str = "us-east-1"):
        self._ses = boto3.client("ses", region_name=region)
        self._from_email = from_email
        self._portal_domain = portal_domain
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
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
    async def send_new_asset_email(
        self,
        *,
        to_email: str,
        client_name: str,
        asset_title: str,
        thumbnail_url: str,
        magic_link_token: str,
        version_number: int = 1,
    ) -> dict:
        """Send a 'new asset for review' notification email.

        Uses a different subject line for version > 1 to indicate a new version.

        Returns the SES response dict.
        """
        if version_number > 1:
            subject = (
                f"\U0001f504 {client_name}: {asset_title} "
                f"\u2014 Nova vers\u00e3o (v{version_number})"
            )
        else:
            subject = f"\U0001f4cb {client_name}: {asset_title} \u2014 Aprova\u00e7\u00e3o pendente"

        review_url = self._build_review_url(magic_link_token)
        template = self._jinja.get_template("email_new_asset.html")
        html = template.render(
            client_name=client_name,
            asset_title=asset_title,
            thumbnail_url=thumbnail_url,
            review_url=review_url,
            version_number=version_number,
        )

        return await self._send(to_email=to_email, subject=subject, html=html)

    async def send_reminder_email(
        self,
        *,
        to_email: str,
        client_name: str,
        asset_title: str,
        thumbnail_url: str,
        magic_link_token: str,
        days_pending: int,
    ) -> dict:
        """Send a reminder email for a pending approval.

        Returns the SES response dict.
        """
        subject = (
            f"\u23f0 {client_name}: {asset_title} "
            f"\u2014 Aguardando sua aprova\u00e7\u00e3o"
        )

        review_url = self._build_review_url(magic_link_token)
        template = self._jinja.get_template("email_reminder.html")
        html = template.render(
            client_name=client_name,
            asset_title=asset_title,
            thumbnail_url=thumbnail_url,
            review_url=review_url,
            days_pending=days_pending,
        )

        return await self._send(to_email=to_email, subject=subject, html=html)

    async def send_confirmation_email(
        self,
        *,
        to_email: str,
        client_name: str,
        asset_title: str,
        decision: str,
    ) -> dict:
        """Send a confirmation email after the client records a decision.

        Args:
            decision: Either "approved" or "changes_requested".

        Returns the SES response dict.
        """
        if decision == "approved":
            emoji = "\u2705"
            action = "Aprovado"
        else:
            emoji = "\U0001f504"
            action = "Altera\u00e7\u00e3o solicitada"

        subject = f"{emoji} {client_name}: {asset_title} \u2014 {action}"

        html = (
            f"<html><body>"
            f"<p>Ol\u00e1,</p>"
            f"<p>Sua decis\u00e3o para <strong>{asset_title}</strong> "
            f"({client_name}) foi registrada: <strong>{action}</strong>.</p>"
            f"<p>Obrigado!</p>"
            f"</body></html>"
        )

        return await self._send(to_email=to_email, subject=subject, html=html)

    # ------------------------------------------------------------------
    # Internal SES send wrapper
    # ------------------------------------------------------------------
    async def _send(self, *, to_email: str, subject: str, html: str) -> dict:
        """Send an email via SES (runs blocking call in executor).

        Raises on SES errors after logging the failure.
        """
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self._ses.send_email,
                    Source=self._from_email,
                    Destination={"ToAddresses": [to_email]},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Html": {"Data": html, "Charset": "UTF-8"},
                        },
                    },
                ),
            )
            logger.info("Email sent to %s — MessageId: %s", to_email, response.get("MessageId"))
            return response
        except Exception:
            logger.error("Failed to send email to %s — subject: %s", to_email, subject)
            raise
