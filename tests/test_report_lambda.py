"""Tests for Report Generator Lambda handler (PDF + S3 + SES + Telegram delivery).

F5.3 — Triggered by EventBridge, generates client + internal PDFs,
uploads to S3, sends client PDF via SES email, sends internal PDF via Telegram.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_event():
    """Build a realistic EventBridge event for report generation."""
    return {
        "detail": {
            "report_type": "client",
            "client_name": "ClientDelta",
            "period": "Fevereiro 2026",
            "report_data": {
                "period": "Fevereiro 2026",
                "client_name": "ClientDelta",
                "resumo_executivo": "Mes produtivo.",
                "total_tasks_created": 20,
                "total_tasks_completed": 15,
                "on_time_rate": 0.8,
                "tasks_by_status": {"aprovado": 15},
                "approval_metrics": {
                    "first_approval_rate": 0.6,
                    "avg_review_days": 1.5,
                    "total_alterations": 8,
                    "total_assets_reviewed": 15,
                },
                "time_per_status": {"planejamento": 24.5},
                "bottlenecks": ["Gargalo teste"],
                "recommendations": ["Recomendacao teste"],
                "highlights": ["Destaque teste"],
            },
            "client_email": "client@client_delta.com",
            "account_manager_chat_id": 12345,
        },
    }


@pytest.fixture()
def sample_event_no_email():
    """Event without client email — should skip email delivery."""
    return {
        "detail": {
            "report_type": "client",
            "client_name": "ClientAlpha",
            "period": "Marco 2026",
            "report_data": {
                "period": "Marco 2026",
                "client_name": "ClientAlpha",
                "resumo_executivo": "Resumo teste.",
                "total_tasks_created": 10,
                "total_tasks_completed": 8,
                "on_time_rate": 0.9,
                "tasks_by_status": {"aprovado": 8},
                "approval_metrics": {
                    "first_approval_rate": 0.75,
                    "avg_review_days": 1.0,
                    "total_alterations": 3,
                    "total_assets_reviewed": 8,
                },
                "time_per_status": {},
                "bottlenecks": [],
                "recommendations": [],
                "highlights": [],
            },
            "client_email": "",
            "account_manager_chat_id": 0,
        },
    }


# ---------------------------------------------------------------------------
# 1. Happy path: generates PDFs, uploads to S3, sends email + Telegram
# ---------------------------------------------------------------------------
class TestProcessHappyPath:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_generates_and_delivers(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"client-pdf-bytes"
        mock_internal_pdf.return_value = b"internal-pdf-bytes"
        mock_s3.return_value = "https://s3.example.com/report.pdf"

        result = await _process(sample_event)

        assert result["status"] == "ok"
        assert "client_pdf_url" in result
        assert "internal_pdf_url" in result
        assert mock_s3.call_count == 2  # client + internal
        mock_email.assert_called_once()
        mock_tg.assert_called_once()

    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_s3_keys_contain_client_name_and_date(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"client-pdf"
        mock_internal_pdf.return_value = b"internal-pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"

        await _process(sample_event)

        # Verify S3 upload keys
        calls = mock_s3.call_args_list
        assert len(calls) == 2
        # First call: client PDF
        client_key = calls[0][0][1]  # positional arg: key
        assert "client_delta" in client_key
        assert "cliente" in client_key
        assert client_key.startswith("reports/")
        # Second call: internal PDF
        internal_key = calls[1][0][1]
        assert "client_delta" in internal_key
        assert "interno" in internal_key


# ---------------------------------------------------------------------------
# 2. Skips email when client_email is empty
# ---------------------------------------------------------------------------
class TestProcessSkipsEmailWhenEmpty:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_skips_email_when_empty(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event_no_email,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"pdf"
        mock_internal_pdf.return_value = b"pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"

        result = await _process(sample_event_no_email)

        assert result["status"] == "ok"
        mock_email.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Skips Telegram when account_manager_chat_id is 0
# ---------------------------------------------------------------------------
class TestProcessSkipsTelegramWhenZero:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_skips_telegram_when_zero(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event_no_email,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"pdf"
        mock_internal_pdf.return_value = b"pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"

        result = await _process(sample_event_no_email)

        assert result["status"] == "ok"
        mock_tg.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Email failure is non-fatal
# ---------------------------------------------------------------------------
class TestProcessEmailFailureNonFatal:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_email_failure_nonfatal(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"pdf"
        mock_internal_pdf.return_value = b"pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"
        mock_email.side_effect = Exception("SES down")

        result = await _process(sample_event)

        assert result["status"] == "ok"
        mock_tg.assert_called_once()  # Telegram still sent


# ---------------------------------------------------------------------------
# 5. Telegram failure is non-fatal
# ---------------------------------------------------------------------------
class TestProcessTelegramFailureNonFatal:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_telegram_failure_nonfatal(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event,
    ):
        from lambdas.report_generator.handler import _process

        mock_client_pdf.return_value = b"pdf"
        mock_internal_pdf.return_value = b"pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"
        mock_tg.side_effect = Exception("Telegram API error")

        result = await _process(sample_event)

        assert result["status"] == "ok"
        mock_email.assert_called_once()  # Email still sent


# ---------------------------------------------------------------------------
# 6. MonthlyReport is correctly reconstructed from JSON
# ---------------------------------------------------------------------------
class TestProcessReconstructsMonthlyReport:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler._upload_to_s3")
    @patch("lambdas.report_generator.handler._send_email")
    @patch("lambdas.report_generator.handler._send_telegram")
    @patch("lambdas.report_generator.handler.build_client_pdf")
    @patch("lambdas.report_generator.handler.build_internal_pdf")
    async def test_reconstructs_monthly_report(
        self,
        mock_internal_pdf,
        mock_client_pdf,
        mock_tg,
        mock_email,
        mock_s3,
        sample_event,
    ):
        from lambdas.report_generator.handler import _process
        from src.agents.schemas import MonthlyReport

        mock_client_pdf.return_value = b"pdf"
        mock_internal_pdf.return_value = b"pdf"
        mock_s3.return_value = "https://s3.example.com/report.pdf"

        await _process(sample_event)

        # Verify build_client_pdf received a MonthlyReport object
        report_arg = mock_client_pdf.call_args[0][0]
        assert isinstance(report_arg, MonthlyReport)
        assert report_arg.client_name == "ClientDelta"
        assert report_arg.period == "Fevereiro 2026"
        assert report_arg.approval_metrics.first_approval_rate == 0.6
        assert report_arg.total_tasks_completed == 15


# ---------------------------------------------------------------------------
# 7. _upload_to_s3 calls boto3 correctly
# ---------------------------------------------------------------------------
class TestUploadToS3:
    @patch("lambdas.report_generator.handler._get_s3")
    def test_upload_to_s3(self, mock_get_s3, monkeypatch):
        monkeypatch.setenv("MEDIA_BUCKET", "test-bucket")
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        from lambdas.report_generator.handler import _upload_to_s3

        mock_client = MagicMock()
        mock_get_s3.return_value = mock_client

        url = _upload_to_s3(b"pdf-bytes", "reports/20260227/client_delta-cliente.pdf")

        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="reports/20260227/client_delta-cliente.pdf",
            Body=b"pdf-bytes",
            ContentType="application/pdf",
        )
        assert "test-bucket" in url
        assert "client_delta-cliente.pdf" in url


# ---------------------------------------------------------------------------
# 8. _send_email constructs MIME with attachment
# ---------------------------------------------------------------------------
class TestSendEmail:
    @pytest.mark.asyncio
    @patch("lambdas.report_generator.handler.boto3")
    async def test_send_email_calls_ses(self, mock_boto3, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("SES_FROM_EMAIL", "test@example.com")

        from lambdas.report_generator.handler import _send_email

        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        await _send_email("client@client_delta.com", "ClientDelta", "Fevereiro 2026", b"pdf-bytes")

        mock_ses.send_raw_email.assert_called_once()
        call_kwargs = mock_ses.send_raw_email.call_args[1]
        assert call_kwargs["Source"] == "test@example.com"
        assert "client@client_delta.com" in call_kwargs["Destinations"]


# ---------------------------------------------------------------------------
# 9. _send_telegram sends document via Bot API
# ---------------------------------------------------------------------------
class TestSendTelegram:
    @pytest.mark.asyncio
    async def test_send_telegram_posts_document(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")

        from lambdas.report_generator.handler import _send_telegram

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("lambdas.report_generator.handler.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _send_telegram(12345, b"pdf-bytes", "ClientDelta", "Fevereiro 2026")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "sendDocument" in call_args[0][0]
            assert call_args[1]["data"]["chat_id"] == "12345"

    @pytest.mark.asyncio
    async def test_send_telegram_skips_without_token(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        from lambdas.report_generator.handler import _send_telegram

        # Should not raise, just log warning and return
        with patch("lambdas.report_generator.handler.httpx.AsyncClient") as mock_client_cls:
            await _send_telegram(12345, b"pdf-bytes", "ClientDelta", "Fevereiro 2026")
            mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# 10. generate_report entry point
# ---------------------------------------------------------------------------
class TestGenerateReportEntryPoint:
    @patch("lambdas.report_generator.handler._process", new_callable=AsyncMock)
    def test_generate_report_calls_process(self, mock_process):
        from lambdas.report_generator.handler import generate_report

        expected = {"status": "ok", "client_pdf_url": "url1", "internal_pdf_url": "url2"}
        mock_process.return_value = expected

        result = generate_report({"detail": {}}, context=None)

        assert result == expected
        mock_process.assert_called_once_with({"detail": {}})


# ---------------------------------------------------------------------------
# 11. _get_s3 lazy singleton
# ---------------------------------------------------------------------------
class TestGetS3Singleton:
    def test_returns_boto3_client(self):
        import lambdas.report_generator.handler as h

        # Reset singleton
        h._s3_client = None

        with patch("lambdas.report_generator.handler.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            client1 = h._get_s3()
            client2 = h._get_s3()

            # Should only create once (singleton)
            mock_boto3.client.assert_called_once_with("s3")
            assert client1 is client2

        # Reset for other tests
        h._s3_client = None
