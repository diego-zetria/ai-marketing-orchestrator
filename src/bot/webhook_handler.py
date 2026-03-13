import asyncio
import hashlib
import hmac
import logging
from typing import Callable, Coroutine

from src.engine.rules import RulesEngine

logger = logging.getLogger(__name__)

# Status transitions that count as alteration cycles
_ALTERATION_TRANSITIONS = {
    ("revisao", "alteracao"),
    ("revisao_cliente", "alteracao_cliente"),
}


class WebhookHandler:
    """Handles ClickUp webhook events and routes notifications to Telegram."""

    def __init__(
        self,
        bot,
        rules_engine: RulesEngine,
        webhook_secret: str = "",
        review_handler=None,
        event_filter=None,
        clickup_client=None,
        alteration_field_id: str = "",
        auto_assign_enabled: bool = True,
        comment_handler=None,
        session_factory=None,
        eventbridge_bus_name: str = "",
        aws_region: str = "us-east-1",
    ):
        self._bot = bot
        self._rules = rules_engine
        self._secret = webhook_secret
        self._review_handler = review_handler
        self._event_filter = event_filter
        self._clickup = clickup_client
        self._alteration_field_id = alteration_field_id
        self._auto_assign_enabled = auto_assign_enabled
        self._comment_handler = comment_handler
        self._session_factory = session_factory
        self._eventbridge_bus_name = eventbridge_bus_name
        self._aws_region = aws_region

        self._event_handlers: dict[str, Callable[[dict], Coroutine]] = {
            "taskStatusUpdated": self._handle_status_updated,
            "taskCommentPosted": self._handle_comment_posted,
            "taskCreated": self._handle_task_created,
        }

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify ClickUp webhook signature using HMAC-SHA256.

        If no secret is configured, all requests are accepted (useful for dev).
        """
        if not self._secret:
            return True
        expected = hmac.new(
            self._secret.encode(), payload, hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_event(self, event: dict) -> None:
        """Process a ClickUp webhook event via the multi-event dispatcher."""
        event_type = event.get("event", "")

        handler = self._event_handlers.get(event_type)
        if handler is None:
            logger.debug("Ignoring unhandled event type: %s", event_type)
            return

        if self._event_filter:
            task_id = event.get("task_id", "")
            if self._event_filter.is_bot_event(event):
                logger.info("Skipping bot-generated event for task %s", task_id)
                return
            if self._event_filter.is_debounced(task_id, event_type):
                logger.info(
                    "Skipping debounced event %s for task %s",
                    event_type, task_id,
                )
                return

        await handler(event)

    # ------------------------------------------------------------------
    # taskStatusUpdated
    # ------------------------------------------------------------------
    async def _handle_status_updated(self, event: dict) -> None:
        """Handle taskStatusUpdated events — notifications + review triggers."""
        for item in event.get("history_items", []):
            if item.get("field") != "status":
                continue

            after_status = item.get("after", {}).get("status", "")
            before_status = item.get("before", {}).get("status", "")
            task_id = event.get("task_id", "")
            list_id = event.get("list_id", "")
            changed_by = item.get("user", {})

            # Log transition for A10 analytics
            if self._session_factory:
                asyncio.create_task(
                    self._safe_log_transition(
                        task_id=task_id,
                        list_id=list_id,
                        from_status=before_status,
                        to_status=after_status,
                        changed_by=changed_by,
                    )
                )

            # A5: Increment alteration counter on revision->alteration
            if (before_status, after_status) in _ALTERATION_TRANSITIONS:
                asyncio.create_task(
                    self._safe_increment_alterations(task_id)
                )

            notif_config = self._rules.get_notification_rules(after_status)
            if not notif_config:
                continue

            # A2: Smart recipient resolution (assignee-aware)
            await self._send_notification(
                task_id=task_id,
                list_id=list_id,
                before_status=before_status,
                after_status=after_status,
                changed_by=changed_by,
                notif_config=notif_config,
            )

            if after_status == "revisao" and self._review_handler:
                asyncio.create_task(
                    self._safe_trigger_review(task_id, list_id)
                )

            if after_status == "revisao_cliente" and self._eventbridge_bus_name:
                asyncio.create_task(
                    self._safe_trigger_client_approval(task_id)
                )

    # ------------------------------------------------------------------
    # taskCommentPosted — delegates to CommentHandler (A1, A3)
    # ------------------------------------------------------------------
    async def _handle_comment_posted(self, event: dict) -> None:
        """Handle taskCommentPosted events via CommentHandler."""
        if self._comment_handler:
            await self._comment_handler.handle_comment(event)
        else:
            task_id = event.get("task_id", "")
            logger.debug(
                "Comment event for task %s ignored (no CommentHandler)",
                task_id,
            )

    # ------------------------------------------------------------------
    # taskCreated — A7: Auto-assign by client
    # ------------------------------------------------------------------
    async def _handle_task_created(self, event: dict) -> None:
        """Handle taskCreated — auto-assign designer+account by client."""
        if not self._auto_assign_enabled or not self._clickup:
            return

        task_id = event.get("task_id", "")
        list_id = event.get("list_id", "")
        if not task_id or not list_id:
            return

        client_name = self._rules.get_client_by_list_id(list_id)
        if client_name == "default":
            logger.debug(
                "Task %s: no client override for list %s, skipping auto-assign",
                task_id, list_id,
            )
            return

        client_config = self._rules.get_client_config(client_name)
        new_assignees: list[int] = []
        for role_key in ("designer", "account"):
            uid = client_config.get(role_key)
            if uid:
                new_assignees.append(int(uid))

        if not new_assignees:
            return

        try:
            task_data = await self._clickup.get_task(task_id)
            existing_ids = {
                a["id"] for a in task_data.get("assignees", [])
            }
            to_add = [uid for uid in new_assignees if uid not in existing_ids]
            if not to_add:
                logger.debug(
                    "Task %s: assignees already present, skipping",
                    task_id,
                )
                return

            await self._clickup.update_task(
                task_id,
                assignees={"add": to_add, "rem": []},
            )
            logger.info(
                "Task %s: auto-assigned %s for client %s",
                task_id, to_add, client_name,
            )
        except Exception:
            logger.exception(
                "Failed to auto-assign task %s for client %s",
                task_id, client_name,
            )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    async def _send_notification(
        self, *, task_id: str, list_id: str = "",
        before_status: str, after_status: str,
        changed_by: dict, notif_config: dict,
    ) -> None:
        """Build and send Telegram notification.

        Uses smart recipient resolution (A2) when ClickUpClient is available,
        falling back to role-based resolution otherwise.

        A6: When status is "revisao", includes enriched preview with task name,
        client, and Drive link.
        """
        changed_by_name = changed_by.get("username", "Alguem")
        message_verb = notif_config.get("message", "foi atualizada")
        task_url = f"https://app.clickup.com/t/{task_id}"

        # A6: Fetch task data for enriched preview
        task_data = await self._safe_fetch_task(task_id)
        task_name = task_data.get("name", task_id) if task_data else task_id
        client_name = self._rules.get_client_by_list_id(list_id)

        if after_status == "revisao" and task_data:
            text = self._build_rich_notification(
                task_id=task_id,
                task_name=task_name,
                task_url=task_url,
                client_name=client_name,
                changed_by_name=changed_by_name,
                task_data=task_data,
            )
        else:
            text = (
                f"Task `{task_name}` {message_verb}\n"
                f"Status: {before_status} -> *{after_status}*\n"
                f"Movida por: {changed_by_name}\n"
                f"[Abrir no ClickUp]({task_url})"
            )

        chat_ids = await self._resolve_recipients_smart(
            notif_config, task_id, list_id,
        )

        topic_id = self._rules.get_client_topic_id(client_name)
        for chat_id in chat_ids:
            try:
                kwargs: dict = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                }
                if topic_id:
                    kwargs["message_thread_id"] = topic_id
                await self._bot.send_message(**kwargs)
            except Exception:
                logger.exception(
                    "Failed to notify chat_id=%s for task %s",
                    chat_id, task_id,
                )

    def _build_rich_notification(
        self, *, task_id: str, task_name: str, task_url: str,
        client_name: str, changed_by_name: str, task_data: dict,
    ) -> str:
        """A6: Build enriched notification for tasks moving to revisao."""
        drive_link = self._extract_drive_link(task_data)
        client_display = client_name.upper() if client_name != "default" else ""

        lines = [
            "📋 *Revisao necessaria*",
            f"Task: `{task_name}`",
        ]
        if client_display:
            lines.append(f"Cliente: *{client_display}*")
        lines.append(f"Movida por: {changed_by_name}")
        if drive_link:
            lines.append(f"📎 [Link de Entrega]({drive_link})")
        lines.append(f"[Abrir no ClickUp]({task_url})")
        return "\n".join(lines)

    @staticmethod
    def _extract_drive_link(task_data: dict) -> str:
        """Extract Drive link from task custom fields."""
        for cf in task_data.get("custom_fields", []):
            value = cf.get("value", "")
            if isinstance(value, str) and "drive.google.com" in value:
                return value
        return ""

    async def _safe_fetch_task(self, task_id: str) -> dict | None:
        """Fetch task data safely, returning None on error."""
        if not self._clickup:
            return None
        try:
            return await self._clickup.get_task(task_id)
        except Exception:
            logger.warning("Failed to fetch task %s for notification", task_id)
            return None

    async def _resolve_recipients_smart(
        self, notif_config: dict, task_id: str, list_id: str,
    ) -> list[int]:
        """Resolve notification recipients using task assignees when possible.

        A2: If ClickUpClient is available, fetch task to get real assignees
        and map them to Telegram chat IDs. Falls back to role-based resolution.
        """
        if self._clickup and task_id:
            try:
                task_data = await self._clickup.get_task(task_id)
                assignees = task_data.get("assignees", [])
                if assignees:
                    chat_ids = []
                    for a in assignees:
                        cid = self._rules.get_telegram_chat_id(
                            str(a.get("id", "")),
                        )
                        if cid and cid != 0:
                            chat_ids.append(cid)
                    if chat_ids:
                        return chat_ids
            except Exception:
                logger.warning(
                    "Failed to fetch task %s for smart notif, "
                    "falling back to role-based",
                    task_id,
                )

        # Fallback: role-based resolution
        return self._resolve_recipients(notif_config)

    def _resolve_recipients(self, notif_config: dict) -> list[int]:
        """Resolve notification recipients from rules config (role-based)."""
        chat_ids: list[int] = []

        if "notify_roles" in notif_config:
            for role in notif_config["notify_roles"]:
                users = self._rules.get_users_by_role(role)
                for user in users:
                    cid = user.get("telegram_chat_id")
                    if cid and cid != 0:
                        chat_ids.append(cid)

        return chat_ids

    # ------------------------------------------------------------------
    # A5: Alteration counter
    # ------------------------------------------------------------------
    async def _safe_increment_alterations(self, task_id: str) -> None:
        """Increment the alteration count custom field (fire-and-forget)."""
        if not self._clickup or not self._alteration_field_id:
            return
        try:
            task_data = await self._clickup.get_task(task_id)
            current_count = 0
            for cf in task_data.get("custom_fields", []):
                if cf.get("id") == self._alteration_field_id:
                    current_count = int(cf.get("value") or 0)
                    break

            await self._clickup.set_custom_field(
                task_id,
                self._alteration_field_id,
                current_count + 1,
            )
            logger.info(
                "Task %s: alteration count incremented to %d",
                task_id, current_count + 1,
            )
        except Exception:
            logger.exception(
                "Failed to increment alteration count for task %s",
                task_id,
            )

    # ------------------------------------------------------------------
    # Transition logging (A10 data collection)
    # ------------------------------------------------------------------
    async def _safe_log_transition(
        self, *, task_id: str, list_id: str,
        from_status: str, to_status: str, changed_by: dict,
    ) -> None:
        """Log a status transition to the DB (fire-and-forget)."""
        from src.db.transition_logger import log_transition

        client_name = self._rules.get_client_by_list_id(list_id)
        task_name = ""
        try:
            task_data = await self._clickup.get_task(task_id)
            task_name = task_data.get("name", "") if task_data else ""
        except Exception:
            pass
        await log_transition(
            self._session_factory,
            task_id=task_id,
            task_name=task_name,
            list_id=list_id,
            client_name=client_name if client_name != "default" else "",
            from_status=from_status,
            to_status=to_status,
            changed_by_id=str(changed_by.get("id", "")),
            changed_by_name=changed_by.get("username", ""),
        )

    # ------------------------------------------------------------------
    # Client approval trigger (revisao_cliente → EventBridge)
    # ------------------------------------------------------------------
    async def _safe_trigger_client_approval(self, task_id: str) -> None:
        """Send EventBridge event when task moves to revisao_cliente (fire-and-forget)."""
        from src.integrations.eventbridge import send_task_status_event

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
                    "Task %s: EventBridge client_approval event sent (revisao_cliente)",
                    task_id,
                )
            else:
                logger.error(
                    "Task %s: EventBridge client_approval event failed",
                    task_id,
                )
        except Exception:
            logger.exception(
                "Task %s: failed to trigger client approval via EventBridge",
                task_id,
            )

    # ------------------------------------------------------------------
    # Review trigger
    # ------------------------------------------------------------------
    async def _safe_trigger_review(self, task_id: str, list_id: str) -> None:
        """Wrapper to catch errors from fire-and-forget review task."""
        try:
            await self._review_handler.trigger_review(task_id, list_id)
        except Exception:
            logger.exception(
                "Error in fire-and-forget review for task %s", task_id,
            )
