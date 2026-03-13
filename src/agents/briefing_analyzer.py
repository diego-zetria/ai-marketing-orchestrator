import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import BriefingAnalysis

logger = logging.getLogger(__name__)


def create_briefing_agent(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    default_instructions = [
        "Voce e um gerente de projetos da agencia de marketing Agency.",
        "",
        "PRIMEIRO: Avalie se a mensagem e um briefing de marketing valido.",
        "Um briefing valido deve conter pelo menos: nome do cliente OU rede social "
        "OU descricao de conteudo a ser criado.",
        "",
        "Se a mensagem NAO for um briefing valido (saudacoes, perguntas, "
        "mensagens curtas, conteudo irrelevante):",
        "- Defina is_valid_briefing=false",
        "- Escreva uma rejection_message amigavel em portugues explicando que "
        "este bot processa briefings de marketing e orientando o que incluir. "
        "Exemplo: nome do cliente, rede social, tipo de post, mes/ano.",
        "- Deixe os demais campos com valores default.",
        "",
        "Se a mensagem FOR um briefing valido:",
        "- Defina is_valid_briefing=true",
        "- Analise o briefing e extraia as informacoes para criar tasks.",
        "- Identifique: nome do cliente, rede social, posts necessarios, urgencia.",
        "- O titulo de cada post deve ser descritivo e conciso.",
        "- Classifique service_type como: 'design' | 'copy' | 'design+copy'.",
        "- Se mencionar urgencia ou prazo curto, marque urgency como 'urgent'.",
        "- Se faltar informacoes, liste duvidas em observations.",
        "- Nao invente informacoes que nao estao no briefing.",
        "",
        "Responda sempre em portugues brasileiro.",
    ]
    kwargs = dict(
        name="briefing_analyzer",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or default_instructions,
        output_schema=BriefingAnalysis,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


async def analyze_briefing(
    agent: Agent, briefing_text: str, max_retries: int = 2,
) -> BriefingAnalysis:
    last_error = None
    for attempt in range(max_retries + 1):
        response = await agent.arun(briefing_text)
        content = response.content

        if isinstance(content, BriefingAnalysis):
            return content

        # If the model returned a string, try to parse it as JSON
        if isinstance(content, str):
            try:
                import json
                data = json.loads(content)
                return BriefingAnalysis(**data)
            except (json.JSONDecodeError, Exception):
                pass

        logger.warning(
            "Briefing analysis attempt %d/%d returned %s instead of BriefingAnalysis",
            attempt + 1, max_retries + 1, type(content).__name__,
        )
        last_error = (
            f"AI retornou resposta invalida (tentativa {attempt + 1}/{max_retries + 1}): "
            f"esperado BriefingAnalysis, recebido {type(content).__name__}"
        )

    raise ValueError(last_error)
