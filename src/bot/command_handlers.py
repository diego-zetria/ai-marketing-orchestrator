import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.agents.performance_analyzer import (
    format_account_data,
    format_media_data,
    generate_performance_insight,
)
from src.bot.auth import is_user_authorized
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

DONE_STATUSES = {"aprovado", "pronto"}

VALID_STATUSES = {
    "ativar", "planejamento", "desenvolvimento", "em criação",
    "revisão", "alteração", "aprovado", "pronto", "impedimento",
}

_STATUS_ALIASES: dict[str, str] = {
    "em criacao": "em criação",
    "revisao": "revisão",
    "alteracao": "alteração",
}


_STATUS_EMOJI: dict[str, str] = {
    "ativar": "⚪",
    "planejamento": "📋",
    "desenvolvimento": "🔧",
    "em criação": "🎨",
    "revisão": "👀",
    "alteração": "🔄",
    "impedimento": "🚫",
    "aprovado": "✅",
    "pronto": "🏁",
}


def _normalize_status(raw: str) -> str:
    """Accept unaccented status input and map to ClickUp's accented version."""
    lower = raw.lower()
    return _STATUS_ALIASES.get(lower, lower)

_CLICKUP_URL_RE = re.compile(r"https?://app\.clickup\.com/t/([^/\s]+)")


def _extract_task_id(raw: str) -> str:
    """Extract task ID from a plain ID or ClickUp URL."""
    raw = raw.strip()
    match = _CLICKUP_URL_RE.match(raw)
    if match:
        return match.group(1)
    return raw


async def handle_meuid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with the user's Telegram ID and username."""
    user = update.effective_user
    lines = [
        f"Seu Telegram ID: `{user.id}`",
        f"Nome: {user.full_name}",
    ]
    if user.username:
        lines.append(f"Username: @{user.username}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


_QUERY_MEDIA = """
SELECT ig_media_id, client_name, media_type, caption, permalink,
       published_at, reach, views, likes, comments, saves, shares,
       total_interactions, avg_watch_time_s, clickup_task_id
FROM marketing_bot.media_insights
WHERE client_name = :client_name
AND published_at >= :since
ORDER BY published_at DESC
"""

_QUERY_ACCOUNT = """
SELECT client_name, date, reach, views, follower_count
FROM marketing_bot.account_insights
WHERE client_name = :client_name
AND date >= :since
ORDER BY date ASC
"""


async def _query_media_insights(session_factory, client_name: str, days: int = 30) -> list[dict]:
    """Query media insights for a client from the last N days."""
    from datetime import timedelta

    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    async with session_factory() as session:
        result = await session.execute(
            text(_QUERY_MEDIA),
            {"client_name": client_name, "since": since},
        )
        return [dict(row._mapping) for row in result.fetchall()]


async def _query_account_insights(session_factory, client_name: str, days: int = 30) -> list[dict]:
    """Query account insights for a client from the last N days."""
    from datetime import timedelta

    since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).date()
    async with session_factory() as session:
        result = await session.execute(
            text(_QUERY_ACCOUNT),
            {"client_name": client_name, "since": since},
        )
        return [dict(row._mapping) for row in result.fetchall()]


