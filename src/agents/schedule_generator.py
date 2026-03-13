import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import PostSchedule

logger = logging.getLogger(__name__)


def create_schedule_agent(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    default_instructions = [
        "Voce e um planejador de conteudo da agencia de marketing Agency.",
        "Sua tarefa e gerar um cronograma mensal de posts para redes sociais.",
        "Baseie-se no briefing do cliente para criar titulos relevantes.",
        "Distribua os posts ao longo do mes de forma equilibrada.",
        "Varie os tipos de post: POST, CARROSSEL, REELS, STORY.",
        "Use o formato DD/MM para as datas (ex: 03/03, 15/03).",
        "Respeite a quantidade de posts solicitada no briefing.",
        "Se o briefing nao especificar quantidade, sugira entre 8 e 12 posts.",
        "Crie titulos descritivos e criativos baseados no conteudo do briefing.",
        "Nao invente informacoes que nao estao no briefing.",
        "Responda sempre em portugues brasileiro.",
    ]
    kwargs = dict(
        name="schedule_generator",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or default_instructions,
        output_schema=PostSchedule,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


async def generate_schedule(
    agent: Agent,
    briefing_text: str,
    client_name: str,
    social_network: str,
    month: str,
    year: str,
    max_retries: int = 2,
) -> PostSchedule:
    prompt = (
        f"Gere um cronograma de posts para o cliente '{client_name}' "
        f"na plataforma '{social_network}' para o mes de {month}/{year}.\n\n"
        f"Briefing do cliente:\n{briefing_text}"
    )
    last_error = None
    for attempt in range(max_retries + 1):
        response = await agent.arun(prompt)
        content = response.content

        if isinstance(content, PostSchedule):
            return content

        logger.warning(
            "Schedule generation attempt %d/%d returned %s instead of PostSchedule",
            attempt + 1, max_retries + 1, type(content).__name__,
        )
        last_error = (
            f"AI retornou resposta invalida (tentativa {attempt + 1}/{max_retries + 1}): "
            f"esperado PostSchedule, recebido {type(content).__name__}"
        )

    raise ValueError(last_error)
