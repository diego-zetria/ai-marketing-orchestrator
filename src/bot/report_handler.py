"""A10: Time report handler — queries task_status_transitions for analytics.

Provides /relatorio command with average time per status, bottleneck detection,
and per-client breakdowns.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Statuses that represent active work (for time-in-status calc)
_ACTIVE_STATUSES = {
    "planejamento", "desenvolvimento", "em criacao",
    "revisao", "alteracao", "aprovado",
}

def _build_query_avg_time(days: int) -> str:
    statuses_sql = ", ".join(f"'{s}'" for s in _ACTIVE_STATUSES)
    return f"""
SELECT
    from_status,
    client_name,
    COUNT(*) AS transitions,
    AVG(EXTRACT(EPOCH FROM (
        COALESCE(next_at, NOW()) - transitioned_at
    ))) AS avg_seconds
FROM (
    SELECT
        t.from_status,
        t.to_status,
        t.client_name,
        t.transitioned_at,
        LEAD(t.transitioned_at) OVER (
            PARTITION BY t.task_id ORDER BY t.transitioned_at
        ) AS next_at
    FROM marketing_bot.task_status_transitions t
    WHERE t.transitioned_at >= NOW() - INTERVAL '{days} days'
) sub
WHERE from_status IN ({statuses_sql})
GROUP BY from_status, client_name
ORDER BY client_name, avg_seconds DESC
"""


def _build_query_bottlenecks(threshold_seconds: int) -> str:
    statuses_sql = ", ".join(f"'{s}'" for s in _ACTIVE_STATUSES)
    return f"""
SELECT
    from_status,
    task_id,
    task_name,
    client_name,
    EXTRACT(EPOCH FROM (NOW() - transitioned_at)) AS seconds_in_status
FROM marketing_bot.task_status_transitions t1
WHERE transitioned_at = (
    SELECT MAX(t2.transitioned_at)
    FROM marketing_bot.task_status_transitions t2
    WHERE t2.task_id = t1.task_id
)
AND from_status IN ({statuses_sql})
AND EXTRACT(EPOCH FROM (NOW() - transitioned_at)) > {threshold_seconds}
ORDER BY seconds_in_status DESC
LIMIT 10
"""


async def generate_time_report(
    session_factory: async_sessionmaker[AsyncSession],
    days: int = 30,
) -> str:
    """Generate a time-per-status report from transition data.

    Returns a formatted text report suitable for Telegram (Markdown).
    """
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(_build_query_avg_time(days)),
            )
            avg_rows = result.fetchall()

            result = await session.execute(
                text(_build_query_bottlenecks(48 * 3600)),
            )
            bottleneck_rows = result.fetchall()

    except Exception:
        logger.exception("Failed to query transition data for report")
        return "Erro ao gerar relatorio. Verifique os logs."

    return _format_report(avg_rows, bottleneck_rows, days)


def _format_report(avg_rows, bottleneck_rows, days: int) -> str:
    """Format query results into a readable Markdown report."""
    lines = [
        f"*Relatorio de Tempo por Status* (ultimos {days} dias)",
        "",
    ]

    if not avg_rows and not bottleneck_rows:
        lines.append("Sem dados de transicao no periodo.")
        return "\n".join(lines)

    # Group by client
    by_client: dict[str, list] = {}
    for row in avg_rows:
        client = row.client_name or "Sem cliente"
        if client not in by_client:
            by_client[client] = []
        by_client[client].append(row)

    for client, rows in sorted(by_client.items()):
        lines.append(f"*{client.upper() if client != 'Sem cliente' else client}:*")
        for row in rows:
            hours = row.avg_seconds / 3600 if row.avg_seconds else 0
            if hours >= 24:
                time_str = f"{hours / 24:.1f}d"
            else:
                time_str = f"{hours:.1f}h"
            lines.append(
                f"  {row.from_status}: ~{time_str} "
                f"({row.transitions} transicoes)"
            )
        lines.append("")

    # Bottlenecks
    if bottleneck_rows:
        lines.append("*Gargalos atuais (>48h no mesmo status):*")
        for row in bottleneck_rows:
            hours = row.seconds_in_status / 3600
            days_stuck = hours / 24
            if days_stuck >= 1:
                time_str = f"{days_stuck:.1f}d"
            else:
                time_str = f"{hours:.1f}h"
            task_display = row.task_name or row.task_id
            client_tag = f" [{row.client_name}]" if row.client_name else ""
            lines.append(
                f"  ⚠️ `{task_display}`{client_tag}\n"
                f"    Status: {row.from_status} ha {time_str}"
            )
        lines.append("")

    return "\n".join(lines)
