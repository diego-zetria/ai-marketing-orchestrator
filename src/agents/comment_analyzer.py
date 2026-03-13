"""CommentAnalyzerAgent: LLM fallback for ambiguous comment intent detection.

Part of the model cascade:
  1. Regex patterns (free, instant) — comment_patterns.detect_intent()
  2. LLM analysis (paid, slower) — this agent, only when regex returns None

The agent uses the move_task_status tool with requires_confirmation=True,
so any proposed status change must be approved by a human before executing.
"""
import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.tools.clickup_tools import ClickUpToolkit

logger = logging.getLogger(__name__)

_DEFAULT_INSTRUCTIONS = [
    "Voce e um assistente da agencia de marketing Agency.",
    "Voce analisa comentarios de tarefas no ClickUp para detectar intencoes.",
    "",
    "Tipos de intencao que voce pode detectar:",
    "1. APROVACAO: o revisor esta aprovando o conteudo",
    "   - Palavras-chave: aprovado, ok, pode publicar, excelente, perfeito",
    "   - So valido se o usuario tem role de revisor",
    "2. ENTREGA: o designer esta entregando o conteudo para revisao",
    "   - Palavras-chave: finalizado, pronto, segue para aprovacao, entrega",
    "   - So valido se o usuario tem role de designer",
    "3. ALTERACAO FEITA: o designer terminou os ajustes solicitados",
    "   - Palavras-chave: alterado, ajustado, corrigido, atualizado",
    "   - So valido se o usuario tem role de designer",
    "",
    "REGRAS IMPORTANTES:",
    "- Se o comentario nao tiver intencao clara de mudanca de status, "
    "NAO proponha nenhuma acao. Responda apenas 'SEM_INTENCAO'.",
    "- Se detectar intencao mas o role ou status nao for valido, "
    "responda 'SEM_INTENCAO'.",
    "- Cuidado com falsos positivos: 'aprovado' dentro de uma pergunta "
    "('ja foi aprovado?') NAO e uma aprovacao.",
    "- Comentarios que sao perguntas, duvidas, ou discussoes NAO sao intencoes.",
    "- So use a ferramenta move_task_status se tiver CERTEZA da intencao.",
    "",
    "Responda em portugues brasileiro.",
]


def create_comment_analyzer_agent(
    api_key: str,
    model_id: str,
    clickup_client=None,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    """Create the CommentAnalyzerAgent for LLM-based intent detection.

    Args:
        api_key: OpenRouter API key.
        model_id: Model ID (e.g. "anthropic/claude-haiku-4-5-20251001" for cost).
        clickup_client: ClickUpClient instance (tools need it for execution).
        instructions: Override default instructions.
        db: Optional Agno PostgresDb for session storage.

    Returns:
        Configured Agent with ClickUp tools (requires_confirmation).
    """
    tools = []
    if clickup_client:
        tools.append(ClickUpToolkit(clickup_client=clickup_client))

    kwargs = dict(
        name="comment_analyzer",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=512,
            retries=1,
        ),
        instructions=instructions or _DEFAULT_INSTRUCTIONS,
        tools=tools,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


async def analyze_comment(
    agent: Agent,
    comment_text: str,
    user_role: str,
    current_status: str,
    task_id: str,
    task_name: str = "",
) -> "CommentAnalysis":
    """Run the CommentAnalyzerAgent on an ambiguous comment.

    Args:
        agent: The CommentAnalyzerAgent.
        comment_text: The ClickUp comment text.
        user_role: The commenter's role (e.g. "designer", "strategy_reviewer").
        current_status: The task's current ClickUp status.
        task_id: The ClickUp task ID.
        task_name: The task name (for context).

    Returns:
        CommentAnalysis with the agent's assessment.
    """
    prompt = (
        f"Analise este comentario de uma tarefa do ClickUp:\n\n"
        f"Comentario: \"{comment_text}\"\n"
        f"Role do usuario: {user_role}\n"
        f"Status atual da task: {current_status}\n"
        f"Task ID: {task_id}\n"
        f"Task: {task_name}\n\n"
        f"Se detectar intencao clara de mudanca de status, "
        f"use a ferramenta move_task_status. "
        f"Caso contrario, responda 'SEM_INTENCAO'."
    )

    response = await agent.arun(prompt)

    # Check if the agent proposed a tool call (paused for confirmation)
    if response.is_paused:
        return CommentAnalysis(
            has_intent=True,
            run_output=response,
        )

    # Agent didn't call the tool — no intent detected
    content = str(response.content or "")
    return CommentAnalysis(
        has_intent=False,
        response_text=content,
    )


class CommentAnalysis:
    """Result of LLM comment analysis."""

    __slots__ = ("has_intent", "run_output", "response_text")

    def __init__(
        self,
        has_intent: bool,
        run_output=None,
        response_text: str = "",
    ):
        self.has_intent = has_intent
        self.run_output = run_output  # RunOutput if paused
        self.response_text = response_text
