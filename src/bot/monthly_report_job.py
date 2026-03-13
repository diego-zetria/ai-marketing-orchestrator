"""F5.3: Monthly report data collection, AI generation, and EventBridge dispatch."""

from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime, timezone

import boto3
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Update
from telegram.ext import ContextTypes

from src.agents.report_generator import generate_report as ai_generate_report
from src.agents.schemas import MonthlyReport
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

_MONTHS_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

_QUERY_APPROVAL_METRICS = """
SELECT
    COUNT(*) FILTER (WHERE ae.event_type = 'decision_made') AS total_reviewed,
    COUNT(*) FILTER (
        WHERE ae.event_type = 'decision_made'
        AND ae.metadata->>'decision' = 'approved'
        AND NOT EXISTS (
            SELECT 1 FROM marketing_bot.approval_events ae2
            WHERE ae2.asset_id = ae.asset_id
            AND ae2.event_type = 'decision_made'
            AND ae2.metadata->>'decision' = 'changes_requested'
            AND ae2.created_at < ae.created_at
        )
    ) AS first_approval_count,
    COUNT(*) FILTER (
        WHERE ae.event_type = 'decision_made'
        AND ae.metadata->>'decision' = 'changes_requested'
    ) AS total_alterations,
    AVG(
        EXTRACT(EPOCH FROM (ae.created_at - aa.created_at)) / 86400.0
    ) FILTER (WHERE ae.event_type = 'decision_made') AS avg_review_days
FROM marketing_bot.approval_events ae
JOIN marketing_bot.approval_assets aa ON aa.id = ae.asset_id
JOIN marketing_bot.clients c ON c.id = aa.client_id
WHERE c.display_name = :client_name
AND ae.created_at >= :start_date
AND ae.created_at < :end_date
"""

_QUERY_TRANSITION_TIMES = """
SELECT
    from_status,
    AVG(EXTRACT(EPOCH FROM (
        COALESCE(next_at, NOW()) - transitioned_at
    ))) / 3600.0 AS avg_hours
FROM (
    SELECT
        t.from_status,
        t.transitioned_at,
        LEAD(t.transitioned_at) OVER (
            PARTITION BY t.task_id ORDER BY t.transitioned_at
        ) AS next_at
    FROM marketing_bot.task_status_transitions t
    WHERE t.client_name = :client_name
    AND t.transitioned_at >= :start_date
    AND t.transitioned_at < :end_date
) sub
GROUP BY from_status
ORDER BY avg_hours DESC
"""

_QUERY_IG_MONTHLY = """
SELECT
    COUNT(*) AS total_posts,
    COALESCE(SUM(reach), 0) AS total_reach,
    CASE WHEN SUM(reach) > 0
         THEN (SUM(total_interactions)::float / SUM(reach)) * 100
         ELSE 0 END AS avg_engagement,
    (SELECT media_type FROM marketing_bot.media_insights mi2
     WHERE mi2.client_name = :client_name
     AND mi2.published_at >= :start_date AND mi2.published_at < :end_date
     GROUP BY media_type
     ORDER BY AVG(
         CASE WHEN reach > 0
         THEN total_interactions::float / reach ELSE 0 END
     ) DESC
     LIMIT 1) AS best_format,
    (SELECT caption FROM marketing_bot.media_insights mi3
     WHERE mi3.client_name = :client_name
     AND mi3.published_at >= :start_date AND mi3.published_at < :end_date
     ORDER BY reach DESC LIMIT 1) AS top_caption,
    (SELECT reach FROM marketing_bot.media_insights mi4
     WHERE mi4.client_name = :client_name
     AND mi4.published_at >= :start_date AND mi4.published_at < :end_date
     ORDER BY reach DESC LIMIT 1) AS top_reach
FROM marketing_bot.media_insights
WHERE client_name = :client_name
AND published_at >= :start_date AND published_at < :end_date
"""

