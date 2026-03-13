"""F5.2: Agno agent for generating Instagram performance insights."""

import logging

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.agents.schemas import PerformanceInsight

logger = logging.getLogger(__name__)

_DEFAULT_INSTRUCTIONS = """Voce e o analista de performance digital da agencia Agency.
Sua tarefa e analisar metricas de posts do Instagram e gerar insights acionaveis.

Regras:
- Escreva tudo em portugues brasileiro (PT-BR), tom profissional mas acessivel
- Identifique os 3 melhores e 3 piores posts por taxa de engajamento
  (total_interactions / reach * 100)
- Compare formatos (IMAGE, VIDEO, CAROUSEL_ALBUM) e identifique qual performa melhor
- Identifique tendencias: qual tipo de conteudo gera mais saves? Mais shares?
- Forneca recomendacoes especificas e acionaveis baseadas nos dados
- Use numeros concretos e percentuais nas analises
- O resumo deve ter 2-3 frases com os insights mais relevantes
- Liste 2-4 tendencias e 2-4 recomendacoes
- Se nao houver dados suficientes, diga isso claramente
"""


def create_performance_analyzer(
    api_key: str,
    model_id: str,
    instructions: str | None = None,
    db=None,
) -> Agent:
    """Create an Agno agent configured for PerformanceInsight generation."""
    kwargs: dict = dict(
        name="performance_analyzer",
        model=OpenRouter(
            id=model_id,
            api_key=api_key,
            max_tokens=4096,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        ),
        instructions=instructions or _DEFAULT_INSTRUCTIONS,
        output_schema=PerformanceInsight,
        use_json_mode=True,
        markdown=False,
    )
    if db is not None:
        kwargs["db"] = db
    return Agent(**kwargs)


def format_media_data(posts: list[dict]) -> str:
    """Format media_insights rows as text for the AI agent prompt."""
    if not posts:
        return "Nenhum dado de posts disponivel."

    lines = [f"Total: {len(posts)} posts\n"]
    for i, p in enumerate(posts, 1):
        caption = (p.get("caption") or "")[:80]
        eng_rate = 0.0
        reach = p.get("reach", 0)
        interactions = p.get("total_interactions", 0)
        if reach > 0:
            eng_rate = (interactions / reach) * 100

        lines.append(
            f"{i}. [{p.get('media_type', '?')}] {p.get('published_at', '?')}"
            f" | Alcance: {reach} | Views: {p.get('views', 0)}"
            f" | Likes: {p.get('likes', 0)} | Comments: {p.get('comments', 0)}"
            f" | Saves: {p.get('saves', 0)} | Shares: {p.get('shares', 0)}"
            f" | Interacoes: {interactions} | Eng: {eng_rate:.1f}%"
            f"\n   Legenda: {caption}"
        )

    # Aggregate by format
    format_counts: dict[str, list[dict]] = {}
    for p in posts:
        fmt = p.get("media_type", "UNKNOWN")
        format_counts.setdefault(fmt, []).append(p)

    lines.append("\n=== RESUMO POR FORMATO ===")
    for fmt, fmt_posts in format_counts.items():
        avg_reach = sum(p.get("reach", 0) for p in fmt_posts) / len(fmt_posts)
        avg_eng = 0.0
        for p in fmt_posts:
            r = p.get("reach", 0)
            if r > 0:
                avg_eng += (p.get("total_interactions", 0) / r) * 100
        avg_eng /= len(fmt_posts)
        lines.append(
            f"  {fmt}: {len(fmt_posts)} posts"
            f" | Media alcance: {avg_reach:.0f}"
            f" | Media eng: {avg_eng:.1f}%"
        )

    return "\n".join(lines)


def format_account_data(entries: list[dict]) -> str:
    """Format account_insights rows as text for the AI agent prompt."""
    if not entries:
        return "Nenhum dado de conta disponivel."

    lines = ["=== METRICAS DA CONTA ==="]
    for e in entries:
        lines.append(
            f"  {e.get('date', '?')}"
            f" | Alcance: {e.get('reach', 0)}"
            f" | Views: {e.get('views', 0)}"
            f" | Seguidores: {e.get('follower_count', 0)}"
        )

    if len(entries) >= 2:
        first = entries[0].get("follower_count", 0)
        last = entries[-1].get("follower_count", 0)
        change = last - first
        avg_reach = sum(e.get("reach", 0) for e in entries) / len(entries)
        lines.append(
            f"\nSeguidores: {first} -> {last} ({'+' if change >= 0 else ''}{change})"
        )
        lines.append(f"Alcance diario medio: {avg_reach:.0f}")

    return "\n".join(lines)


async def generate_performance_insight(
    agent: Agent,
    client_name: str,
    period: str,
    posts_data: str,
    account_data: str,
    max_retries: int = 2,
) -> PerformanceInsight:
    """Run the performance analyzer agent and return a PerformanceInsight.

    Retries up to max_retries times if the response is not a valid schema.
    """
    prompt = f"""Cliente: {client_name}
Periodo: {period}

DADOS DOS POSTS DO INSTAGRAM:
{posts_data}

DADOS DA CONTA:
{account_data}

Analise os dados acima e gere o insight de performance.
Identifique os melhores e piores posts, compare formatos, e forneca recomendacoes."""

    for attempt in range(max_retries + 1):
        response = await agent.arun(prompt)
        if isinstance(response.content, PerformanceInsight):
            return response.content
        logger.warning(
            "Performance analyzer returned %s instead of PerformanceInsight (attempt %d/%d)",
            type(response.content).__name__,
            attempt + 1,
            max_retries + 1,
        )

    raise ValueError(
        f"Performance analyzer resposta invalida apos {max_retries + 1} tentativas"
    )