class CommandHandlers:
    def __init__(
        self,
        clickup_client: ClickUpClient,
        rules_engine: RulesEngine,
        allowed_user_ids: list[int],
        session_factory=None,
        performance_agent=None,
        review_handler=None,
    ):
        self._clickup = clickup_client
        self._rules = rules_engine
        self._allowed_ids = allowed_user_ids
        self._session_factory = session_factory
        self._performance_agent = performance_agent
        self._review_handler = review_handler
        self._list_ids = self._collect_list_ids()

    def _collect_list_ids(self) -> list[str]:
        """Gather all unique list IDs from rules config."""
        ids = set()
        for client_name in self._rules.get_all_clients():
            config = self._rules.get_client_config(client_name)
            if "list_id" in config:
                ids.add(config["list_id"])
        default_lid = self._rules.get_default_list_id()
        if default_lid:
            ids.add(default_lid)
        return list(ids)

    def _build_list_name_map(self) -> dict[str, str]:
        """Map list_id -> display name for the list picker."""
        mapping: dict[str, str] = {}
        for client_name in self._rules.get_all_clients():
            config = self._rules.get_client_config(client_name)
            if "list_id" in config:
                mapping[config["list_id"]] = client_name.replace("_", " ").title()
        default_lid = self._rules.get_default_list_id()
        if default_lid and default_lid not in mapping:
            mapping[default_lid] = "Creative Journey"
        return mapping

    async def _is_authorized(self, user_id: int) -> bool:
        return await is_user_authorized(user_id, self._allowed_ids, self._session_factory)

    async def _fetch_all_tasks(self, **kwargs) -> list[dict]:
        """Fetch tasks from all known lists."""
        all_tasks = []
        for list_id in self._list_ids:
            try:
                tasks = await self._clickup.get_tasks(list_id, **kwargs)
                all_tasks.extend(tasks)
            except Exception:
                logger.exception("Error fetching tasks from list %s", list_id)
        return all_tasks

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show active tasks overview."""
        if not await self._is_authorized(update.effective_user.id):
            return

        all_tasks = await self._fetch_all_tasks(include_closed=False)
        active = [
            t for t in all_tasks
            if t.get("status", {}).get("status", "") not in DONE_STATUSES
        ]

        if not active:
            await update.message.reply_text("Sem tasks ativas no momento.")
            return

        lines = ["*Tasks ativas:*\n"]
        for t in active[:20]:
            status = t.get("status", {}).get("status", "?")
            assignees = ", ".join(
                a.get("username", "?") for a in t.get("assignees", [])
            )
            due = self._format_due_date(t.get("due_date"))
            lines.append(
                f"• `{t['name']}`\n"
                f"  Status: *{status}* | Resp: {assignees or 'ninguem'}"
                f"{f' | Prazo: {due}' if due else ''}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def handle_pendencias(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show overdue tasks."""
        if not await self._is_authorized(update.effective_user.id):
            return

        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        all_tasks = await self._fetch_all_tasks(include_closed=False)

        overdue = [
            t for t in all_tasks
            if t.get("due_date") and int(t["due_date"]) < now_ms
            and t.get("status", {}).get("status", "") not in DONE_STATUSES
        ]

        if not overdue:
            await update.message.reply_text("Nenhuma task atrasada!")
            return

        lines = [f"*{len(overdue)} task(s) atrasada(s):*\n"]
        for t in overdue:
            status = t.get("status", {}).get("status", "?")
            assignees = ", ".join(
                a.get("username", "?") for a in t.get("assignees", [])
            )
            due = self._format_due_date(t.get("due_date"))
            lines.append(
                f"• `{t['name']}`\n"
                f"  Status: *{status}* | Resp: {assignees or 'ninguem'}"
                f"{f' | Prazo: {due}' if due else ''}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def handle_minhas(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show tasks assigned to the requesting user."""
        user_id = update.effective_user.id
        if not await self._is_authorized(user_id):
            return

        clickup_id = self._rules.get_clickup_user_id(user_id)
        if not clickup_id:
            await update.message.reply_text(
                "Seu usuario Telegram nao esta mapeado para o ClickUp. "
                "Peca ao admin para configurar."
            )
            return

        all_tasks = await self._fetch_all_tasks(
            assignees=[int(clickup_id)], include_closed=False,
        )
        active = [
            t for t in all_tasks
            if t.get("status", {}).get("status", "") not in DONE_STATUSES
        ]

        if not active:
            await update.message.reply_text("Voce nao tem tasks ativas no momento.")
            return

        lines = [f"*Suas {len(active)} task(s):*\n"]
        for t in active[:20]:
            status = t.get("status", {}).get("status", "?")
            due = self._format_due_date(t.get("due_date"))
            lines.append(
                f"• `{t['name']}`\n"
                f"  Status: *{status}*"
                f"{f' | Prazo: {due}' if due else ''}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def handle_mover(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Move a task to a new status. Interactive (no args) or direct (/mover <id> <status>)."""
        if not await self._is_authorized(update.effective_user.id):
            return

        args = context.args or []

        # Interactive mode: no args -> show list picker first
        if len(args) == 0:
            list_map = self._build_list_name_map()
            buttons = []
            # "Todas" option first
            buttons.append(
                [InlineKeyboardButton("📂 Todas as listas", callback_data="mover_list_all")]
            )
            for lid, name in sorted(list_map.items(), key=lambda x: x[1]):
                buttons.append(
                    [InlineKeyboardButton(f"📁 {name}", callback_data=f"mover_list_{lid}")]
                )
            buttons.append(
                [InlineKeyboardButton("Cancelar", callback_data="mover_cancel")]
            )
            await update.message.reply_text(
                "Selecione a lista:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        # Direct mode: /mover <id> <status>
        if len(args) < 2:
            await update.message.reply_text(
                "Uso: /mover <task_id> <status>  ou  /mover (interativo)"
            )
            return

        task_id = _extract_task_id(args[0])
        new_status = _normalize_status(" ".join(args[1:]))

        if new_status not in VALID_STATUSES:
            await update.message.reply_text(
                f"Status '{new_status}' invalido.\n"
                f"Status validos: {', '.join(sorted(VALID_STATUSES))}"
            )
            return

        await self._move_task(update.message, task_id, new_status)

    async def handle_mover_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle inline keyboard callbacks for interactive /mover."""
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "mover_cancel":
            await query.edit_message_text("Operação cancelada.")
            return

        # Step 1: user picked a list -> show tasks from that list
        if data.startswith("mover_list_"):
            list_filter = data.removeprefix("mover_list_")
            if list_filter == "all":
                tasks = await self._fetch_all_tasks(include_closed=False)
            else:
                try:
                    tasks = await self._clickup.get_tasks(list_filter, include_closed=False)
                except Exception:
                    logger.exception("Error fetching tasks from list %s", list_filter)
                    await query.edit_message_text("Erro ao buscar tasks desta lista.")
                    return

            active = [t for t in tasks if t.get("status", {}).get("status", "") not in DONE_STATUSES]
            if not active:
                await query.edit_message_text("Nenhuma task ativa nesta lista.")
                return

            now_ms = str(int(datetime.now(tz=timezone.utc).timestamp() * 1000))
            overdue = [t for t in active if t.get("due_date") and t["due_date"] < now_ms]
            upcoming = [t for t in active if t not in overdue]
            overdue.sort(key=lambda t: t.get("due_date") or "0")
            upcoming.sort(key=lambda t: t.get("due_date") or "9")
            sorted_tasks = overdue + upcoming

            buttons = []
            for t in sorted_tasks[:10]:
                name = t["name"][:30]
                status = t.get("status", {}).get("status", "?")
                emoji = _STATUS_EMOJI.get(status, "")
                label = f"{emoji} {name} [{status}]"
                buttons.append(
                    [InlineKeyboardButton(label, callback_data=f"mover_task_{t['id']}")]
                )
            buttons.append(
                [InlineKeyboardButton("Cancelar", callback_data="mover_cancel")]
            )
            await query.edit_message_text(
                f"Selecione a task ({len(active)} ativas):",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return

        # Step 2: user picked a task -> show status buttons
        if data.startswith("mover_task_"):
            task_id = data.removeprefix("mover_task_")
            context.user_data["mover_task_id"] = task_id
            status_buttons = []
            row: list[InlineKeyboardButton] = []
            for s in sorted(VALID_STATUSES):
                emoji = _STATUS_EMOJI.get(s, "")
                row.append(InlineKeyboardButton(
                    f"{emoji} {s}", callback_data=f"mover_status_{s}",
                ))
                if len(row) == 2:
                    status_buttons.append(row)
                    row = []
            if row:
                status_buttons.append(row)
            status_buttons.append(
                [InlineKeyboardButton("Cancelar", callback_data="mover_cancel")]
            )
            await query.edit_message_text(
                "Selecione o novo status:",
                reply_markup=InlineKeyboardMarkup(status_buttons),
            )
            return

        # Step 3: user picked a status -> move the task
        if data.startswith("mover_status_"):
            new_status = data.removeprefix("mover_status_")
            task_id = context.user_data.get("mover_task_id")
            if not task_id:
                await query.edit_message_text("Erro: task nao encontrada. Use /mover novamente.")
                return
            await self._move_task(query, task_id, new_status)

    async def _move_task(self, target, task_id: str, new_status: str) -> None:
        """Execute the task move and reply. target can be Message or CallbackQuery."""
        try:
            await self._clickup.update_task(task_id, status=new_status)
            text = f"Task `{task_id}` movida para *{new_status}*."
            if hasattr(target, "edit_message_text"):
                await target.edit_message_text(text, parse_mode="Markdown")
            else:
                await target.reply_text(text, parse_mode="Markdown")

            # Trigger AI review when moving to "revisão"
            if _normalize_status(new_status) == "revisão" and self._review_handler:
                import asyncio
                task = await self._clickup.get_task(task_id)
                list_id = task.get("list", {}).get("id", "")
                asyncio.create_task(
                    self._review_handler.trigger_review(task_id, list_id)
                )
        except Exception:
            logger.exception("Error moving task %s", task_id)
            err = f"Erro ao mover task `{task_id}`. Verifique o ID e tente novamente."
            if hasattr(target, "edit_message_text"):
                await target.edit_message_text(err)
            else:
                await target.reply_text(err)

    async def handle_comentar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add a comment to a task: /comentar <task_id_or_url> <text>"""
        if not await self._is_authorized(update.effective_user.id):
            return

        args = context.args or []
        if len(args) < 1:
            await update.message.reply_text(
                "Uso: /comentar <task_id ou URL> <texto do comentario>"
            )
            return

        task_id = _extract_task_id(args[0])
        comment_text = " ".join(args[1:])

        if not comment_text:
            await update.message.reply_text(
                "Informe o texto do comentario apos o ID da task."
            )
            return

        try:
            await self._clickup.add_comment(task_id, comment_text)
            await update.message.reply_text(
                f"Comentario adicionado na task `{task_id}`.",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Error adding comment to task %s", task_id)
            await update.message.reply_text(
                f"Erro ao comentar na task `{task_id}`. Verifique o ID e tente novamente."
            )

    async def handle_relatorio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """A10: Show time-per-status report from transition data."""
        if not await self._is_authorized(update.effective_user.id):
            return

        if not self._session_factory:
            await update.message.reply_text(
                "Relatorio indisponivel: banco de dados nao configurado."
            )
            return

        from src.bot.report_handler import generate_time_report

        args = context.args or []
        days = 30
        if args:
            try:
                days = int(args[0])
            except ValueError:
                pass

        report = await generate_time_report(self._session_factory, days=days)
        await update.message.reply_text(report, parse_mode="Markdown")

    async def handle_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show Instagram analytics: /analytics <client>"""
        if not await self._is_authorized(update.effective_user.id):
            return

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Uso: /analytics <cliente>\n"
                "Exemplo: /analytics ClientDelta"
            )
            return

        if not self._session_factory:
            await update.message.reply_text(
                "Analytics indisponivel: banco de dados nao configurado."
            )
            return

        client_name = args[0]

        await update.message.reply_text(
            f"Gerando analise de performance para {client_name}..."
        )

        try:
            media_rows = await _query_media_insights(
                self._session_factory, client_name, days=30,
            )
            account_rows = await _query_account_insights(
                self._session_factory, client_name, days=30,
            )

            if not media_rows and not account_rows:
                await update.message.reply_text(
                    f"Sem dados do Instagram para {client_name}. "
                    "Verifique se a conta esta conectada."
                )
                return

            posts_text = format_media_data(media_rows)
            account_text = format_account_data(account_rows)

            if self._performance_agent:
                insight = await generate_performance_insight(
                    agent=self._performance_agent,
                    client_name=client_name,
                    period="Ultimos 30 dias",
                    posts_data=posts_text,
                    account_data=account_text,
                )
                await update.message.reply_text(insight.formatted_text)
            else:
                await update.message.reply_text(
                    f"Dados de {client_name} (sem agente IA):\n\n{posts_text}"
                )
        except Exception:
            logger.exception("Error generating analytics for %s", client_name)
            await update.message.reply_text(
                "Erro ao gerar analytics. Verifique os logs."
            )

    @staticmethod
    def _format_due_date(due_date_ms: str | None) -> str:
        """Format ClickUp timestamp to DD/MM."""
        if not due_date_ms:
            return ""
        try:
            dt = datetime.fromtimestamp(int(due_date_ms) / 1000, tz=timezone.utc)
            return dt.strftime("%d/%m")
        except (ValueError, TypeError):
            return ""