_QUERY_IG_FOLLOWER_CHANGE = """
SELECT
    (SELECT follower_count FROM marketing_bot.account_insights
     WHERE client_name = :client_name AND date >= :start_date AND date < :end_date
     ORDER BY date DESC LIMIT 1)
    -
    (SELECT follower_count FROM marketing_bot.account_insights
     WHERE client_name = :client_name AND date >= :start_date AND date < :end_date
     ORDER BY date ASC LIMIT 1)
AS follower_change
"""


class ReportDataCollector:
    """Collects and aggregates monthly data for a client from ClickUp + DB."""

    def __init__(
        self,
        clickup_client: ClickUpClient,
        rules_engine: RulesEngine,
        session_factory: async_sessionmaker[AsyncSession],
        team_id: str,
    ) -> None:
        self.clickup_client = clickup_client
        self.rules_engine = rules_engine
        self.session_factory = session_factory
        self.team_id = team_id

    def _month_range_ms(self, month: int, year: int) -> tuple[int, int]:
        """Return (start_ms, end_ms) for a given month."""
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    async def collect_client_data(
        self,
        client_name: str,
        month: int,
        year: int,
    ) -> dict:
        """Collect all metrics for a client for a given month."""
        start_ms, end_ms = self._month_range_ms(month, year)
        start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        last_day = calendar.monthrange(year, month)[1]
        end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        # 1. Fetch completed tasks from ClickUp
        tasks = await self.clickup_client.get_filtered_team_tasks(
            team_id=self.team_id,
            date_done_gt=start_ms,
            date_done_lt=end_ms,
        )

        # Filter to this client's tasks
        client_tasks = []
        for t in tasks:
            list_id = t.get("list", {}).get("id", "")
            task_client = self.rules_engine.get_client_by_list_id(list_id)
            if task_client and task_client.lower() == client_name.lower():
                client_tasks.append(t)

        # 2. Compute on-time rate
        completed = len(client_tasks)
        on_time = 0
        for t in client_tasks:
            due = t.get("due_date")
            done = t.get("date_done")
            if due and done and int(done) <= int(due):
                on_time += 1

        on_time_rate = on_time / completed if completed > 0 else 0.0

        # 3. Tasks by status
        status_counts: dict[str, int] = {}
        for t in client_tasks:
            status = t.get("status", {}).get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # 4. Time per status from DB (task_status_transitions table)
        # Note: ClickUp "Total Time in Status" ClickApp is NOT enabled,
        # so we use our own transition log data exclusively.
        time_per_status: dict[str, float] = {}
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    text(_QUERY_TRANSITION_TIMES),
                    {
                        "client_name": client_name,
                        "start_date": start_dt,
                        "end_date": end_dt,
                    },
                )
                for row in result.fetchall():
                    time_per_status[row.from_status] = round(row.avg_hours, 1)
        except Exception:
            logger.exception("Failed to query transition times for %s", client_name)

        # 5. Approval metrics from DB
        approval = {
            "first_approval_rate": 0.0,
            "avg_review_days": 0.0,
            "total_alterations": 0,
            "total_assets_reviewed": 0,
        }
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    text(_QUERY_APPROVAL_METRICS),
                    {
                        "client_name": client_name,
                        "start_date": start_dt,
                        "end_date": end_dt,
                    },
                )
                row = result.fetchone()
                if row and row.total_reviewed:
                    approval["total_assets_reviewed"] = row.total_reviewed
                    approval["first_approval_rate"] = (
                        row.first_approval_count / row.total_reviewed
                        if row.total_reviewed > 0
                        else 0.0
                    )
                    approval["total_alterations"] = row.total_alterations or 0
                    approval["avg_review_days"] = round(row.avg_review_days or 0.0, 1)
        except Exception:
            logger.exception("Failed to query approval metrics for %s", client_name)

        # 6. Instagram metrics (if available)
        ig_metrics = None
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    text(_QUERY_IG_MONTHLY),
                    {
                        "client_name": client_name,
                        "start_date": start_dt,
                        "end_date": end_dt,
                    },
                )
                row = result.fetchone()
                if row and row.total_posts > 0:
                    # Get follower change
                    fc_result = await session.execute(
                        text(_QUERY_IG_FOLLOWER_CHANGE),
                        {
                            "client_name": client_name,
                            "start_date": start_dt,
                            "end_date": end_dt,
                        },
                    )
                    fc_row = fc_result.fetchone()
                    follower_change = (
                        fc_row.follower_change
                        if fc_row and fc_row.follower_change
                        else 0
                    )

                    ig_metrics = {
                        "total_posts_tracked": row.total_posts,
                        "total_reach": row.total_reach,
                        "avg_engagement_rate": round(row.avg_engagement, 1),
                        "best_format": row.best_format or "N/A",
                        "follower_change": follower_change,
                        "top_post_caption": (row.top_caption or "")[:80],
                        "top_post_reach": row.top_reach or 0,
                    }
        except Exception:
            logger.exception("Failed to query Instagram metrics for %s", client_name)

        return {
            "period": f"{_MONTHS_PT[month]} {year}",
            "client_name": client_name,
            "total_tasks_created": completed,  # approximation from done tasks
            "total_tasks_completed": completed,
            "on_time_rate": round(on_time_rate, 2),
            "tasks_by_status": status_counts,
            "approval_metrics": approval,
            "time_per_status": time_per_status,
            "instagram_metrics": ig_metrics,
        }

    async def collect_and_format(
        self,
        client_name: str,
        month: int,
        year: int,
    ) -> str:
        """Collect data and format as text prompt for the AI agent."""
        data = await self.collect_client_data(client_name, month, year)

        lines = [
            f"RELATORIO MENSAL — {data['client_name']} — {data['period']}",
            "",
            f"Tasks concluidas: {data['total_tasks_completed']}",
            f"Taxa de entrega no prazo: {data['on_time_rate']:.0%}",
            "",
            "=== TASKS POR STATUS ===",
        ]
        for status, count in sorted(data["tasks_by_status"].items()):
            lines.append(f"  {status}: {count}")

        lines.append("")
        lines.append("=== METRICAS DE APROVACAO ===")
        am = data["approval_metrics"]
        lines.append(f"  Assets revisados: {am['total_assets_reviewed']}")
        lines.append(f"  Taxa primeira aprovacao: {am['first_approval_rate']:.0%}")
        lines.append(f"  Media dias para decisao: {am['avg_review_days']}")
        lines.append(f"  Total alteracoes: {am['total_alterations']}")

        lines.append("")
        lines.append("=== TEMPO MEDIO POR STATUS (horas) ===")
        for status, hours in sorted(
            data["time_per_status"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            lines.append(f"  {status}: {hours:.1f}h")

        if data.get("instagram_metrics"):
            ig = data["instagram_metrics"]
            lines.append("")
            lines.append("=== METRICAS INSTAGRAM ===")
            lines.append(f"  Posts rastreados: {ig['total_posts_tracked']}")
            lines.append(f"  Alcance total: {ig['total_reach']:,}")
            lines.append(f"  Engajamento medio: {ig['avg_engagement_rate']}%")
            lines.append(f"  Melhor formato: {ig['best_format']}")
            lines.append(f"  Variacao seguidores: {ig['follower_change']:+d}")
            lines.append(
                f"  Melhor post: {ig['top_post_caption']}"
                f" ({ig['top_post_reach']:,} alcance)"
            )

        lines.append("")
        lines.append(
            "Analise os dados acima e gere o relatorio mensal. "
            "Identifique gargalos, destaques positivos e recomendacoes para o proximo mes."
        )
        return "\n".join(lines)


async def _dispatch_to_eventbridge(
    report: MonthlyReport,
    client_email: str,
    account_manager_chat_id: int,
    bus_name: str,
    region: str,
) -> None:
    """Send report to EventBridge for Lambda processing."""
    eb = boto3.client("events", region_name=region)
    eb.put_events(
        Entries=[{
            "Source": "app.bot.reports",
            "DetailType": "MonthlyReportGenerated",
            "EventBusName": bus_name,
            "Detail": json.dumps({
                "report_type": "monthly",
                "client_name": report.client_name,
                "period": report.period,
                "report_data": report.model_dump(mode="json"),
                "client_email": client_email,
                "account_manager_chat_id": account_manager_chat_id,
            }),
        }],
    )


async def monthly_report_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: generate reports for all clients on the 1st."""
    job_data = context.job.data
    collector: ReportDataCollector = job_data["collector"]
    report_agent = job_data["report_agent"]
    rules_engine = job_data["rules_engine"]
    bus_name: str = job_data["eventbridge_bus_name"]
    region: str = job_data["aws_region"]
    group_chat_id: int = job_data["group_chat_id"]

    now = datetime.now(tz=timezone.utc)
    # Report for previous month
    if now.month == 1:
        month, year = 12, now.year - 1
    else:
        month, year = now.month - 1, now.year

    clients = rules_engine.get_all_clients()
    generated = 0

    for client_name in clients:
        try:
            data_text = await collector.collect_and_format(client_name, month, year)
            report = await ai_generate_report(report_agent, data_text)

            config = rules_engine.get_client_config(client_name)
            client_email = config.get("email", "")
            account_id = config.get("account_manager_id", "")
            account_chat_id = (
                rules_engine.get_telegram_chat_id(str(account_id))
                if account_id
                else 0
            ) or 0

            await _dispatch_to_eventbridge(
                report, client_email, account_chat_id, bus_name, region,
            )
            generated += 1
        except Exception:
            logger.exception("Failed to generate report for %s", client_name)

    # Notify group
    try:
        await context.bot.send_message(
            chat_id=group_chat_id,
            text=(
                f"Relatorios mensais gerados: {generated}/{len(clients)} "
                f"clientes ({_MONTHS_PT[month]} {year})"
            ),
        )
    except Exception:
        logger.exception("Failed to send monthly report summary to group")


async def handle_relatorio_mensal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /relatorio_mensal [client] [month] [year] command."""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: /relatorio_mensal <cliente> [mes] [ano]\n"
            "Exemplo: /relatorio_mensal ClientDelta 2 2026"
        )
        return

    client_name = args[0]
    now = datetime.now(tz=timezone.utc)
    month = int(args[1]) if len(args) > 1 else (now.month - 1 or 12)
    year = int(args[2]) if len(args) > 2 else (now.year if month < 13 else now.year - 1)

    job_data = context.bot_data
    collector = job_data.get("report_collector")
    report_agent = job_data.get("report_agent")
    bus_name = job_data.get("eventbridge_bus_name", "")
    region = job_data.get("aws_region", "us-east-1")
    rules_engine = job_data.get("rules_engine")

    if not collector or not report_agent:
        await update.message.reply_text(
            "Relatorio mensal indisponivel — configuracao pendente."
        )
        return

    await update.message.reply_text(
        f"Gerando relatorio de {_MONTHS_PT.get(month, '?')} {year} para {client_name}..."
    )

    try:
        data_text = await collector.collect_and_format(client_name, month, year)
        report = await ai_generate_report(report_agent, data_text)

        config = rules_engine.get_client_config(client_name) if rules_engine else {}
        client_email = config.get("email", "")
        chat_id = update.effective_chat.id

        if bus_name:
            await _dispatch_to_eventbridge(
                report, client_email, chat_id, bus_name, region
            )
            await update.message.reply_text(
                f"Relatorio de {client_name} ({report.period}) enviado para processamento. "
                "O PDF sera entregue em instantes."
            )
        else:
            await update.message.reply_text(
                f"Relatorio gerado (EventBridge nao configurado):\n\n"
                f"{report.resumo_executivo}"
            )
    except Exception:
        logger.exception("Failed to generate on-demand report for %s", client_name)
        await update.message.reply_text("Erro ao gerar relatorio. Verifique os logs.")
