import logging

from agno.agent import Agent

from src.agents.content_reviewer import review_content
from src.agents.schemas import CombinedReviewResult, ContentReview
from src.bot.keyboards import review_action_keyboard
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)


class ReviewHandler:
    """Orchestrates AI content review flow: fetch task -> review -> send to group."""

    # Standard checklist items always included in every review
    STANDARD_CHECKLIST_ITEMS = [
        "Tom de voz adequado",
        "Ortografia e gramatica",
        "CTAs presentes",
        "Hashtags corretas",
        "Dimensoes e formato",
    ]

    def __init__(
        self,
        review_agent: Agent,
        clickup_client: ClickUpClient,
        rules_engine: RulesEngine,
        bot,
        group_chat_id: int,
        create_checklist: bool = True,
        brand_agent: Agent | None = None,
    ):
        self._agent = review_agent
        self._clickup = clickup_client
        self._rules = rules_engine
        self._bot = bot
        self._group_chat_id = group_chat_id
        self._create_checklist = create_checklist
        self._brand_agent = brand_agent

    async def trigger_review(self, task_id: str, list_id: str) -> None:
        """Called when task moves to 'revisao'. Runs AI review and sends to group."""
        try:
            task = await self._clickup.get_task(task_id)
            comments = await self._clickup.get_comments(task_id)
            comments_text = "\n".join(c.get("comment_text", "") for c in comments)
            client_name = self._rules.get_client_by_list_id(list_id)

            if self._brand_agent:
                combined = await self._run_combined_review(
                    task, comments_text, client_name,
                )
                review = combined.quality
                compliance = combined.compliance
            else:
                review = await review_content(
                    agent=self._agent,
                    task_name=task.get("name", ""),
                    task_description=task.get("description", ""),
                    comments_text=comments_text,
                    client_name=client_name,
                )
                compliance = None

            # A4: Create checklist in ClickUp
            if self._create_checklist:
                await self._create_review_checklist(
                    task_id, review, compliance,
                )

            # Post review as ClickUp comment (like CodeRabbit on PRs)
            clickup_comment = self._format_clickup_comment(review, compliance)
            try:
                await self._clickup.add_comment(task_id, clickup_comment)
                logger.info("Task %s: AI review posted as comment", task_id)
            except Exception:
                logger.exception("Failed to post review comment for task %s", task_id)

            msg = self._format_review_message(task, review, compliance)
            keyboard = review_action_keyboard(task_id)
            # A9: Route to client topic if configured
            topic_id = self._rules.get_client_topic_id(client_name)
            send_kwargs: dict = {
                "chat_id": self._group_chat_id,
                "text": msg,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            }
            if topic_id:
                send_kwargs["message_thread_id"] = topic_id
            await self._bot.send_message(**send_kwargs)
        except Exception:
            logger.exception("Error during content review for task %s", task_id)

    async def _run_combined_review(
        self, task: dict, comments_text: str, client_name: str,
    ) -> CombinedReviewResult:
        """Run combined brand + quality review."""
        from src.agents.review_team import run_combined_review

        return await run_combined_review(
            brand_agent=self._brand_agent,
            quality_agent=self._agent,
            task_name=task.get("name", ""),
            task_description=task.get("description", ""),
            comments_text=comments_text,
            client_name=client_name,
        )

    async def _create_review_checklist(
        self, task_id: str, review: ContentReview, compliance=None,
    ) -> None:
        """A4: Create a review checklist on the ClickUp task."""
        try:
            checklist = await self._clickup.create_checklist(
                task_id, "Revisao IA",
            )
            checklist_id = checklist.get("id", "")
            if not checklist_id:
                logger.warning(
                    "Task %s: checklist created but no ID returned", task_id,
                )
                return

            # Standard items
            for item in self.STANDARD_CHECKLIST_ITEMS:
                await self._clickup.add_checklist_item(checklist_id, item)

            # Issues from AI review
            for issue in review.issues:
                await self._clickup.add_checklist_item(
                    checklist_id, f"[Problema] {issue}",
                )

            # Suggestions from AI review
            for sug in review.suggestions:
                await self._clickup.add_checklist_item(
                    checklist_id, f"[Sugestao] {sug}",
                )

            # Brand compliance violations
            if compliance and compliance.violations:
                for v in compliance.violations:
                    prefix = "[Marca]" if v.severity == "critical" else "[Marca-Aviso]"
                    await self._clickup.add_checklist_item(
                        checklist_id, f"{prefix} {v.detail}",
                    )

            logger.info(
                "Task %s: review checklist created",
                task_id,
            )
        except Exception:
            logger.exception(
                "Failed to create review checklist for task %s", task_id,
            )

    @staticmethod
    def _format_clickup_comment(review: ContentReview, compliance=None) -> str:
        """Format AI review as a ClickUp task comment."""
        status = "Aprovado" if review.approved else "Ajustes necessários"
        if compliance and not compliance.passed:
            status = "Ajustes necessários"

        lines = [
            f"🤖 Revisão IA — Score: {review.overall_score}/10 | {status}",
            "",
            review.summary,
        ]

        if review.issues:
            lines.append("")
            lines.append("❌ Problemas:")
            for issue in review.issues:
                lines.append(f"  • {issue}")

        if review.suggestions:
            lines.append("")
            lines.append("💡 Sugestões:")
            for sug in review.suggestions:
                lines.append(f"  • {sug}")

        if review.checklist:
            lines.append("")
            lines.append("✅ Checklist:")
            for item in review.checklist:
                lines.append(f"  ☐ {item}")

        if compliance and compliance.violations:
            lines.append("")
            lines.append("🎨 Conformidade da Marca:")
            for v in compliance.violations:
                icon = "🔴" if v.severity == "critical" else "🟡"
                lines.append(f"  {icon} {v.detail}")
        elif compliance:
            lines.append("")
            lines.append("🎨 Marca: ✅ Conforme")

        return "\n".join(lines)

    def _format_review_message(
        self, task: dict, review: ContentReview, compliance=None,
    ) -> str:
        """Format the review as a Markdown message for Telegram."""
        task_id = task.get("id", "")
        task_name = task.get("name", "")
        task_url = f"https://app.clickup.com/t/{task_id}"

        # Overall approval considers both quality and compliance
        overall_approved = review.approved
        if compliance and not compliance.passed:
            overall_approved = False

        status_emoji = "✅" if overall_approved else "⚠️"
        status_text = "Aprovado pela IA" if overall_approved else "Precisa de ajustes"

        lines = [
            f"{status_emoji} *Revisao IA - {task_name}*",
            f"Score: *{review.overall_score}/10* | {status_text}",
            "",
            f"_{review.summary}_",
            "",
        ]

        if review.checklist:
            lines.append("*Checklist:*")
            for item in review.checklist:
                lines.append(f"  ✓ {item}")
            lines.append("")

        if review.issues:
            lines.append("*Problemas:*")
            for issue in review.issues:
                lines.append(f"  ✗ {issue}")
            lines.append("")

        if review.suggestions:
            lines.append("*Sugestoes:*")
            for sug in review.suggestions:
                lines.append(f"  → {sug}")
            lines.append("")

        # Brand compliance section
        if compliance and compliance.violations:
            lines.append("*Conformidade da Marca:*")
            for v in compliance.violations:
                icon = "🔴" if v.severity == "critical" else "🟡"
                lines.append(f"  {icon} {v.detail}")
            lines.append("")
        elif compliance:
            lines.append("*Marca:* ✅ Conforme")
            lines.append("")

        lines.append(f"[Abrir no ClickUp]({task_url})")

        return "\n".join(lines)

    async def handle_review_callback(self, update, context) -> None:
        """Handle [Aprovar] / [Pedir Alteracao] button clicks."""
        query = update.callback_query
        await query.answer()
        action, task_id = query.data.split(":", 1)

        if action == "review_approve":
            await self._clickup.update_task(task_id, status="aprovado")
            await query.edit_message_text(
                query.message.text + "\n\n>>> Aprovado pelo revisor."
            )
        elif action == "review_change":
            await self._clickup.update_task(task_id, status="alteracao")
            await query.edit_message_text(
                query.message.text + "\n\n>>> Alteracao solicitada."
            )
