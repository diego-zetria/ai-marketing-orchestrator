import json
import logging
from contextlib import asynccontextmanager
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.agents.brand_compliance import create_brand_compliance_agent
from src.agents.briefing_analyzer import create_briefing_agent
from src.agents.comment_analyzer import create_comment_analyzer_agent
from src.agents.content_reviewer import create_review_agent
from src.agents.creative_director import create_creative_director
from src.agents.performance_analyzer import create_performance_analyzer
from src.agents.report_generator import create_report_agent
from src.agents.schedule_generator import create_schedule_agent
from src.agents.summary_generator import create_summary_agent
from src.api.app import create_app
from src.bot.audio_transcriber import AudioTranscriber
from src.bot.command_handlers import CommandHandlers, handle_meuid
from src.bot.comment_handler import CommentHandler
from src.bot.deadline_alert import deadline_alert_callback
from src.bot.event_filter import EventFilter
from src.bot.handlers import BriefingHandler
from src.bot.instagram_sync import (
    refresh_tokens_callback,
    sync_account_callback,
    sync_media_callback,
)
from src.bot.monthly_report_job import (
    ReportDataCollector,
    handle_relatorio_mensal,
    monthly_report_callback,
)
from src.bot.review_handler import ReviewHandler
from src.bot.summary_job import daily_summary_callback, weekly_summary_callback
from src.bot.webhook_handler import WebhookHandler
from src.config.settings import Settings
from src.db.session import create_session_factory
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient
from src.integrations.instagram.client import InstagramClient
from src.observability import is_observability_enabled, setup_observability, shutdown_observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _register_summary_jobs(telegram_app, settings, job_data):
    """Register daily and weekly summary jobs on the JobQueue."""
    tz = ZoneInfo(settings.summary_timezone)
    daily_time = time(
        hour=settings.summary_daily_hour,
        minute=settings.summary_daily_minute,
        tzinfo=tz,
    )
    # Monday 8am weekly summary
    weekly_time = time(hour=9, minute=0, tzinfo=tz)

    telegram_app.job_queue.run_daily(
        daily_summary_callback,
        time=daily_time,
        data=job_data,
        name="daily_summary",
    )
    telegram_app.job_queue.run_daily(
        weekly_summary_callback,
        time=weekly_time,
        days=(0,),  # Monday
        data=job_data,
        name="weekly_summary",
    )
    logger.info(
        "Summary jobs registered: daily at %s, weekly Monday at %s (%s)",
        daily_time, weekly_time, settings.summary_timezone,
    )


def _register_deadline_jobs(telegram_app, settings, job_data):
    """Register deadline alert jobs on the JobQueue."""
    tz = ZoneInfo(settings.summary_timezone)
    alert_job_data = {
        "clickup_client": job_data["clickup_client"],
        "rules_engine": job_data["rules_engine"],
        "group_chat_id": job_data["group_chat_id"],
        "debounce_cache": {},
        "debounce_hours": settings.deadline_alert_debounce_hours,
    }
    for hour in settings.deadline_alert_hours:
        alert_time = time(hour=hour, minute=0, tzinfo=tz)
        telegram_app.job_queue.run_daily(
            deadline_alert_callback,
            time=alert_time,
            data=alert_job_data,
            name=f"deadline_alert_{hour:02d}",
        )
    logger.info(
        "Deadline alert jobs registered at hours %s (%s)",
        settings.deadline_alert_hours, settings.summary_timezone,
    )


def _register_monthly_report_job(telegram_app, settings, report_data):
    """Register monthly report cron job on the JobQueue."""
    tz = ZoneInfo(settings.summary_timezone)
    report_time = time(hour=settings.report_hour, minute=0, tzinfo=tz)
    telegram_app.job_queue.run_monthly(
        monthly_report_callback,
        when=report_time,
        day=settings.report_day_of_month,
        data=report_data,
        name="monthly_report",
    )
    logger.info(
        "Monthly report job registered: day %d at %s (%s)",
        settings.report_day_of_month, report_time, settings.summary_timezone,
    )


def _register_instagram_jobs(telegram_app, settings, ig_job_data):
    """Register Instagram sync jobs on the JobQueue."""
    tz = ZoneInfo(settings.summary_timezone)

    # Media sync at configured hours
    for hour in settings.instagram_sync_hours:
        sync_time = time(hour=hour, minute=0, tzinfo=tz)
        telegram_app.job_queue.run_daily(
            sync_media_callback,
            time=sync_time,
            data=ig_job_data,
            name=f"ig_media_sync_{hour:02d}",
        )

    # Account insights sync daily
    account_time = time(hour=settings.instagram_account_sync_hour, minute=0, tzinfo=tz)
    telegram_app.job_queue.run_daily(
        sync_account_callback,
        time=account_time,
        data=ig_job_data,
        name="ig_account_sync",
    )

    # Token refresh check daily at 3am
    refresh_time = time(hour=3, minute=0, tzinfo=tz)
    telegram_app.job_queue.run_daily(
        refresh_tokens_callback,
        time=refresh_time,
        data=ig_job_data,
        name="ig_token_refresh",
    )

    logger.info(
        "Instagram sync jobs registered: media at %s, account at %s, token refresh at 03:00 (%s)",
        settings.instagram_sync_hours, settings.instagram_account_sync_hour,
        settings.summary_timezone,
    )


