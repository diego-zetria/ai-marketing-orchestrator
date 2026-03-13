import logging
from pathlib import Path

import yaml
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import ContentReview

logger = logging.getLogger(__name__)

DEFAULT_BRANDS_DIR = Path("config/brands")


def create_review_agent(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    default_instructions = [
        "Voce e um revisor de conteudo da agencia de marketing Agency.",
        "Analise o conteudo da task conforme as guidelines da marca.",
        "Verifique: tom de voz, ortografia, gramatica, CTAs, hashtags, emojis.",
        "Liste itens verificados em checklist.",
        "Liste problemas encontrados em issues.",
        "Sugira melhorias em suggestions.",
        "De uma nota de 1 a 10 em overall_score.",
        "Escreva um resumo de 2-3 frases em summary.",
        "Se o conteudo atender as guidelines, marque approved=True.",
        "Responda sempre em portugues brasileiro.",
    ]
    kwargs = dict(
        name="content_reviewer",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or default_instructions,
        output_schema=ContentReview,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


def _load_brand_guidelines(
    client_name: str,
    brands_dir: Path | None = None,
    db_content: str | None = None,
) -> str:
    """Load brand guidelines. Priority: db_content > YAML > .md > default."""
    if db_content:
        return db_content
    base = brands_dir or DEFAULT_BRANDS_DIR

    # Try YAML first (structured), fallback to .md (legacy)
    yaml_path = base / f"{client_name}.yaml"
    if yaml_path.exists():
        return _format_yaml_guidelines(yaml_path)

    md_path = base / f"{client_name}.md"
    if md_path.exists():
        return md_path.read_text()

    # Default fallbacks
    default_yaml = base / "default.yaml"
    if default_yaml.exists():
        return _format_yaml_guidelines(default_yaml)

    default_md = base / "default.md"
    return default_md.read_text()


def load_brand_config(
    client_name: str,
    brands_dir: Path | None = None,
) -> dict:
    """Load structured brand config as a dict (for Brand Compliance agent).

    Returns the parsed YAML dict, or an empty dict if no YAML exists.
    """
    base = brands_dir or DEFAULT_BRANDS_DIR
    yaml_path = base / f"{client_name}.yaml"
    if not yaml_path.exists():
        yaml_path = base / "default.yaml"
    if not yaml_path.exists():
        return {}
    return yaml.safe_load(yaml_path.read_text()) or {}


def _format_yaml_guidelines(yaml_path: Path) -> str:
    """Convert structured YAML brand config into a readable text prompt."""
    data = yaml.safe_load(yaml_path.read_text()) or {}
    lines = [f"# Guidelines {data.get('brand', 'default').upper()}"]

    if tone := data.get("tone"):
        lines.append(f"\nTom: {tone}")

    if forbidden := data.get("forbidden_words"):
        lines.append(f"\nPalavras proibidas: {', '.join(forbidden)}")

    if hashtags := data.get("hashtags"):
        if req := hashtags.get("required"):
            lines.append(f"Hashtags obrigatorias: {', '.join(req)}")
        if sug := hashtags.get("suggested"):
            lines.append(f"Hashtags sugeridas: {', '.join(sug)}")

    if colors := data.get("color_palette"):
        lines.append(f"Paleta de cores: {', '.join(colors)}")

    if elements := data.get("required_elements"):
        for platform, rules in elements.items():
            lines.append(f"\n## {platform.capitalize()}")
            for key, val in rules.items():
                lines.append(f"- {key}: {val}")

    if guidelines := data.get("guidelines"):
        lines.append("\n## Diretrizes")
        for g in guidelines:
            lines.append(f"- {g}")

    return "\n".join(lines)


async def review_content(
    agent: Agent,
    task_name: str,
    task_description: str,
    comments_text: str,
    client_name: str,
    brands_dir: Path | None = None,
    brand_guidelines_content: str | None = None,
) -> ContentReview:
    """Run the AI review agent on task content."""
    guidelines = _load_brand_guidelines(
        client_name, brands_dir=brands_dir, db_content=brand_guidelines_content
    )
    prompt = (
        f"Revise o conteudo abaixo conforme as guidelines da marca.\n\n"
        f"## Guidelines\n{guidelines}\n\n"
        f"## Task: {task_name}\n{task_description}\n\n"
        f"## Comentarios/Conteudo:\n{comments_text}"
    )
    response = await agent.arun(prompt)
    return response.content
