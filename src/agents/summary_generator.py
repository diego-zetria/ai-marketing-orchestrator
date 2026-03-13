import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import DailySummary

logger = logging.getLogger(__name__)


def create_summary_agent(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    default_instructions = [
        "Voce e o gerente de projetos da agencia Agency.",
        "Gere um resumo executivo claro e conciso das tasks.",
        "Inclua: ativas, concluidas, atrasadas, gargalos, deadlines proximos.",
        "Use emojis para status. Mencione responsaveis quando relevante.",
        "Responda em portugues brasileiro.",
    ]
    kwargs = dict(
        name="summary_generator",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or default_instructions,
        output_schema=DailySummary,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


async def generate_summary(agent: Agent, tasks_data: str) -> DailySummary:
    response = await agent.arun(tasks_data)
    if isinstance(response.content, DailySummary):
        return response.content
    raise ValueError("Agent did not return DailySummary")
