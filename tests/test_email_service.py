"""Tests for the SES email service (src/approval/services/email.py).

All SES interactions are mocked using unittest.mock.patch so no real AWS
credentials or network access are required. Template rendering is tested
against the actual Jinja2 templates on disk.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.approval.services.email import TEMPLATES_DIR, EmailService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FROM_EMAIL = "noreply@app.agency"
PORTAL_DOMAIN = "https://approve.app.agency"
REGION = "us-east-1"

TO_EMAIL = "cliente@example.com"
CLIENT_NAME = "ClientAlpha"
ASSET_TITLE = "Post Instagram Junho"
THUMBNAIL_URL = "https://cdn.app.agency/thumbs/abc.webp"
MAGIC_LINK_TOKEN = "tok_abc123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ses():
    """Patch boto3.client so no real SES calls are made."""
    with patch("src.approval.services.email.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.send_email.return_value = {"MessageId": "fake-message-id-001"}
        yield mock_client


@pytest.fixture
def service(mock_ses):
    """EmailService instance with mocked SES."""
    return EmailService(from_email=FROM_EMAIL, portal_domain=PORTAL_DOMAIN, region=REGION)


# ===========================================================================
# Review URL construction
# ===========================================================================


class TestReviewUrl:
    """Verify the review URL is built correctly from portal_domain + token."""

    def test_builds_review_url(self, service):
        url = service._build_review_url("tok_xyz")
        assert url == "https://approve.app.agency/review?token=tok_xyz"

    def test_strips_trailing_slash(self, mock_ses):
        svc = EmailService(
            from_email=FROM_EMAIL,
            portal_domain="https://approve.app.agency/",
            region=REGION,
        )
        url = svc._build_review_url("tok_abc")
        assert url == "https://approve.app.agency/review?token=tok_abc"

    def test_preserves_token_characters(self, service):
        url = service._build_review_url("eyJhbGciOiJIUzI1NiJ9.test")
        assert url.endswith("?token=eyJhbGciOiJIUzI1NiJ9.test")


# ===========================================================================
# send_new_asset_email
# ===========================================================================


class TestSendNewAssetEmail:
    """send_new_asset_email: sends correct email for new assets."""

    @pytest.mark.asyncio
    async def test_sends_email_with_correct_args(self, service, mock_ses):
        result = await service.send_new_asset_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
        )
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args.kwargs

        assert call_kwargs["Source"] == FROM_EMAIL
        assert call_kwargs["Destination"] == {"ToAddresses": [TO_EMAIL]}
        assert result == {"MessageId": "fake-message-id-001"}

    @pytest.mark.asyncio
    async def test_v1_subject_line(self, service, mock_ses):
        await service.send_new_asset_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            version_number=1,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert CLIENT_NAME in subject
        assert ASSET_TITLE in subject
        assert "Aprova\u00e7\u00e3o pendente" in subject
        assert "Nova vers\u00e3o" not in subject

    @pytest.mark.asyncio
    async def test_v2_subject_line_different(self, service, mock_ses):
        await service.send_new_asset_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            version_number=3,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert CLIENT_NAME in subject
        assert ASSET_TITLE in subject
        assert "Nova vers\u00e3o (v3)" in subject
        assert "Aprova\u00e7\u00e3o pendente" not in subject

    @pytest.mark.asyncio
    async def test_html_contains_review_url(self, service, mock_ses):
        await service.send_new_asset_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        expected_url = f"{PORTAL_DOMAIN}/review?token={MAGIC_LINK_TOKEN}"
        assert expected_url in html

    @pytest.mark.asyncio
    async def test_html_contains_thumbnail(self, service, mock_ses):
        await service.send_new_asset_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        assert THUMBNAIL_URL in html


# ===========================================================================
# send_reminder_email
# ===========================================================================


class TestSendReminderEmail:
    """send_reminder_email: sends reminder with days_pending info."""

    @pytest.mark.asyncio
    async def test_sends_email_successfully(self, service, mock_ses):
        result = await service.send_reminder_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            days_pending=3,
        )
        mock_ses.send_email.assert_called_once()
        assert result == {"MessageId": "fake-message-id-001"}

    @pytest.mark.asyncio
    async def test_subject_contains_aguardando(self, service, mock_ses):
        await service.send_reminder_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            days_pending=5,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert "Aguardando sua aprova\u00e7\u00e3o" in subject

    @pytest.mark.asyncio
    async def test_html_includes_days_pending(self, service, mock_ses):
        await service.send_reminder_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            days_pending=7,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        assert "7 dias" in html

    @pytest.mark.asyncio
    async def test_html_singular_day(self, service, mock_ses):
        await service.send_reminder_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            days_pending=1,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        # Should have "1 dia" (singular) somewhere
        assert "1 dia" in html

    @pytest.mark.asyncio
    async def test_html_contains_amber_button(self, service, mock_ses):
        await service.send_reminder_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            thumbnail_url=THUMBNAIL_URL,
            magic_link_token=MAGIC_LINK_TOKEN,
            days_pending=2,
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        assert "#f59e0b" in html
        assert "Revisar Agora" in html


# ===========================================================================
# send_confirmation_email
# ===========================================================================


class TestSendConfirmationEmail:
    """send_confirmation_email: sends correct confirmation per decision type."""

    @pytest.mark.asyncio
    async def test_approved_subject(self, service, mock_ses):
        await service.send_confirmation_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            decision="approved",
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert "Aprovado" in subject
        assert "\u2705" in subject

    @pytest.mark.asyncio
    async def test_changes_requested_subject(self, service, mock_ses):
        await service.send_confirmation_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            decision="changes_requested",
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert "Altera\u00e7\u00e3o solicitada" in subject
        assert "\U0001f504" in subject

    @pytest.mark.asyncio
    async def test_approved_html_contains_action(self, service, mock_ses):
        await service.send_confirmation_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            decision="approved",
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        assert "Aprovado" in html
        assert ASSET_TITLE in html

    @pytest.mark.asyncio
    async def test_changes_requested_html_contains_action(self, service, mock_ses):
        await service.send_confirmation_email(
            to_email=TO_EMAIL,
            client_name=CLIENT_NAME,
            asset_title=ASSET_TITLE,
            decision="changes_requested",
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        html = call_kwargs["Message"]["Body"]["Html"]["Data"]
        assert "Altera\u00e7\u00e3o solicitada" in html


# ===========================================================================
# _send (internal SES wrapper)
# ===========================================================================


class TestSendInternal:
    """_send: wraps SES send_email with error logging."""

    @pytest.mark.asyncio
    async def test_returns_ses_response(self, service, mock_ses):
        result = await service._send(
            to_email=TO_EMAIL,
            subject="Test Subject",
            html="<html><body>Test</body></html>",
        )
        assert result == {"MessageId": "fake-message-id-001"}

    @pytest.mark.asyncio
    async def test_logs_error_and_reraises_on_failure(self, service, mock_ses):
        mock_ses.send_email.side_effect = Exception("SES quota exceeded")
        with pytest.raises(Exception, match="SES quota exceeded"):
            await service._send(
                to_email=TO_EMAIL,
                subject="Fail Subject",
                html="<html><body>Fail</body></html>",
            )

    @pytest.mark.asyncio
    async def test_ses_called_with_utf8_charset(self, service, mock_ses):
        await service._send(
            to_email=TO_EMAIL,
            subject="Charset test",
            html="<html><body>Charset</body></html>",
        )
        call_kwargs = mock_ses.send_email.call_args.kwargs
        assert call_kwargs["Message"]["Subject"]["Charset"] == "UTF-8"
        assert call_kwargs["Message"]["Body"]["Html"]["Charset"] == "UTF-8"


# ===========================================================================
# Template rendering
# ===========================================================================


class TestTemplateRendering:
    """Verify Jinja2 templates render correctly with variables."""

    def test_templates_dir_exists(self):
        assert TEMPLATES_DIR.is_dir(), f"Templates dir not found: {TEMPLATES_DIR}"

    def test_new_asset_template_exists(self):
        assert (TEMPLATES_DIR / "email_new_asset.html").is_file()

    def test_reminder_template_exists(self):
        assert (TEMPLATES_DIR / "email_reminder.html").is_file()

    def test_new_asset_template_renders(self, service):
        template = service._jinja.get_template("email_new_asset.html")
        html = template.render(
            client_name="ClientDelta",
            asset_title="Banner LinkedIn",
            thumbnail_url="https://example.com/thumb.webp",
            review_url="https://approve.app.agency/review?token=abc",
            version_number=1,
        )
        assert "ClientDelta" in html
        assert "Banner LinkedIn" in html
        assert "https://example.com/thumb.webp" in html
        assert "https://approve.app.agency/review?token=abc" in html
        assert "Revisar e Aprovar" in html
        assert "expira em 7 dias" in html
        assert "#22c55e" in html

    def test_new_asset_template_version_badge_v1(self, service):
        template = service._jinja.get_template("email_new_asset.html")
        html = template.render(
            client_name="Test",
            asset_title="Test Asset",
            thumbnail_url="https://example.com/t.webp",
            review_url="https://example.com/review",
            version_number=1,
        )
        assert "v1" in html
        assert "Nova versao" not in html

    def test_new_asset_template_version_badge_v2(self, service):
        template = service._jinja.get_template("email_new_asset.html")
        html = template.render(
            client_name="Test",
            asset_title="Test Asset",
            thumbnail_url="https://example.com/t.webp",
            review_url="https://example.com/review",
            version_number=2,
        )
        assert "v2" in html
        assert "Nova versao" in html

    def test_reminder_template_renders(self, service):
        template = service._jinja.get_template("email_reminder.html")
        html = template.render(
            client_name="ClientGamma",
            asset_title="Video Institucional",
            thumbnail_url="https://example.com/vid.webp",
            review_url="https://approve.app.agency/review?token=xyz",
            days_pending=5,
        )
        assert "ClientGamma" in html
        assert "Video Institucional" in html
        assert "https://example.com/vid.webp" in html
        assert "https://approve.app.agency/review?token=xyz" in html
        assert "5 dias" in html
        assert "Revisar Agora" in html
        assert "#f59e0b" in html

    def test_reminder_template_singular_day(self, service):
        template = service._jinja.get_template("email_reminder.html")
        html = template.render(
            client_name="Test",
            asset_title="Test",
            thumbnail_url="https://example.com/t.webp",
            review_url="https://example.com/review",
            days_pending=1,
        )
        # Should render "1 dia" (no trailing 's')
        assert "1 dia" in html


# ===========================================================================
# Service initialization
# ===========================================================================


class TestEmailServiceInit:
    """Verify EmailService constructor wires up SES client."""

    def test_stores_from_email(self, service):
        assert service._from_email == FROM_EMAIL

    def test_stores_portal_domain(self, service):
        assert service._portal_domain == PORTAL_DOMAIN

    def test_jinja_env_created(self, service):
        assert service._jinja is not None
        assert service._jinja.loader is not None

    def test_ses_client_created_with_region(self, mock_ses):
        with patch("src.approval.services.email.boto3") as mock_boto3:
            EmailService(
                from_email="a@b.com",
                portal_domain="https://example.com",
                region="eu-west-1",
            )
            mock_boto3.client.assert_called_once_with("ses", region_name="eu-west-1")

    def test_default_region(self, mock_ses):
        with patch("src.approval.services.email.boto3") as mock_boto3:
            EmailService(from_email="a@b.com", portal_domain="https://example.com")
            mock_boto3.client.assert_called_once_with("ses", region_name="us-east-1")
