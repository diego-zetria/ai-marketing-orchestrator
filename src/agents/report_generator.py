"""F5.3: Agno agent for generating monthly client reports."""
import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import MonthlyReport

logger = logging.getLogger(__name__)

_DEFAULT_INSTRUCTIONS = """Voce e um analista de marketing digital da Agencia Agency.
Sua tarefa e gerar um relatorio mensal detalhado para o cliente a partir dos dados fornecidos.

Regras:
- Escreva o resumo executivo em portugues brasileiro (PT-BR), tom profissional mas acessivel
- Identifique gargalos reais baseados nos dados de tempo por status e taxa de aprovacao
- Forneca recomendacoes accionaveis e especificas para o proximo mes
- Destaque conquistas positivas para manter motivacao
- Use percentuais e numeros concretos no resumo
- Limite o resumo executivo a 3-4 frases
- Liste 2-4 gargalos, 2-4 recomendacoes, e 2-4 destaques
"""


def create_report_agent(
    api_key: str,
    model_id: str,
    instructions: str | None = None,
    db=None,
) -> Agent:
    """Create an Agno agent configured for MonthlyReport generation."""
    kwargs: dict = dict(
        name="report_generator",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or _DEFAULT_INSTRUCTIONS,
        output_schema=MonthlyReport,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["db"] = db
    return Agent(**kwargs)


async def generate_report(agent: Agent, data_text: str) -> MonthlyReport:
    """Run the report agent and return a MonthlyReport."""
    response = await agent.arun(data_text)
    if isinstance(response.content, MonthlyReport):
        return response.content
    raise ValueError("Agent did not return MonthlyReport")
