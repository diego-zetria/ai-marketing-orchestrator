"""CommentHandler: processes taskCommentPosted webhook events.

Dispatches to:
- A3: Drive link extraction (saves to custom field)
- A1: Auto-status via comment intent detection (confirm or auto mode)

Also provides ``handle_auto_status_callback`` for Telegram inline button responses.
"""
import logging
import re

from src.bot.comment_patterns import detect_intent_dynamic
from src.engine.rules import RulesEngine

logger = logging.getLogger(__name__)

# Regex for Google Drive links in free text
_DRIVE_LINK_RE = re.compile(
    r"https?://drive\.google\.com/\S+",
    re.IGNORECASE,
)


class CommentHandler:
    """Handles taskCommentPosted events from ClickUp webhooks."""

    def __init__(
        self,
        bot,
        rules_engine: RulesEngine,
        clickup_client=None,
        drive_link_field_id: str = "",
        auto_status_mode: str = "confirm",
        group_chat_id: int = 0,
        comment_analyzer_agent=None,
        eventbridge_bus_name: str = "",
        aws_region: str = "us-east-1",
    ):
        self._bot = bot
        self._rules = rules_engine
        self._clickup = clickup_client
        self._drive_link_field_id = drive_link_field_id
        self._auto_status_mode = auto_status_mode
        self._group_chat_id = group_chat_id
        self._analyzer_agent = comment_analyzer_agent
        self._eventbridge_bus_name = eventbridge_bus_name
        self._aws_region = aws_region

    async def handle_comment(self, event: dict) -> None:
        """Process a taskCommentPosted event.

        Extracts comment text and user info, then dispatches to
        Drive link extraction (A3) and intent detection (A1).
        """
        task_id = event.get("task_id", "")
        history_items = event.get("history_items", [])

        if not history_items:
            return

        # ClickUp comment event has comment data in history_items
        comment_data = history_items[0].get("comment", {})
        comment_text = comment_data.get("text_content", "")
        comment_user = history_items[0].get("user", {})
        user_id = str(comment_user.get("id", ""))

        if not comment_text:
            return

        # A3: Extract Drive links
        await self._extract_drive_links(task_id, comment_text, comment_data)

        # A1: Detect intent and propose status change
        await self._detect_and_handle_intent(
            task_id, comment_text, user_id,
        )

    # ------------------------------------------------------------------
    # A3: Drive link extraction
    # ------------------------------------------------------------------
    async def _extract_drive_links(
        self, task_id: str, comment_text: str, comment_data: dict,
    ) -> None:
        """Extract Google Drive links from comment and save to custom field."""
        if not self._clickup or not self._drive_link_field_id:
            return

        links: list[str] = []

        # Check bookmarks in comment data (ClickUp structured comments)
        for item in comment_data.get("comment", []):
            if item.get("type") == "bookmark":
                attrs = item.get("attributes", {})
                url = attrs.get("url", "")
                if "drive.google.com" in url:
                    links.append(url)

        # Also check free text with regex
        text_links = _DRIVE_LINK_RE.findall(comment_text)
        for link in text_links:
            if link not in links:
                links.append(link)

        if not links:
            return

        # Save first Drive link to custom field
        drive_link = links[0]
        try:
            await self._clickup.set_custom_field(
                task_id, self._drive_link_field_id, drive_link,
            )
            logger.info(
                "Task %s: saved Drive link to custom field: %s",
                task_id, drive_link[:60],
            )
        except Exception:
            logger.exception(
                "Failed to save Drive link for task %s", task_id,
            )

    # ------------------------------------------------------------------
    # A1: Intent detection + auto-status
    # ------------------------------------------------------------------
    async def _detect_and_handle_intent(
        self, task_id: str, comment_text: str, user_id: str,
    ) -> None:
        """Detect comment intent and handle status change."""
        if not self._clickup:
            return

        user_role = self._rules.get_user_role_by_clickup_id(user_id)
        if not user_role:
            return

        # Fetch task to get current status
        try:
            task_data = await self._clickup.get_task(task_id)
        except Exception:
            logger.exception(
                "Failed to fetch task %s for intent detection", task_id,
            )
            return

        current_status = task_data.get("status", {}).get("status", "")
        task_name = task_data.get("name", task_id)

        intent = detect_intent_dynamic(self._rules, comment_text, user_role, current_status)
        if intent is None:
            # LLM fallback: analyze ambiguous comments
            if self._analyzer_agent:
                await self._llm_fallback(
                    task_id, task_name, comment_text,
                    user_role, current_status, user_id,
                )
            return

        user_name = self._rules.get_user_name_by_clickup_id(user_id)
        display_name = user_name or user_id

        # client_approval: trigger email flow (no status change)
        if intent.intent_type == "client_approval":
            if self._auto_status_mode == "auto":
                await self._trigger_client_approval(task_id, task_name, display_name)
            else:
                await self._send_client_approval_confirm(
                    task_id, task_name, intent, display_name,
                )
            return

        if self._auto_status_mode == "auto":
            await self._auto_move_status(
                task_id, task_name, intent.target_status, display_name,
            )
        else:
            await self._send_confirm_buttons(
                task_id, task_name, intent, display_name,
            )

    async def _llm_fallback(
        self,
        task_id: str,
        task_name: str,
        comment_text: str,
        user_role: str,
        current_status: str,
        user_id: str,
    ) -> None:
        """LLM fallback: analyze comment with CommentAnalyzerAgent.

        Only called when regex detect_intent returns None. If the LLM
        detects intent and proposes a tool call, the run pauses
        (requires_confirmation) and we send confirm buttons to Telegram.
        """
        from src.agents.comment_analyzer import analyze_comment

        try:
            analysis = await analyze_comment(
                agent=self._analyzer_agent,
                comment_text=comment_text,
                user_role=user_role,
                current_status=current_status,
                task_id=task_id,
                task_name=task_name,
            )
        except Exception:
            logger.exception(
                "LLM comment analysis failed for task %s", task_id,
            )
            return

        if not analysis.has_intent:
            logger.debug(
                "Task %s: LLM found no intent in comment", task_id,
            )
            return

        # The agent proposed a tool call — extract info from requirements
        run_output = analysis.run_output
        if not run_output or not run_output.is_paused:
            return

        user_name = self._rules.get_user_name_by_clickup_id(user_id)
        display_name = user_name or user_id

        # Extract proposed status from the paused tool call
        for req in run_output.requirements or []:
            tool_exec = req.tool_execution
            if not tool_exec:
                continue
            args = tool_exec.tool_args or {}
            new_status = args.get("new_status", "")
            reason = args.get("reason", "")

            if not new_status:
                continue

            # Send confirm buttons (same UX as regex path)
            await self._send_llm_confirm_buttons(
                task_id=task_id,
                task_name=task_name,
                target_status=new_status,
                reason=reason,
                user_name=display_name,
            )
            break  # Only handle first tool call

    async def _send_llm_confirm_buttons(
        self,
        task_id: str,
        task_name: str,
        target_status: str,
        reason: str,
        user_name: str,
    ) -> None:
        """Send confirmation buttons for LLM-proposed status change."""
        if not self._group_chat_id:
            return

        from src.bot.keyboards import auto_status_confirm_keyboard

        text = (
            f"🤖 *IA detectou intencao* de *{user_name}*:\n"
            f"Task: `{task_name}`\n"
            f"Motivo: _{reason}_\n\n"
            f"Mover para *{target_status}*?"
        )

        try:
            await self._bot.send_message(
                chat_id=self._group_chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=auto_status_confirm_keyboard(
                    task_id, target_status,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send LLM confirm for task %s", task_id,
            )

    async def _auto_move_status(
        self,
        task_id: str,
        task_name: str,
        target_status: str,
        moved_by: str,
    ) -> None:
        """Move task status automatically (auto mode)."""
        try:
            await self._clickup.update_task(task_id, status=target_status)
            logger.info(
                "Task %s: auto-moved to '%s' (detected from comment by %s)",
                task_id, target_status, moved_by,
            )
        except Exception:
            logger.exception(
                "Failed to auto-move task %s to %s", task_id, target_status,
            )

    async def _send_confirm_buttons(
        self,
        task_id: str,
        task_name: str,
        intent,
        user_name: str,
    ) -> None:
        """Send confirmation buttons to Telegram (confirm mode)."""
        if not self._group_chat_id:
            return

        from src.bot.keyboards import auto_status_confirm_keyboard

        text = (
            f"Detectei que *{user_name}* comentou "
            f"\"_{intent.matched_pattern}_\" na task:\n"
            f"`{task_name}`\n\n"
            f"Mover para *{intent.target_status}*?"
        )

        try:
            send_kwargs: dict = {
                "chat_id": self._group_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": auto_status_confirm_keyboard(
                    task_id, intent.target_status,
                ),
            }
            # A9: Route to client topic if configured
            if self._clickup:
                try:
                    task_data = await self._clickup.get_task(task_id)
                    list_id = task_data.get("list", {}).get("id", "")
                    if list_id:
                        client_name = self._rules.get_client_by_list_id(list_id)
                        topic_id = self._rules.get_client_topic_id(client_name)
                        if topic_id:
                            send_kwargs["message_thread_id"] = topic_id
                except Exception:
                    pass  # Fallback: send without topic
            await self._bot.send_message(**send_kwargs)
        except Exception:
            logger.exception(
                "Failed to send auto-status confirm for task %s", task_id,
            )

    # ------------------------------------------------------------------
    # Client approval: trigger EventBridge (no status change)
    # ------------------------------------------------------------------
    async def _trigger_client_approval(
        self, task_id: str, task_name: str, triggered_by: str,
    ) -> None:
        """Send EventBridge event to trigger approval email to client."""
        import asyncio

        from src.integrations.eventbridge import send_task_status_event

        if not self._eventbridge_bus_name:
            logger.warning(
                "Task %s: client_approval detected but no EventBridge bus configured",
                task_id,
            )
            return

        loop = asyncio.get_event_loop()
        try:
            ok = await loop.run_in_executor(
                None,
                lambda: send_task_status_event(
                    self._eventbridge_bus_name,
                    task_id,
                    status="client_approval",
                    region=self._aws_region,
                ),
            )
            if ok:
                logger.info(
                    "Task %s: triggered client approval email (by %s)",
                    task_id, triggered_by,
                )
            else:
                logger.warning(
                    "Task %s: EventBridge send failed", task_id,
                )
        except Exception:
            logger.exception(
                "Task %s: failed to trigger client approval", task_id,
            )

    async def _send_client_approval_confirm(
        self,
        task_id: str,
        task_name: str,
        intent,
        user_name: str,
    ) -> None:
        """Send confirmation buttons for sending approval email to client."""
        if not self._group_chat_id:
            return

        from src.bot.keyboards import client_approval_confirm_keyboard

        text = (
            f"Detectei que *{user_name}* quer enviar para o cliente:\n"
            f"`{task_name}`\n\n"
            f"Enviar email de aprovacao para o cliente?"
        )

        try:
            send_kwargs: dict = {
                "chat_id": self._group_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": client_approval_confirm_keyboard(task_id),
            }
            await self._bot.send_message(**send_kwargs)
        except Exception:
            logger.exception(
                "Failed to send client approval confirm for task %s", task_id,
            )

    async def handle_auto_status_callback(self, update, context) -> None:
        """Handle autostatus/clientapproval confirm/ignore Telegram callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data  # e.g. "autostatus_confirm:task_id:status"
        parts = data.split(":", 2)
        if len(parts) < 2:
            return

        action = parts[0]
        task_id = parts[1]

        # Client approval confirm: trigger EventBridge (no status change)
        if action == "clientapproval_confirm":
            try:
                await self._trigger_client_approval(
                    task_id, task_id, "Telegram",
                )
                await query.edit_message_text(
                    f"Email de aprovacao enviado para o cliente "
                    f"(task `{task_id}`).",
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception(
                    "Failed to trigger client approval for task %s", task_id,
                )
                await query.edit_message_text(
                    f"Erro ao enviar aprovacao para task `{task_id}`.",
                    parse_mode="Markdown",
                )
            return

        if action == "clientapproval_ignore":
            await query.edit_message_text(
                f"Envio para cliente ignorado (task `{task_id}`).",
                parse_mode="Markdown",
            )
            return

        # Auto-status confirm/ignore (original flow)
        if len(parts) < 3:
            return

        target_status = parts[2]

        if action == "autostatus_confirm" and self._clickup:
            try:
                await self._clickup.update_task(task_id, status=target_status)
                await query.edit_message_text(
                    f"Task `{task_id}` movida para *{target_status}*.",
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception(
                    "Failed to move task %s to %s via callback",
                    task_id, target_status,
                )
                await query.edit_message_text(
                    f"Erro ao mover task `{task_id}`. Tente manualmente.",
                    parse_mode="Markdown",
                )
        elif action == "autostatus_ignore":
            await query.edit_message_text(
                f"Auto-status ignorado para task `{task_id}`.",
                parse_mode="Markdown",
            )