def main():
    settings = Settings()

    # Initialize observability (Langfuse + OpenTelemetry)
    if is_observability_enabled():
        obs_ok = setup_observability(service_name="marketing-briefing-bot")
        if obs_ok:
            logger.info("Observability initialized (Langfuse + AgnoInstrumentor)")
        else:
            logger.warning("Observability enabled but failed to initialize")

    agent = create_briefing_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    schedule_agent = create_schedule_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    summary_agent = create_summary_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    review_agent = create_review_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    brand_agent = create_brand_compliance_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    comment_analyzer_agent = create_comment_analyzer_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    report_agent = create_report_agent(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    creative_director_agent = create_creative_director(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    performance_agent = create_performance_analyzer(
        api_key=settings.openrouter_api_key,
        model_id=settings.openrouter_model_id,
    )
    ig_client = InstagramClient()
    audio_transcriber = None
    if settings.groq_api_key or settings.openai_api_key:
        audio_transcriber = AudioTranscriber(
            groq_api_key=settings.groq_api_key,
            openai_api_key=settings.openai_api_key,
        )

    clickup_client = ClickUpClient(api_token=settings.clickup_api_token)
    session_factory = create_session_factory(settings.database_url)

    if settings.rules_engine_mode == "db":
        from src.engine.dynamic_rules import DynamicRulesEngine

        rules_engine = DynamicRulesEngine()
        logger.info("Rules engine: DB mode (DynamicRulesEngine)")
    else:
        rules_path = Path("config/rules.yaml")
        rules_engine = RulesEngine(rules_path)
        logger.info("Rules engine: YAML mode (%s)", rules_path)

    handler = BriefingHandler(
        agent=agent,
        clickup_client=clickup_client,
        rules_engine=rules_engine,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        db_session_factory=session_factory,
        schedule_agent=schedule_agent,
        audio_transcriber=audio_transcriber,
        creative_director_agent=creative_director_agent,
    )

    telegram_app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handler.handle_message)
    )
    telegram_app.add_handler(
        MessageHandler(filters.Document.PDF, handler.handle_document)
    )
    telegram_app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handler.handle_voice)
    )
    telegram_app.add_handler(
        CallbackQueryHandler(handler.handle_schedule_callback, pattern="^schedule_")
    )
    telegram_app.add_handler(
        CallbackQueryHandler(handler.handle_creative_callback, pattern="^creative_")
    )

    review_handler = ReviewHandler(
        review_agent=review_agent,
        clickup_client=clickup_client,
        rules_engine=rules_engine,
        bot=telegram_app.bot,
        group_chat_id=settings.telegram_notification_group_id,
        brand_agent=brand_agent,
    )
    telegram_app.add_handler(
        CallbackQueryHandler(review_handler.handle_review_callback, pattern="^review_")
    )

    cmd_handlers = CommandHandlers(
        clickup_client=clickup_client,
        rules_engine=rules_engine,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        session_factory=session_factory,
        performance_agent=performance_agent,
        review_handler=review_handler,
    )
    telegram_app.add_handler(CommandHandler("meuid", handle_meuid))
    telegram_app.add_handler(CommandHandler("status", cmd_handlers.handle_status))
    telegram_app.add_handler(CommandHandler("pendencias", cmd_handlers.handle_pendencias))
    telegram_app.add_handler(CommandHandler("minhas", cmd_handlers.handle_minhas))
    telegram_app.add_handler(CommandHandler("mover", cmd_handlers.handle_mover))
    telegram_app.add_handler(
        CallbackQueryHandler(cmd_handlers.handle_mover_callback, pattern="^mover_")
    )
    telegram_app.add_handler(CommandHandler("comentar", cmd_handlers.handle_comentar))
    telegram_app.add_handler(CommandHandler("relatorio", cmd_handlers.handle_relatorio))
    telegram_app.add_handler(CommandHandler("relatorio_mensal", handle_relatorio_mensal))
    telegram_app.add_handler(CommandHandler("analytics", cmd_handlers.handle_analytics))

    # Summary jobs data
    job_data = {
        "clickup_client": clickup_client,
        "rules_engine": rules_engine,
        "summary_agent": summary_agent,
        "group_chat_id": settings.telegram_notification_group_id,
    }

    # Monthly report collector + job data
    report_collector = ReportDataCollector(
        clickup_client=clickup_client,
        rules_engine=rules_engine,
        session_factory=session_factory,
        team_id=settings.clickup_team_id,
    )
    report_job_data = {
        "collector": report_collector,
        "report_agent": report_agent,
        "rules_engine": rules_engine,
        "eventbridge_bus_name": settings.eventbridge_bus_name,
        "aws_region": settings.aws_region,
        "group_chat_id": settings.telegram_notification_group_id,
    }

    ig_job_data = {
        "ig_client": ig_client,
        "session_factory": session_factory,
        "clickup_client": clickup_client,
        "rules_engine": rules_engine,
        "team_id": settings.clickup_team_id,
    }

    # Store in bot_data for /relatorio_mensal command access
    telegram_app.bot_data["report_collector"] = report_collector
    telegram_app.bot_data["report_agent"] = report_agent
    telegram_app.bot_data["eventbridge_bus_name"] = settings.eventbridge_bus_name
    telegram_app.bot_data["aws_region"] = settings.aws_region
    telegram_app.bot_data["rules_engine"] = rules_engine

    logger.info(
        f"Starting Marketing Briefing Bot... "
        f"allowed_user_ids={settings.telegram_allowed_user_ids}"
    )

    if settings.telegram_webhook_url:
        logger.info("Webhook mode: %s", settings.telegram_webhook_url)

        @asynccontextmanager
        async def lifespan(app):
            await telegram_app.initialize()
            await telegram_app.bot.set_webhook(
                url=settings.telegram_webhook_url,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram webhook registered: %s", settings.telegram_webhook_url)
            await telegram_app.start()
            if settings.rules_engine_mode == "db":
                await rules_engine.reload(session_factory)
                logger.info("DynamicRulesEngine loaded from DB")
            _register_summary_jobs(telegram_app, settings, job_data)
            _register_deadline_jobs(telegram_app, settings, job_data)
            _register_monthly_report_job(telegram_app, settings, report_job_data)
            _register_instagram_jobs(telegram_app, settings, ig_job_data)
            yield
            # Stop the application (scheduler, pending tasks) but do NOT call
            # telegram_app.updater.stop() or bot.delete_webhook() — during ECS
            # rolling deploys the old container's deleteWebhook races with the
            # new container's setWebhook, leaving the bot unreachable.
            # We only stop the job queue and shut down cleanly.
            if telegram_app.job_queue:
                await telegram_app.job_queue.stop()
            shutdown_observability()

        fastapi_app = create_app(lifespan=lifespan)

        @fastapi_app.post("/webhook/telegram")
        async def telegram_webhook(request: Request):
            data = await request.json()
            update = Update.de_json(data, telegram_app.bot)
            await telegram_app.process_update(update)
            return {"ok": True}

        # Event filter for feedback loop prevention
        event_filter = EventFilter(
            bot_user_id=settings.clickup_bot_user_id,
        ) if settings.clickup_bot_user_id else None

        # Comment handler for A1 (auto-status) and A3 (Drive links)
        comment_handler = CommentHandler(
            bot=telegram_app.bot,
            rules_engine=rules_engine,
            clickup_client=clickup_client,
            drive_link_field_id=settings.clickup_drive_link_field_id,
            auto_status_mode=settings.auto_status_mode,
            group_chat_id=settings.telegram_notification_group_id,
            comment_analyzer_agent=comment_analyzer_agent,
            eventbridge_bus_name=settings.eventbridge_bus_name,
            aws_region=settings.aws_region,
        )
        telegram_app.add_handler(
            CallbackQueryHandler(
                comment_handler.handle_auto_status_callback,
                pattern="^autostatus_",
            )
        )
        telegram_app.add_handler(
            CallbackQueryHandler(
                comment_handler.handle_auto_status_callback,
                pattern="^clientapproval_",
            )
        )

        webhook_handler = WebhookHandler(
            bot=telegram_app.bot,
            rules_engine=rules_engine,
            webhook_secret=settings.clickup_webhook_secret,
            review_handler=review_handler,
            event_filter=event_filter,
            clickup_client=clickup_client,
            alteration_field_id=settings.clickup_alteration_count_field_id,
            auto_assign_enabled=settings.auto_assign_enabled,
            comment_handler=comment_handler,
            session_factory=session_factory,
            eventbridge_bus_name=settings.eventbridge_bus_name,
            aws_region=settings.aws_region,
        )

        @fastapi_app.post("/webhooks/clickup")
        async def clickup_webhook(request: Request):
            body = await request.body()
            signature = request.headers.get("X-Signature", "")

            if not webhook_handler.verify_signature(body, signature):
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid signature"},
                )

            event = json.loads(body)
            await webhook_handler.handle_event(event)
            return {"ok": True}

        uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
    else:
        logger.info("Running in POLLING mode (TELEGRAM_WEBHOOK_URL not set)")
        if settings.rules_engine_mode == "db":
            import asyncio
            asyncio.get_event_loop().run_until_complete(rules_engine.reload(session_factory))
            logger.info("DynamicRulesEngine loaded from DB")
        _register_summary_jobs(telegram_app, settings, job_data)
        _register_deadline_jobs(telegram_app, settings, job_data)
        _register_monthly_report_job(telegram_app, settings, report_job_data)
        _register_instagram_jobs(telegram_app, settings, ig_job_data)
        telegram_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
