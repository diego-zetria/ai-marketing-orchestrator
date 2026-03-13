"""ReviewTeam: multi-agent review using Agno Teams coordinate mode.

Combines a Brand Compliance agent and a Quality Critic (content_reviewer)
into a coordinated team. Also provides a direct `run_combined_review()` for
non-Team usage (simpler, no coordinator LLM overhead).
"""
import logging
from pathlib import Path

from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.team import Team, TeamMode

from src.agents.brand_compliance import (
    check_brand_compliance,
    create_brand_compliance_agent,
)
from src.agents.content_reviewer import (
    create_review_agent,
    review_content,
)
from src.agents.schemas import CombinedReviewResult

logger = logging.getLogger(__name__)


def create_review_team(
    api_key: str,
    model_id: str,
    coordinator_model_id: str | None = None,
    db=None,
) -> Team:
    """Create an Agno Team in coordinate mode with brand + quality agents.

    The coordinator synthesizes the outputs from both agents.
    For lighter usage without a coordinator LLM call, use
    ``run_combined_review()`` directly instead.
    """
    brand_agent = create_brand_compliance_agent(
        api_key=api_key, model_id=model_id, db=db,
    )
    quality_agent = create_review_agent(
        api_key=api_key, model_id=model_id, db=db,
    )

    coord_model_id = coordinator_model_id or model_id
    return Team(
        name="ReviewTeam",
        mode=TeamMode.coordinate,
        model=OpenRouter(
            id=coord_model_id,
            api_key=api_key,
            max_tokens=4096,
        ),
        members=[brand_agent, quality_agent],
        instructions=[
            "Voce coordena a revisao de conteudo da agencia Agency.",
            "Primeiro, peca ao brand_compliance para verificar conformidade.",
            "Depois, peca ao content_reviewer para avaliar qualidade.",
            "Sintetize ambos os resultados em um parecer final.",
        ],
        share_member_interactions=True,
        max_iterations=5,
    )


async def run_combined_review(
    brand_agent: Agent,
    quality_agent: Agent,
    task_name: str,
    task_description: str,
    comments_text: str,
    client_name: str,
    platform: str = "",
    brands_dir: Path | None = None,
) -> CombinedReviewResult:
    """Run brand compliance + quality review sequentially (no coordinator).

    This is the preferred approach for production: it avoids an extra LLM
    call for coordination and returns a typed CombinedReviewResult directly.
    """
    # 1. Brand compliance check
    compliance = await check_brand_compliance(
        agent=brand_agent,
        task_name=task_name,
        task_description=task_description,
        comments_text=comments_text,
        client_name=client_name,
        platform=platform,
        brands_dir=brands_dir,
    )

    # 2. Quality review
    quality = await review_content(
        agent=quality_agent,
        task_name=task_name,
        task_description=task_description,
        comments_text=comments_text,
        client_name=client_name,
        brands_dir=brands_dir,
    )

    return CombinedReviewResult(
        quality=quality,
        compliance=compliance,
    )
