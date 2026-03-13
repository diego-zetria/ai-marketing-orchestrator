import logging
from datetime import datetime, timedelta, timezone

from telegram.ext import ContextTypes

from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

DONE_STATUSES = {"aprovado", "pronto"}
CRITICAL_THRESHOLD_S = 24 * 3600  # 24 hours
ATTENTION_THRESHOLD_S = 48 * 3600  # 48 hours
STALLED_THRESHOLD_S = 24 * 3600  # 24 hours without update


async def collect_at_risk_tasks(
    clickup_client: ClickUpClient,
    rules_engine: RulesEngine,
) -> dict:
    """Fetch tasks from all lists, categorize by deadline risk."""
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

    critical_24h = []
    attention_48h = []
    stalled = []

    for t in all_tasks:
        status = t.get("status", {}).get("status", "")
        if status in DONE_STATUSES:
            continue

        due_date = t.get("due_date")
        if due_date:
            due_ms = int(due_date)
            # Only future deadlines (overdue already covered by /pendencias)
            if due_ms > now_ms:
                remaining_s = (due_ms - now_ms) / 1000
                if remaining_s < CRITICAL_THRESHOLD_S:
                    critical_24h.append(t)
                elif remaining_s < ATTENTION_THRESHOLD_S:
                    attention_48h.append(t)

        # Stalled check (regardless of due_date)
        date_updated = t.get("date_updated")
        if date_updated:
            updated_s = int(date_updated) / 1000
            if (now_s - updated_s) > STALLED_THRESHOLD_S:
                stalled.append(t)

    return {
        "critical_24h": critical_24h,
        "attention_48h": attention_48h,
        "stalled": stalled,
    }


def format_alert_message(at_risk: dict) -> str:
    """Format at-risk tasks into a Markdown alert message."""
    critical = at_risk.get("critical_24h", [])
    attention = at_risk.get("attention_48h", [])
    stalled = at_risk.get("stalled", [])

    total = len(critical) + len(attention) + len(stalled)
    if total == 0:
        return ""

    lines = [f"*ALERTA DE DEADLINE: {total} task(s) em risco*\n"]

    if critical:
        lines.append("*CRITICO (menos de 24h):*")
        for t in critical:
            lines.append(_format_task_line(t))
        lines.append("")

    if attention:
        lines.append("*ATENCAO (menos de 48h):*")
        for t in attention:
            lines.append(_format_task_line(t))
        lines.append("")

    if stalled:
        lines.append("*PARADAS (sem atualizacao ha 24h+):*")
        for t in stalled:
            lines.append(_format_task_line(t))
        lines.append("")

    return "\n".join(lines).strip()


def _format_task_line(task: dict) -> str:
    """Format a single task line for the alert message."""
    name = task.get("name", "?")
    status = task.get("status", {}).get("status", "?")
    assignees = ", ".join(a.get("username", "?") for a in task.get("assignees", []))
    resp = assignees or "ninguem"
    url = task.get("url", f"https://app.clickup.com/t/{task.get('id', '')}")

    due_date = task.get("due_date")
    prazo = ""
    if due_date:
        due_dt = datetime.fromtimestamp(int(due_date) / 1000, tz=timezone.utc)
        prazo = f" | Prazo: {due_dt.strftime('%d/%m %H:%M')}"

    return (
        f"- `{name}`\n"
        f"  Status: *{status}* | Resp: {resp}{prazo}\n"
        f"  [Abrir no ClickUp]({url})"
    )


def should_send_alert(
    task_id: str,
    alert_type: str,
    debounce_cache: dict,
    debounce_hours: int,
) -> bool:
    """Check if alert should be sent (not debounced)."""
    key = (task_id, alert_type)
    last_sent = debounce_cache.get(key)
    if last_sent is None:
        return True
    elapsed = datetime.now(tz=timezone.utc) - last_sent
    return elapsed > timedelta(hours=debounce_hours)


async def send_deadline_alerts(
    *,
    bot,
    at_risk_tasks: dict,
    rules_engine: RulesEngine,
    group_chat_id: int,
    debounce_cache: dict,
    debounce_hours: int,
) -> None:
    """Send individual and group alerts for at-risk tasks."""
    non_debounced = {"critical_24h": [], "attention_48h": [], "stalled": []}

    for category in ("critical_24h", "attention_48h", "stalled"):
        for task in at_risk_tasks.get(category, []):
            task_id = task.get("id", "")
            if not should_send_alert(task_id, category, debounce_cache, debounce_hours):
                continue

            non_debounced[category].append(task)
            debounce_cache[(task_id, category)] = datetime.now(tz=timezone.utc)

            # Individual notification to assignees
            for assignee in task.get("assignees", []):
                clickup_uid = assignee.get("id", "")
                if not clickup_uid:
                    continue
                chat_id = rules_engine.get_telegram_chat_id(clickup_uid)
                if not chat_id:
                    continue
                try:
                    name = task.get("name", "?")
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"Alerta: task `{name}` esta em risco ({category}).",
                        parse_mode="Markdown",
                    )
                except Exception:
                    logger.exception("Error sending individual deadline alert to %s", chat_id)

    # Group message
    group_msg = format_alert_message(non_debounced)
    if group_msg:
        try:
            await bot.send_message(
                chat_id=group_chat_id,
                text=group_msg,
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Error sending group deadline alert")


async def deadline_alert_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: collect at-risk tasks and send alerts."""
    job_data = context.job.data
    clickup_client = job_data["clickup_client"]
    rules_engine = job_data["rules_engine"]
    group_chat_id = job_data["group_chat_id"]
    debounce_cache = job_data["debounce_cache"]
    debounce_hours = job_data["debounce_hours"]

    try:
        at_risk = await collect_at_risk_tasks(clickup_client, rules_engine)
    except Exception:
        logger.exception("Error collecting at-risk tasks for deadline alert")
        await context.bot.send_message(
            chat_id=group_chat_id,
            text="Erro ao coletar dados para alertas de deadline. Verifique os logs.",
        )
        return

    await send_deadline_alerts(
        bot=context.bot,
        at_risk_tasks=at_risk,
        rules_engine=rules_engine,
        group_chat_id=group_chat_id,
        debounce_cache=debounce_cache,
        debounce_hours=debounce_hours,
    )
