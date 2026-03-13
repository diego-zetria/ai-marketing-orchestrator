"""F5.1: Agno agent for AI Creative Director — strategic content suggestions."""
import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import CreativeDirection

logger = logging.getLogger(__name__)

_DEFAULT_INSTRUCTIONS = [
    "Voce e o Diretor Criativo da agencia de marketing Agency.",
    "Sua tarefa e gerar uma direcao criativa estrategica para o conteudo "
    "do cliente no proximo mes.",
    "",
    "Voce recebera:",
    "- Guidelines da marca (tom, palavras proibidas, formatos obrigatorios)",
    "- Historico de conteudo dos ultimos meses (tipos, temas, frequencia)",
    "- Calendario sazonal com datas comerciais e culturais relevantes",
    "",
    "Gere de 3 a 5 temas estrategicos (themes) que sejam:",
    "- Alinhados com as guidelines e o tom da marca",
    "- Variados entre os pilares: educativo, promocional, inspiracional, entretenimento",
    "- Com subtopicos especificos e acionaveis (3-5 por tema)",
    "- Com formatos recomendados baseados no que funciona para o cliente",
    "",
    "Para cada tema, forneca uma justificativa (rationale) baseada em:",
    "- Padroes do historico de conteudo do cliente",
    "- Tendencias sazonais e datas comemorativas",
    "- Boas praticas de marketing digital para o segmento",
    "",
    "Inclua oportunidades sazonais relevantes do calendario fornecido.",
    "Sugira um mix de formatos (format_mix) equilibrado para o mes.",
    "Indique o que evitar (avoid) com base nas guidelines e no historico.",
    "",
    "Responda sempre em portugues brasileiro.",
    "Seja criativo mas realista — as sugestoes devem ser executaveis pela equipe.",
]


def create_creative_director(
    api_key: str,
    model_id: str,
    instructions: list[str] | None = None,
    db=None,
) -> Agent:
    """Create an Agno agent configured for CreativeDirection generation."""
    kwargs: dict = dict(
        name="creative_director",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or _DEFAULT_INSTRUCTIONS,
        output_schema=CreativeDirection,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["storage"] = db
    return Agent(**kwargs)


def format_task_history(tasks: list[dict]) -> str:
    """Format ClickUp task history into a text summary for the agent prompt."""
    if not tasks:
        return "Nenhum historico de conteudo disponivel para este cliente."

    type_counts: dict[str, int] = {}
    themes: list[str] = []
    statuses: dict[str, int] = {}

    for task in tasks:
        name = task.get("name", "")
        status = task.get("status", {})
        status_name = (
            status.get("status", "desconhecido")
            if isinstance(status, dict)
            else str(status)
        )

        statuses[status_name] = statuses.get(status_name, 0) + 1

        parts = name.split(" - ", 1)
        if len(parts) == 2:
            type_and_title = parts[1].strip()
            for content_type in ("POST", "CARROSSEL", "REELS", "STORY"):
                if type_and_title.upper().startswith(content_type):
                    type_counts[content_type] = type_counts.get(content_type, 0) + 1
                    title = type_and_title[len(content_type):].strip()
                    if title:
                        themes.append(title)
                    break

        desc = task.get("description", "")
        if desc and len(desc) > 10:
            themes.append(desc[:100])

    lines = [f"Total: {len(tasks)} tasks nos ultimos 3 meses.", ""]

    if type_counts:
        lines.append("Tipos de conteudo:")
        for ctype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {ctype}: {count}")

    if statuses:
        lines.append("")
        lines.append("Status:")
        for st, count in sorted(statuses.items(), key=lambda x: -x[1]):
            lines.append(f"  - {st}: {count}")

    if themes:
        lines.append("")
        lines.append("Temas/titulos recentes:")
        for theme in themes[:10]:
            lines.append(f"  - {theme}")

    return "\n".join(lines)


async def generate_creative_direction(
    agent: Agent,
    client_name: str,
    social_network: str,
    month: str,
    year: str,
    brand_guidelines: str,
    task_history: str,
    seasonal_data: str,
    max_retries: int = 2,
) -> CreativeDirection:
    """Run the Creative Director agent and return a CreativeDirection."""
    prompt = (
        f"Gere uma direcao criativa para o cliente '{client_name}' "
        f"na plataforma '{social_network}' para o mes de {month}/{year}.\n\n"
        f"GUIDELINES DA MARCA:\n{brand_guidelines}\n\n"
        f"HISTORICO DE CONTEUDO (ultimos 3 meses):\n{task_history}\n\n"
        f"CALENDARIO SAZONAL:\n{seasonal_data}"
    )

    last_error = None
    for attempt in range(max_retries + 1):
        response = await agent.arun(prompt)
        content = response.content

        if isinstance(content, CreativeDirection):
            return content

        logger.warning(
            "Creative direction attempt %d/%d returned %s instead of CreativeDirection",
            attempt + 1, max_retries + 1, type(content).__name__,
        )
        last_error = (
            f"AI retornou resposta invalida (tentativa {attempt + 1}/{max_retries + 1}): "
            f"esperado CreativeDirection, recebido {type(content).__name__}"
        )

    raise ValueError(last_error)
