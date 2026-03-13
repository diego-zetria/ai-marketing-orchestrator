"""Tests for /analytics command and main.py wiring."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_handle_analytics_no_args():
    from src.bot.command_handlers import CommandHandlers

    handler = CommandHandlers(
        clickup_client=MagicMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123],
        session_factory=MagicMock(),
    )

    update = MagicMock()
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await handler.handle_analytics(update, context)
    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Uso:" in call_text or "/analytics" in call_text


@pytest.mark.asyncio
async def test_handle_analytics_unauthorized():
    from src.bot.command_handlers import CommandHandlers

    handler = CommandHandlers(
        clickup_client=MagicMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123],
        session_factory=None,
    )

    update = MagicMock()
    update.effective_user.id = 999  # not authorized
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["ClientDelta"]

    await handler.handle_analytics(update, context)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_analytics_no_session_factory():
    from src.bot.command_handlers import CommandHandlers

    handler = CommandHandlers(
        clickup_client=MagicMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123],
        session_factory=None,
    )

    update = MagicMock()
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["ClientDelta"]

    await handler.handle_analytics(update, context)
    call_text = update.message.reply_text.call_args[0][0]
    assert "indisponivel" in call_text.lower() or "banco" in call_text.lower()


@pytest.mark.asyncio
async def test_handle_analytics_with_agent():
    from src.agents.schemas import (
        AccountGrowth,
        FormatStats,
        PerformanceInsight,
        PostPerformance,
    )
    from src.bot.command_handlers import CommandHandlers

    mock_insight = PerformanceInsight(
        client_name="ClientDelta",
        period="Ultimos 30 dias",
        resumo="Bom desempenho geral.",
        top_posts=[
            PostPerformance(
                caption_preview="Dica da semana",
                media_type="CAROUSEL_ALBUM",
                published_at="03/03/2026",
                reach=3200,
                engagement_rate=5.8,
                top_metric="saves",
            ),
        ],
        bottom_posts=[],
        format_analysis={
            "CAROUSEL_ALBUM": FormatStats(count=4, avg_reach=2500.0, avg_engagement_rate=4.9),
        },
        trends=["Carrosseis geram mais alcance"],
        recommendations=["Mais carrosseis"],
        account_growth=AccountGrowth(
            followers_start=5000, followers_end=5142,
            followers_change=142, avg_daily_reach=1200.5,
        ),
    )

    handler = CommandHandlers(
        clickup_client=MagicMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123],
        session_factory=MagicMock(),
    )
    handler._performance_agent = MagicMock()

    # Mock the DB queries and agent call
    with patch(
        "src.bot.command_handlers._query_media_insights",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "src.bot.command_handlers._query_account_insights",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "src.bot.command_handlers.generate_performance_insight",
        new_callable=AsyncMock,
        return_value=mock_insight,
    ):
        update = MagicMock()
        update.effective_user.id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["ClientDelta"]

        await handler.handle_analytics(update, context)

    # Should have sent 2 messages: "Gerando..." + result
    assert update.message.reply_text.call_count == 2
    final_text = update.message.reply_text.call_args_list[1][0][0]
    assert "ClientDelta" in final_text


def test_settings_has_instagram_fields():
    from src.config.settings import Settings

    # Ensure required fields exist with defaults
    env = {
        "TELEGRAM_BOT_TOKEN": "test",
        "OPENROUTER_API_KEY": "test",
        "CLICKUP_API_TOKEN": "test",
        "CLICKUP_DEFAULT_LIST_ID": "test",
    }
    with patch.dict(os.environ, env, clear=False):
        s = Settings()
    assert hasattr(s, "meta_app_id")
    assert hasattr(s, "meta_app_secret")
    assert hasattr(s, "instagram_sync_hours")
    assert s.meta_app_id == ""
    assert s.instagram_sync_hours == [6, 12, 18, 0]
