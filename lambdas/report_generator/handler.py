"""Report Generator Lambda -- builds PDF, uploads S3, sends email + Telegram.

Triggered by EventBridge when the bot publishes a MonthlyReportGenerated event.

Flow:
1. Reconstruct MonthlyReport from JSON event detail
2. Generate two PDFs (client + internal) via pdf_builder
3. Upload both to S3
4. Send client PDF via SES email with attachment
5. Send internal PDF via Telegram Bot API to account manager
"""

import asyncio
import io
import logging
import os
from datetime import datetime, timezone

import boto3
import httpx

from lambdas.report_generator.pdf_builder import build_client_pdf, build_internal_pdf
from src.agents.schemas import ApprovalMetrics, MonthlyReport

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Global singletons (Lambda container reuse pattern)
# ---------------------------------------------------------------------------
_s3_client = None


def _get_s3():
    """Lazy-initialise shared S3 client on first invocation."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------
def _upload_to_s3(pdf_bytes: bytes, key: str) -> str:
    """Upload PDF to S3 and return the public URL."""
    bucket = os.environ.get("MEDIA_BUCKET", "approval-media-bucket")
    _get_s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )
    region = os.environ.get("AWS_REGION", "us-east-1")
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


# ---------------------------------------------------------------------------
# Email delivery (SES)
# ---------------------------------------------------------------------------
async def _send_email(
    to_email: str,
    client_name: str,
    period: str,
    pdf_bytes: bytes,
) -> None:
    """Send report email via SES with PDF attachment."""
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    from_email = os.environ.get("SES_FROM_EMAIL", "approvals@example.com")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Relatorio Mensal -- {client_name} -- {period}"
    msg["From"] = from_email
    msg["To"] = to_email

    body = MIMEText(
        f"<h2>Relatorio Mensal -- {client_name}</h2>"
        f"<p>Segue em anexo o relatorio de {period}.</p>"
        f"<p>Agencia Agency</p>",
        "html",
    )
    msg.attach(body)

    attachment = MIMEApplication(pdf_bytes, "pdf")
    filename = (
        f"relatorio-{client_name.lower().replace(' ', '-')}"
        f"-{period.lower().replace(' ', '-')}.pdf"
    )
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    ses.send_raw_email(
        Source=from_email,
        Destinations=[to_email],
        RawMessage={"Data": msg.as_string()},
    )


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------
async def _send_telegram(
    chat_id: int,
    pdf_bytes: bytes,
    client_name: str,
    period: str,
) -> None:
    """Send internal PDF to account manager via Telegram Bot API."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set -- skipping Telegram delivery")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    filename = f"relatorio-interno-{client_name.lower().replace(' ', '-')}.pdf"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            data={
                "chat_id": str(chat_id),
                "caption": f"Relatorio Mensal Interno -- {client_name} -- {period}",
            },
            files={"document": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
        )
        if response.status_code >= 400:
            logger.error(
                "Telegram send failed: %s %s",
                response.status_code,
                response.text,
            )


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
async def _process(event: dict) -> dict:
    """Process EventBridge event: generate PDFs, upload, deliver.

    Args:
        event: EventBridge event with ``detail`` containing report_data,
               client_email, account_manager_chat_id, client_name, period.

    Returns:
        Dict with status, client_pdf_url, and internal_pdf_url.
    """
    detail = event.get("detail", {})
    report_data = detail["report_data"]
    client_email = detail.get("client_email", "")
    account_manager_chat_id = detail.get("account_manager_chat_id", 0)
    client_name = detail["client_name"]
    period = detail["period"]

    # Reconstruct MonthlyReport from JSON
    am_data = report_data.get("approval_metrics", {})
    report = MonthlyReport(
        **{k: v for k, v in report_data.items() if k != "approval_metrics"},
        approval_metrics=ApprovalMetrics(**am_data),
    )

    # Generate PDFs
    client_pdf = build_client_pdf(report)
    internal_pdf = build_internal_pdf(report)

    # Upload to S3
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    safe_name = client_name.lower().replace(" ", "-")
    client_key = f"reports/{ts}/{safe_name}-cliente.pdf"
    internal_key = f"reports/{ts}/{safe_name}-interno.pdf"

    client_url = _upload_to_s3(client_pdf, client_key)
    internal_url = _upload_to_s3(internal_pdf, internal_key)

    # Deliver via email (non-fatal)
    if client_email:
        try:
            await _send_email(client_email, client_name, period, client_pdf)
        except Exception:
            logger.exception("Failed to send email to %s", client_email)

    # Deliver via Telegram (non-fatal)
    if account_manager_chat_id:
        try:
            await _send_telegram(account_manager_chat_id, internal_pdf, client_name, period)
        except Exception:
            logger.exception("Failed to send Telegram to %s", account_manager_chat_id)

    return {
        "status": "ok",
        "client_pdf_url": client_url,
        "internal_pdf_url": internal_url,
    }


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------
def generate_report(event: dict, context: object) -> dict:
    """AWS Lambda handler -- synchronous entry point."""
    return asyncio.get_event_loop().run_until_complete(_process(event))
