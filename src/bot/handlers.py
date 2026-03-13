import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from src.agents.briefing_analyzer import analyze_briefing
from src.agents.content_reviewer import _load_brand_guidelines
from src.agents.creative_director import (
    format_task_history,
    generate_creative_direction,
)
from src.agents.schedule_generator import generate_schedule
from src.agents.schemas import BriefingAnalysis, PostSchedule
from src.agents.seasonal import load_seasonal_data
from src.bot.audio_transcriber import MAX_AUDIO_DURATION, MAX_AUDIO_FILE_SIZE
from src.bot.auth import is_user_authorized
from src.bot.keyboards import (
    creative_direction_keyboard,
    schedule_prompt_keyboard,
    schedule_review_keyboard,
)
from src.bot.pdf_extractor import MAX_FILE_SIZE, extract_text_from_pdf
from src.bot.responses import format_error_response, format_success_response
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient
from src.integrations.clickup.models import CreateTaskRequest

logger = logging.getLogger(__name__)


class BriefingHandler:
    def __init__(
        self,
        agent,
        clickup_client: ClickUpClient,
        rules_engine: RulesEngine,
        allowed_user_ids: list[int],
        db_session_factory=None,
        schedule_agent=None,
        audio_transcriber=None,
        creative_director_agent=None,
    ):
        self._agent = agent
        self._clickup = clickup_client
        self._rules = rules_engine
        self._allowed_ids = allowed_user_ids
        self._db_session_factory = db_session_factory
        self._schedule_agent = schedule_agent
        self._transcriber = audio_transcriber
        self._creative_director = creative_director_agent

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        logger.info(f"Message from user_id={user_id}")
        if not await is_user_authorized(user_id, self._allowed_ids, self._db_session_factory):
            logger.warning(f"User {user_id} not authorized")
            await update.message.reply_text(
                f"Voce nao tem permissao para usar este bot. Seu ID: {user_id}"
            )
            return

        # Check if we're in schedule edit mode
        if context.user_data.get("awaiting_edit"):
            await self.handle_schedule_edit(update, context)
            return

        text = update.message.text
        if not text or len(text.strip()) < 10:
            await update.message.reply_text("Envie um briefing com pelo menos 10 caracteres.")
            return

        await update.message.reply_text("Analisando briefing... aguarde.")

        try:
            await self._process_briefing(update, context, text)
        except Exception as e:
            logger.exception("Error processing briefing")
            await update.message.reply_text(format_error_response(str(e)), parse_mode="Markdown")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler para documentos PDF."""
        user_id = update.effective_user.id
        logger.info(f"Document from user_id={user_id}")
        if not await is_user_authorized(user_id, self._allowed_ids, self._db_session_factory):
            logger.warning(f"User {user_id} not in allowed list")
            await update.message.reply_text(
                f"Voce nao tem permissao para usar este bot. Seu ID: {user_id}"
            )
            return

        document = update.message.document
        if document.mime_type != "application/pdf":
            await update.message.reply_text("Envie apenas arquivos PDF.")
            return

        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("Arquivo muito grande. Maximo: 20MB.")
            return

        await update.message.reply_text("Processando PDF... aguarde.")

        try:
            tg_file = await document.get_file()
            pdf_bytes = bytes(await tg_file.download_as_bytearray())
            text = await extract_text_from_pdf(pdf_bytes, document.file_name or "briefing.pdf")
            await self._process_briefing(update, context, text)
        except ValueError as e:
            await update.message.reply_text(f"Erro no PDF: {e}")
        except Exception as e:
            logger.exception("Error processing PDF briefing")
            await update.message.reply_text(format_error_response(str(e)), parse_mode="Markdown")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler para mensagens de voz e audio."""
        user_id = update.effective_user.id
        logger.info(f"Voice/audio from user_id={user_id}")
        if not await is_user_authorized(user_id, self._allowed_ids, self._db_session_factory):
            await update.message.reply_text(
                f"Voce nao tem permissao para usar este bot. Seu ID: {user_id}"
            )
            return

        if not self._transcriber:
            await update.message.reply_text(
                "Transcricao de audio nao esta configurada. Envie o briefing por texto."
            )
            return

        audio_obj = update.message.voice or update.message.audio
        if not audio_obj:
            return

        if audio_obj.file_size and audio_obj.file_size > MAX_AUDIO_FILE_SIZE:
            await update.message.reply_text(
                f"Arquivo muito grande ({audio_obj.file_size // 1024 // 1024}MB). Maximo: 20MB."
            )
            return

        if audio_obj.duration > MAX_AUDIO_DURATION:
            await update.message.reply_text(
                f"Audio muito longo ({audio_obj.duration}s). "
                f"Maximo: {MAX_AUDIO_DURATION // 60} minutos."
            )
            return

        status_msg = await update.message.reply_text("Transcrevendo audio... aguarde.")

        try:
            tg_file = await audio_obj.get_file()
            audio_bytes = bytes(await tg_file.download_as_bytearray())

            ext = ".ogg" if update.message.voice else self._audio_extension(
                getattr(audio_obj, "mime_type", None),
            )
            filename = f"briefing{ext}"

            text = await self._transcriber.transcribe(audio_bytes, filename)

            if not text or len(text.strip()) < 10:
                await status_msg.edit_text(
                    "Nao foi possivel identificar texto suficiente no audio. "
                    "Tente falar mais claramente ou envie o briefing por texto."
                )
                return

            await status_msg.edit_text("Audio transcrito. Analisando briefing...")
            await self._process_briefing(update, context, text.strip())

        except Exception as e:
            logger.exception("Error processing voice briefing")
            await status_msg.edit_text(
                format_error_response(f"Erro ao processar audio: {e}"),
                parse_mode="Markdown",
            )

    @staticmethod
    def _audio_extension(mime_type: str | None) -> str:
        """Retorna extensao de arquivo baseada no MIME type."""
        mime_map = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-wav": ".wav",
        }
        return mime_map.get(mime_type or "", ".ogg")

    async def _process_briefing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
        text: str,
    ) -> None:
        """Logica comum: analisa briefing e cria tasks, then offers schedule."""
        analysis = await analyze_briefing(self._agent, text)

        if not analysis.is_valid_briefing:
            msg = analysis.rejection_message or (
                "Nao consegui identificar um briefing nessa mensagem.\n\n"
                "Para criar tasks, inclua:\n"
                "- Nome do cliente\n"
                "- Rede social (Instagram, LinkedIn, etc.)\n"
                "- Tipo de conteudo desejado\n"
                "- Mes/ano de referencia"
            )
            await update.message.reply_text(msg)
            return
        # Skip subtasks when schedule agent is available - cronograma will create them
        skip_subtasks = self._schedule_agent is not None
        tasks_info, list_id, parent_id = await self._create_tasks(
            analysis, skip_subtasks=skip_subtasks,
        )
        response = format_success_response(analysis, tasks_info)
        await update.message.reply_text(response, parse_mode="Markdown")

        # Store state for schedule / creative direction flow
        if self._schedule_agent or self._creative_director:
            context.user_data["briefing_text"] = text
            context.user_data["analysis"] = analysis
            context.user_data["parent_task_id"] = parent_id
            context.user_data["list_id"] = list_id

        # Creative Direction step (F5.1)
        if self._creative_director:
            try:
                await update.message.reply_text("Gerando sugestoes criativas... aguarde.")
                direction = await self._generate_creative_direction(analysis)
                context.user_data["creative_direction"] = direction
                text_to_send = direction.formatted_text
                # Telegram limit is 4096 chars; split if needed
                if len(text_to_send) > 4000:
                    # Send body without keyboard, then keyboard on last chunk
                    while len(text_to_send) > 4000:
                        split_at = text_to_send.rfind("\n", 0, 4000)
                        if split_at == -1:
                            split_at = 4000
                        await update.message.reply_text(text_to_send[:split_at])
                        text_to_send = text_to_send[split_at:].lstrip("\n")
                await update.message.reply_text(
                    text_to_send,
                    reply_markup=creative_direction_keyboard(),
                )
                return  # Wait for creative callback before schedule
            except Exception as e:
                logger.exception("Error generating creative direction")
                await update.message.reply_text(
                    f"Nao foi possivel gerar sugestoes criativas: {e}\n"
                    "Seguindo para o cronograma..."
                )
                # Fall through to schedule prompt

        if self._schedule_agent:
            await update.message.reply_text(
                "Deseja gerar o cronograma de posts para este cliente?",
                reply_markup=schedule_prompt_keyboard(),
            )

    async def handle_schedule_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle inline keyboard callbacks for the schedule flow."""
        query = update.callback_query
        await query.answer()

        action = query.data

        if action == "schedule_skip":
            await query.edit_message_text(
                "Ok, cronograma pulado. Envie outro briefing quando quiser."
            )
            return

        if action == "schedule_generate" or action == "schedule_regenerate":
            await self._generate_and_show_schedule(query, context)
            return

        if action == "schedule_approve":
            await self._approve_schedule(query, context)
            return

        if action == "schedule_edit":
            context.user_data["awaiting_edit"] = True
            await query.edit_message_text(
                "Envie uma mensagem com os ajustes desejados.\n"
                "Ex: 'troca o post 3 por um reels e adiciona story dia 15/03'"
            )
            return

    async def _generate_and_show_schedule(self, query, context) -> None:
        """Generate schedule via AI and show to user."""
        analysis = context.user_data.get("analysis")
        briefing_text = context.user_data.get("briefing_text", "")

        try:
            schedule = await generate_schedule(
                agent=self._schedule_agent,
                briefing_text=briefing_text,
                client_name=analysis.client_name,
                social_network=analysis.social_network,
                month=analysis.month,
                year=analysis.year,
            )
            context.user_data["schedule"] = schedule

            network = analysis.social_network.capitalize()
            month = analysis.month.capitalize()
            client = analysis.client_name
            header = (
                f"Cronograma {network} - {client}"
                f" - {month} {analysis.year}\n\n"
            )
            await query.edit_message_text(
                text=header + schedule.formatted_text,
                reply_markup=schedule_review_keyboard(),
            )
        except Exception as e:
            logger.exception("Error generating schedule")
            await query.edit_message_text(f"Erro ao gerar cronograma: {e}")

    async def _approve_schedule(self, query, context) -> None:
        """Create ClickUp subtasks from the approved schedule."""
        schedule: PostSchedule = context.user_data.get("schedule")
        analysis = context.user_data.get("analysis")
        parent_id = context.user_data.get("parent_task_id")

        if not schedule or not parent_id:
            await query.edit_message_text("Erro: dados do cronograma nao encontrados.")
            return

        client_name_lower = analysis.client_name.lower()
        designer_id = self._rules.get_client_designer(client_name_lower)
        list_id = context.user_data.get("list_id")
        if not list_id:
            config = self._rules.get_client_config(client_name_lower)
            list_id = config.get("list_id") or self._rules.get_assignment(
                "design", client_name=client_name_lower,
            ).list_id

        try:
            created_count = 0
            for post in schedule.posts:
                due_date_ms = self._parse_due_date(post.date, analysis.year)
                assignees = [int(designer_id)] if designer_id else []

                subtask = CreateTaskRequest(
                    name=post.task_name,
                    status="desenvolvimento",
                    parent=parent_id,
                    assignees=assignees,
                    due_date=due_date_ms,
                )
                await self._clickup.create_task(list_id=list_id, task=subtask)
                created_count += 1

            await query.edit_message_text(
                f"{created_count} subtasks do cronograma criadas no ClickUp!"
            )
        except Exception as e:
            logger.exception("Error creating schedule subtasks")
            await query.edit_message_text(f"Erro ao criar subtasks: {e}")

    async def handle_schedule_edit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle free-text edit instructions for the schedule."""
        context.user_data["awaiting_edit"] = False
        edit_text = update.message.text
        schedule = context.user_data.get("schedule")
        analysis = context.user_data.get("analysis")
        briefing_text = context.user_data.get("briefing_text", "")

        try:
            prompt = (
                f"Ajuste o cronograma abaixo conforme a instrucao do usuario.\n\n"
                f"Cronograma atual:\n{schedule.formatted_text}\n\n"
                f"Instrucao do usuario: {edit_text}\n\n"
                f"Briefing original:\n{briefing_text}"
            )

            adjusted = await generate_schedule(
                agent=self._schedule_agent,
                briefing_text=prompt,
                client_name=analysis.client_name,
                social_network=analysis.social_network,
                month=analysis.month,
                year=analysis.year,
            )
            context.user_data["schedule"] = adjusted

            header = "Cronograma ajustado:\n\n"
            await update.message.reply_text(
                header + adjusted.formatted_text,
                reply_markup=schedule_review_keyboard(),
            )
        except Exception as e:
            logger.exception("Error editing schedule")
            await update.message.reply_text(f"Erro ao ajustar cronograma: {e}")

    @staticmethod
    def _parse_due_date(date_str: str, year: str) -> int | None:
        """Parse 'DD/MM' + year into Unix timestamp ms for ClickUp."""
        try:
            day, month = date_str.split("/")
            dt = datetime(int(year), int(month), int(day), 12, 0, 0, tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None

    async def _create_tasks(
        self, analysis: BriefingAnalysis, *, skip_subtasks: bool = False,
    ) -> tuple[list[dict], str, str]:
        first_assignment = self._rules.get_assignment(
            analysis.posts[0].service_type if analysis.posts else "design",
            client_name=analysis.client_name,
        )
        list_id = first_assignment.list_id

        priority = 1 if analysis.urgency == "urgent" else 3

        parent_request = CreateTaskRequest(
            name=analysis.card_title,
            description=analysis.project_summary,
            priority=priority,
            status="planejamento",
        )
        parent_result = await self._clickup.create_task(
            list_id=list_id, task=parent_request,
        )
        parent_id = parent_result["id"]

        tasks_info = []
        if skip_subtasks:
            # Only build info for the response, don't create ClickUp subtasks
            for post in analysis.posts:
                assignment = self._rules.get_assignment(
                    post.service_type, client_name=analysis.client_name,
                )
                tasks_info.append({
                    "title": post.title,
                    "assignees": assignment.assignees,
                    "parent_id": parent_id,
                })
        else:
            for post in analysis.posts:
                assignment = self._rules.get_assignment(
                    post.service_type, client_name=analysis.client_name,
                )
                subtask_request = CreateTaskRequest(
                    name=post.title,
                    description=post.description,
                    assignees=[int(a) for a in assignment.assignees if a.isdigit()],
                    tags=assignment.tags,
                    parent=parent_id,
                )
                await self._clickup.create_task(list_id=list_id, task=subtask_request)
                tasks_info.append({
                    "title": post.title,
                    "assignees": assignment.assignees,
                    "parent_id": parent_id,
                })

        return tasks_info, list_id, parent_id

    async def _generate_creative_direction(self, analysis):
        """Collect data and generate creative direction for the client."""
        client_name = analysis.client_name.lower()
        brand_guidelines = _load_brand_guidelines(client_name)

        # Fetch task history (last 3 months)
        import time as time_mod

        now_ms = int(time_mod.time() * 1000)
        three_months_ms = 90 * 24 * 60 * 60 * 1000
        try:
            all_tasks = await self._clickup.get_filtered_team_tasks(
                team_id=self._rules._data.get("team_id", ""),
                date_done_gt=now_ms - three_months_ms,
                date_done_lt=now_ms,
            )
            client_config = self._rules.get_client_config(client_name)
            client_list_id = client_config.get("list_id", "")
            client_tasks = [
                t for t in all_tasks
                if t.get("list", {}).get("id") == client_list_id
            ]
        except Exception:
            logger.warning("Could not fetch task history for %s", client_name)
            client_tasks = []

        task_history = format_task_history(client_tasks)

        month_map = {
            "janeiro": "01", "fevereiro": "02", "marco": "03", "abril": "04",
            "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
            "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12",
        }
        month_num = month_map.get(analysis.month.lower(), analysis.month.zfill(2))
        seasonal_data = load_seasonal_data(month_num)

        return await generate_creative_direction(
            agent=self._creative_director,
            client_name=analysis.client_name,
            social_network=analysis.social_network,
            month=analysis.month,
            year=analysis.year,
            brand_guidelines=brand_guidelines,
            task_history=task_history,
            seasonal_data=seasonal_data,
        )

    async def handle_creative_callback(
        self, update, context,
    ) -> None:
        """Handle inline keyboard callbacks for creative direction flow."""
        query = update.callback_query
        await query.answer()

        action = query.data

        if action == "creative_skip":
            if self._schedule_agent:
                await self._generate_and_show_schedule(query, context)
            else:
                await query.edit_message_text("Ok, sugestoes puladas.")
            return

        if action == "creative_use":
            creative_direction = context.user_data.get("creative_direction")
            if creative_direction and self._schedule_agent:
                briefing_text = context.user_data.get("briefing_text", "")
                enriched = (
                    f"{briefing_text}\n\n"
                    f"DIRECAO CRIATIVA APROVADA:\n"
                    f"{creative_direction.resumo_estrategico}\n"
                    f"Temas: {', '.join(t.name for t in creative_direction.themes)}\n"
                )
                if creative_direction.seasonal_opportunities:
                    enriched += (
                        "Oportunidades sazonais: "
                        f"{', '.join(o.event for o in creative_direction.seasonal_opportunities)}\n"
                    )
                enriched += f"Mix: {creative_direction.format_mix}\n"
                context.user_data["briefing_text"] = enriched
                await self._generate_and_show_schedule(query, context)
            else:
                await query.edit_message_text("Ok, sugestoes incorporadas.")
            return
