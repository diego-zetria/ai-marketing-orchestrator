"""Brand Compliance agent — validates content against structured brand rules.

Focused on objective rule validation (forbidden words, required hashtags,
element constraints) rather than subjective quality assessment.
"""
import logging
from pathlib import Path

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.content_reviewer import load_brand_config
from src.agents.schemas import BrandComplianceResult

logger = logging.getLogger(__name__)


def create_brand_compliance_agent(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    default_instructions = [
        "Voce e um auditor de conformidade de marca da agencia Agency.",
        "Sua tarefa e verificar se o conteudo segue as regras da marca.",
        "Foque em validacao OBJETIVA: palavras proibidas, hashtags obrigatorias, "
        "limites de emojis, paleta de cores mencionada, formatos exigidos.",
        "NAO avalie qualidade subjetiva do conteudo — apenas conformidade.",
        "Para cada violacao, indique a regra, severidade (critical/warning/info) "
        "e detalhe.",
        "Se nenhuma violacao for encontrada, retorne violations vazia e passed=True.",
        "compliance_score: 10 se tudo ok, -1 por warning, -2 por critical.",
        "Responda sempre em portugues brasileiro.",
    ]
    kwargs = dict(
        name="brand_compliance",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or default_instructions,
        output_schema=BrandComplianceResult,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


async def check_brand_compliance(
    agent: Agent,
    task_name: str,
    task_description: str,
    comments_text: str,
    client_name: str,
    platform: str = "",
    brands_dir: Path | None = None,
) -> BrandComplianceResult:
    """Run brand compliance check on task content."""
    brand_config = load_brand_config(client_name, brands_dir=brands_dir)
    if not brand_config:
        # No structured config — return auto-pass
        return BrandComplianceResult(
            violations=[],
            compliance_score=10,
            passed=True,
            summary="Sem regras estruturadas de marca para verificar.",
        )

    rules_text = _format_rules_for_prompt(brand_config, platform)
    prompt = (
        f"Verifique a conformidade do conteudo com as regras da marca.\n\n"
        f"## Regras da Marca\n{rules_text}\n\n"
        f"## Task: {task_name}\n{task_description}\n\n"
        f"## Conteudo:\n{comments_text}"
    )
    response = await agent.arun(prompt)
    return response.content


def _format_rules_for_prompt(config: dict, platform: str = "") -> str:
    """Format brand config dict into a readable rules text for the prompt."""
    lines = []

    if tone := config.get("tone"):
        lines.append(f"Tom de voz: {tone}")

    if forbidden := config.get("forbidden_words"):
        lines.append(f"Palavras proibidas: {', '.join(forbidden)}")

    if hashtags := config.get("hashtags"):
        if req := hashtags.get("required"):
            lines.append(f"Hashtags obrigatorias: {', '.join(req)}")

    if elements := config.get("required_elements"):
        target = elements.get(platform, {}) if platform else {}
        if not target and elements:
            # Use first platform as fallback
            target = next(iter(elements.values()), {})
        for key, val in target.items():
            lines.append(f"{key}: {val}")

    if colors := config.get("color_palette"):
        lines.append(f"Paleta de cores: {', '.join(colors)}")

    return "\n".join(lines) if lines else "Sem regras especificas."
