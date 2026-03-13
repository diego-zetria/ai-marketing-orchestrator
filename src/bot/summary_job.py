import logging
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from src.agents.summary_generator import generate_summary
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

DONE_STATUSES = {"aprovado", "pronto"}
BOTTLENECK_THRESHOLD_S = 48 * 3600  # 48 hours
DEADLINE_WINDOW_S = 48 * 3600  # 48 hours


async def collect_task_data(
    clickup_client: ClickUpClient, rules_engine: RulesEngine,
) -> str:
    """Fetch tasks from all lists, categorize, and format as text for the AI agent."""
    list_ids = set()
    for client_name in rules_engine.get_all_clients():
        config = rules_engine.get_client_config(client_name)
        if "list_id" in config:
            list_ids.add(config["list_id"])
    default_lid = rules_engine.get_default_list_id()
    if default_lid:
        list_ids.add(default_lid)

    all_tasks = []
    for list_id in list_ids:
        tasks = await clickup_client.get_tasks(list_id, include_closed=True)
        all_tasks.extend(tasks)

    now_s = datetime.now(tz=timezone.utc).timestamp()
    now_ms = int(now_s * 1000)

    active = []
    done = []
    overdue = []
    bottlenecks = []
    upcoming_deadlines = []

    for t in all_tasks:
        status = t.get("status", {}).get("status", "")
        is_done = status in DONE_STATUSES

        if is_done:
            done.append(t)
            continue

        active.append(t)

        # Overdue check
        due_date = t.get("due_date")
        if due_date and int(due_date) < now_ms:
            overdue.append(t)

        # Upcoming deadline check (within 48h)
        if due_date:
            due_s = int(due_date) / 1000
            if 0 < (due_s - now_s) <= DEADLINE_WINDOW_S:
                upcoming_deadlines.append(t)

        # Bottleneck check (not updated for 48h+)
        date_updated = t.get("date_updated")
        if date_updated:
            updated_s = int(date_updated) / 1000
            if (now_s - updated_s) > BOTTLENECK_THRESHOLD_S:
                bottlenecks.append(t)

    lines = [
        f"Total tasks: {len(all_tasks)}",
        f"Ativas: {len(active)}",
        f"Concluidas: {len(done)}",
        f"Atrasadas: {len(overdue)}",
        "",
    ]

    if overdue:
        lines.append("=== TASKS ATRASADAS ===")
        for t in overdue:
            assignees = ", ".join(a.get("username", "?") for a in t.get("assignees", []))
            resp = assignees or "ninguem"
            lines.append(f"- {t['name']} | Status: {t['status']['status']} | Resp: {resp}")
        lines.append("")

    if bottlenecks:
        lines.append("=== GARGALOS (paradas ha mais de 48h) ===")
        for t in bottlenecks:
            assignees = ", ".join(a.get("username", "?") for a in t.get("assignees", []))
            resp = assignees or "ninguem"
            lines.append(f"- {t['name']} | Status: {t['status']['status']} | Resp: {resp}")
        lines.append("")

    if upcoming_deadlines:
        lines.append("=== DEADLINES PROXIMOS (48h) ===")
        for t in upcoming_deadlines:
            due_dt = datetime.fromtimestamp(int(t["due_date"]) / 1000, tz=timezone.utc)
            lines.append(f"- {t['name']} | Prazo: {due_dt.strftime('%d/%m %H:%M')}")
        lines.append("")

    if active:
        lines.append("=== TODAS AS TASKS ATIVAS ===")
        for t in active:
            assignees = ", ".join(a.get("username", "?") for a in t.get("assignees", []))
            resp = assignees or "ninguem"
            lines.append(f"- {t['name']} | Status: {t['status']['status']} | Resp: {resp}")

    return "\n".join(lines)


async def daily_summary_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: collect data, generate AI summary, send to group."""
    job_data = context.job.data
    clickup_client = job_data["clickup_client"]
    rules_engine = job_data["rules_engine"]
    summary_agent = job_data["summary_agent"]
    group_chat_id = job_data["group_chat_id"]

    try:
        tasks_data = await collect_task_data(clickup_client, rules_engine)
    except Exception:
        logger.exception("Error collecting task data for daily summary")
        await context.bot.send_message(
            chat_id=group_chat_id,
            text="Erro ao coletar dados para o resumo diario. Verifique os logs.",
        )
        return

    try:
        summary = await generate_summary(summary_agent, tasks_data)
        # A9: Send to "geral" topic if configured
        topic_id = rules_engine.get_topic_id("geral") if rules_engine else None
        send_kwargs: dict = {
            "chat_id": group_chat_id,
            "text": summary.resumo,
            "parse_mode": "Markdown",
        }
        if topic_id:
            send_kwargs["message_thread_id"] = topic_id
        await context.bot.send_message(**send_kwargs)
    except Exception:
        logger.exception("Error generating daily summary")
        await context.bot.send_message(
            chat_id=group_chat_id,
            text="Erro ao gerar resumo diario via IA. Verifique os logs.",
        )


async def weekly_summary_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback for weekly summary — same logic, different prompt framing."""
    job_data = context.job.data
    clickup_client = job_data["clickup_client"]
    rules_engine = job_data["rules_engine"]
    summary_agent = job_data["summary_agent"]
    group_chat_id = job_data["group_chat_id"]

    try:
        tasks_data = await collect_task_data(clickup_client, rules_engine)
        tasks_data = "RESUMO SEMANAL:\n" + tasks_data
    except Exception:
        logger.exception("Error collecting task data for weekly summary")
        await context.bot.send_message(
            chat_id=group_chat_id,
            text="Erro ao coletar dados para o resumo semanal. Verifique os logs.",
        )
        return

    try:
        summary = await generate_summary(summary_agent, tasks_data)
        # A9: Send to "geral" topic if configured
        topic_id = rules_engine.get_topic_id("geral") if rules_engine else None
        send_kwargs: dict = {
            "chat_id": group_chat_id,
            "text": summary.resumo,
            "parse_mode": "Markdown",
        }
        if topic_id:
            send_kwargs["message_thread_id"] = topic_id
        await context.bot.send_message(**send_kwargs)
    except Exception:
        logger.exception("Error generating weekly summary")
        await context.bot.send_message(
            chat_id=group_chat_id,
            text="Erro ao gerar resumo semanal via IA. Verifique os logs.",
        )
