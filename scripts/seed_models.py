"""Seed the homologated AI models catalog with 17 curated models.

Authenticates with the admin endpoint, then POSTs each model definition.
Existing models (HTTP 409) are skipped gracefully.
After seeding, triggers a price sync from OpenRouter.

Usage:
    python scripts/seed_models.py

Environment:
    API_URL        - Base URL of the backoffice API (default: http://localhost:8000)
    ADMIN_PASSWORD - Admin login password (default: changeme)
"""

from __future__ import annotations

import os
import sys

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

MODELS: list[dict] = [
    # ── Tier Premium ──────────────────────────────────────────────
    {
        "model_id": "anthropic/claude-opus-4.6",
        "provider": "Anthropic",
        "display_name": "Claude Opus 4.6",
        "description_pt": (
            "O modelo mais poderoso da Anthropic. Qualidade maxima em analises "
            "complexas, revisoes detalhadas e tarefas que exigem raciocinio "
            "profundo. Ideal quando a precisao e mais importante que a velocidade."
        ),
        "tier": "premium",
        "quality_stars": 5,
        "speed_rating": "moderate",
        "cost_rating": "premium",
        "best_for": ["Revisao de Conteudo", "Analise Profunda"],
        "recommended_agents": ["content_reviewer"],
        "is_recommended": False,
        "display_order": 1,
    },
    {
        "model_id": "google/gemini-3.1-pro-preview",
        "provider": "Google",
        "display_name": "Gemini 3.1 Pro",
        "description_pt": (
            "Modelo frontier da Google com enorme capacidade de memoria (1M "
            "tokens). Aceita texto, imagens, audio e video. Excelente para "
            "analisar documentos longos e conteudo multimidia."
        ),
        "tier": "premium",
        "quality_stars": 5,
        "speed_rating": "moderate",
        "cost_rating": "moderate",
        "best_for": ["Documentos Longos", "Analise de Imagens", "Multimidia"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 2,
    },
    {
        "model_id": "openai/gpt-4.1",
        "provider": "OpenAI",
        "display_name": "GPT-4.1",
        "description_pt": (
            "Modelo flagship da OpenAI. Versatil e confiavel para qualquer tipo "
            "de tarefa. Grande capacidade de memoria (1M tokens) e suporte a "
            "ferramentas."
        ),
        "tier": "premium",
        "quality_stars": 5,
        "speed_rating": "moderate",
        "cost_rating": "moderate",
        "best_for": ["Uso Geral", "Criacao de Briefings"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 3,
    },
    # ── Tier Recommended ──────────────────────────────────────────
    {
        "model_id": "anthropic/claude-sonnet-4.6",
        "provider": "Anthropic",
        "display_name": "Claude Sonnet 4.6",
        "description_pt": (
            "Excelente equilibrio entre qualidade, velocidade e custo. E o "
            "modelo padrao do nosso sistema e funciona muito bem para a grande "
            "maioria das tarefas da agencia, desde revisao de conteudo ate "
            "criacao de briefings e cronogramas."
        ),
        "tier": "recommended",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "moderate",
        "best_for": [
            "Revisao de Conteudo",
            "Criacao de Briefings",
            "Cronogramas",
            "Resumos",
            "Uso Geral",
        ],
        "recommended_agents": [
            "briefing_analyzer",
            "content_reviewer",
            "schedule_generator",
            "summary_generator",
        ],
        "is_recommended": True,
        "display_order": 10,
    },
    {
        "model_id": "google/gemini-2.5-pro",
        "provider": "Google",
        "display_name": "Gemini 2.5 Pro",
        "description_pt": (
            "Modelo forte da Google com excelente capacidade de raciocinio e "
            "analise. Boa opcao para tarefas que precisam de analise detalhada "
            "com custo moderado."
        ),
        "tier": "recommended",
        "quality_stars": 4,
        "speed_rating": "moderate",
        "cost_rating": "moderate",
        "best_for": ["Analise Profunda", "Resumos", "Uso Geral"],
        "recommended_agents": ["content_reviewer", "summary_generator"],
        "is_recommended": False,
        "display_order": 11,
    },
    {
        "model_id": "openai/gpt-4o",
        "provider": "OpenAI",
        "display_name": "GPT-4o",
        "description_pt": (
            "Modelo multimodal da OpenAI que aceita texto e imagens. Otimo para "
            "analisar posts com imagens, revisar criativos e tarefas que "
            "envolvem conteudo visual."
        ),
        "tier": "recommended",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "moderate",
        "best_for": ["Analise de Imagens", "Revisao de Conteudo", "Uso Geral"],
        "recommended_agents": ["content_reviewer"],
        "is_recommended": False,
        "display_order": 12,
    },
    {
        "model_id": "deepseek/deepseek-v3.2",
        "provider": "DeepSeek",
        "display_name": "DeepSeek V3.2",
        "description_pt": (
            "Modelo de alta qualidade com custo muito baixo. Boa alternativa "
            "economica para tarefas do dia a dia que nao exigem o maximo de "
            "qualidade."
        ),
        "tier": "recommended",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Uso Geral", "Economia", "Resumos"],
        "recommended_agents": ["summary_generator"],
        "is_recommended": False,
        "display_order": 13,
    },
    {
        "model_id": "moonshotai/kimi-k2.5",
        "provider": "Moonshot AI",
        "display_name": "Kimi K2.5",
        "description_pt": (
            "Modelo multimodal da Moonshot AI com excelente capacidade de "
            "analise visual e uso de ferramentas. Entende imagens e texto "
            "com alta qualidade, ideal para revisar criativos e posts com "
            "imagens. Boa relacao custo-beneficio."
        ),
        "tier": "recommended",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Analise de Imagens", "Uso Geral", "Revisao de Conteudo"],
        "recommended_agents": ["content_reviewer"],
        "is_recommended": False,
        "display_order": 14,
    },
    # ── Tier Fast ─────────────────────────────────────────────────
    {
        "model_id": "anthropic/claude-haiku-4.5",
        "provider": "Anthropic",
        "display_name": "Claude Haiku 4.5",
        "description_pt": (
            "Modelo rapido e economico da Anthropic. Ideal para tarefas simples "
            "que precisam de resposta imediata, como triagem de briefings e "
            "respostas rapidas."
        ),
        "tier": "fast",
        "quality_stars": 3,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Resumos", "Uso Geral", "Economia"],
        "recommended_agents": ["summary_generator"],
        "is_recommended": False,
        "display_order": 20,
    },
    {
        "model_id": "google/gemini-2.5-flash",
        "provider": "Google",
        "display_name": "Gemini 2.5 Flash",
        "description_pt": (
            "Modelo ultra-rapido da Google com grande memoria (1M tokens). "
            "Muito barato e eficiente para tarefas que precisam processar muito "
            "texto rapidamente."
        ),
        "tier": "fast",
        "quality_stars": 3,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Documentos Longos", "Resumos", "Economia"],
        "recommended_agents": ["summary_generator"],
        "is_recommended": False,
        "display_order": 21,
    },
    {
        "model_id": "openai/gpt-4.1-mini",
        "provider": "OpenAI",
        "display_name": "GPT-4.1 Mini",
        "description_pt": (
            "Versao compacta e rapida do GPT-4.1. Boa qualidade com custo "
            "reduzido, ideal para tarefas rotineiras e resumos diarios."
        ),
        "tier": "fast",
        "quality_stars": 3,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Resumos", "Uso Geral", "Economia"],
        "recommended_agents": ["summary_generator"],
        "is_recommended": False,
        "display_order": 22,
    },
    {
        "model_id": "openai/gpt-4.1-nano",
        "provider": "OpenAI",
        "display_name": "GPT-4.1 Nano",
        "description_pt": (
            "O modelo mais rapido e barato da OpenAI. Para tarefas muito "
            "simples onde velocidade e custo sao prioridade absoluta."
        ),
        "tier": "fast",
        "quality_stars": 2,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Economia", "Uso Geral"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 23,
    },
    {
        "model_id": "x-ai/grok-4.1-fast",
        "provider": "xAI",
        "display_name": "Grok 4.1 Fast",
        "description_pt": (
            "Modelo rapido da xAI com enorme capacidade de memoria (2M "
            "tokens) e excelente uso de ferramentas. Muito barato e "
            "eficiente para tarefas agenticas como pesquisa e atendimento. "
            "Suporta raciocinio que pode ser ativado/desativado."
        ),
        "tier": "fast",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Uso Geral", "Economia", "Documentos Longos"],
        "recommended_agents": ["summary_generator", "briefing_analyzer"],
        "is_recommended": False,
        "display_order": 24,
    },
    {
        "model_id": "google/gemini-3-flash-preview",
        "provider": "Google",
        "display_name": "Gemini 3 Flash Preview",
        "description_pt": (
            "Modelo rapido da Google com raciocinio proximo ao Pro mas com "
            "muito menos latencia. Suporta texto, imagens, audio, video e "
            "PDFs com janela de 1M tokens. Ideal para tarefas agenticas e "
            "assistencia interativa com otimo custo-beneficio."
        ),
        "tier": "fast",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Uso Geral", "Multimidia", "Documentos Longos"],
        "recommended_agents": ["summary_generator", "content_reviewer"],
        "is_recommended": False,
        "display_order": 25,
    },
    # ── Tier Specialist ───────────────────────────────────────────
    {
        "model_id": "qwen/qwen3.5-plus-02-15",
        "provider": "Alibaba",
        "display_name": "Qwen 3.5 Plus",
        "description_pt": (
            "Modelo multilingual forte da Alibaba. Excelente para traducoes e "
            "conteudo em multiplos idiomas. Grande capacidade de memoria."
        ),
        "tier": "specialist",
        "quality_stars": 4,
        "speed_rating": "moderate",
        "cost_rating": "budget",
        "best_for": ["Uso Geral", "Economia"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 30,
    },
    {
        "model_id": "meta-llama/llama-4-maverick",
        "provider": "Meta",
        "display_name": "Llama 4 Maverick",
        "description_pt": (
            "Modelo open source da Meta com excelente qualidade. Boa opcao para "
            "quem valoriza transparencia e privacidade dos dados."
        ),
        "tier": "specialist",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Uso Geral", "Economia"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 31,
    },
    {
        "model_id": "minimax/minimax-m2.5",
        "provider": "MiniMax",
        "display_name": "MiniMax M2.5",
        "description_pt": (
            "Modelo ultra-economico com boa qualidade para o preco. Ideal para "
            "alto volume de tarefas simples onde o custo e critico."
        ),
        "tier": "specialist",
        "quality_stars": 3,
        "speed_rating": "fast",
        "cost_rating": "budget",
        "best_for": ["Economia", "Uso Geral"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 32,
    },
    {
        "model_id": "z-ai/glm-5",
        "provider": "Z.ai",
        "display_name": "GLM 5",
        "description_pt": (
            "Modelo open-source da Z.ai com foco em planejamento e "
            "execucao autonoma de tarefas complexas. Forte em raciocinio "
            "profundo e autocorrecao. Boa opcao para tarefas que exigem "
            "analise detalhada e planejamento."
        ),
        "tier": "specialist",
        "quality_stars": 4,
        "speed_rating": "moderate",
        "cost_rating": "moderate",
        "best_for": ["Analise Profunda", "Uso Geral"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 33,
    },
    # ── Tier Router ───────────────────────────────────────────────
    {
        "model_id": "openrouter/auto",
        "provider": "OpenRouter",
        "display_name": "Auto Router",
        "description_pt": (
            "Roteamento automatico do OpenRouter. Escolhe automaticamente o "
            "melhor modelo disponivel para cada tarefa, otimizando custo e "
            "qualidade."
        ),
        "tier": "router",
        "quality_stars": 4,
        "speed_rating": "fast",
        "cost_rating": "moderate",
        "best_for": ["Uso Geral"],
        "recommended_agents": [],
        "is_recommended": False,
        "display_order": 40,
    },
]


def login(client: httpx.Client) -> str:
    """Authenticate and return the JWT token."""
    response = client.post(
        f"{API_URL}/api/admin/auth/login",
        json={"password": ADMIN_PASSWORD},
    )
    if response.status_code != 200:
        print(f"[FAIL] Login failed: {response.status_code} - {response.text}")
        sys.exit(1)

    token = response.json()["token"]
    print(f"[OK]   Authenticated with {API_URL}")
    return token


def seed_model(client: httpx.Client, headers: dict, model: dict) -> str:
    """POST a single model to the catalog.

    Returns: "added", "skipped", or "failed".
    """
    response = client.post(
        f"{API_URL}/api/admin/models",
        json=model,
        headers=headers,
    )

    name = model["display_name"]

    if response.status_code == 201:
        print(f"  [ADD]  {name}")
        return "added"

    if response.status_code == 409:
        print(f"  [SKIP] {name} - already exists")
        return "skipped"

    print(f"  [FAIL] {name} - {response.status_code}: {response.text}")
    return "failed"


def sync_prices(client: httpx.Client, headers: dict) -> None:
    """Trigger a price sync from OpenRouter after seeding new models."""
    print("\nSyncing prices from OpenRouter...")
    response = client.post(
        f"{API_URL}/api/admin/models/sync",
        headers=headers,
    )
    if response.is_success:
        data = response.json()
        print(
            f"[OK]   Sync complete: {data['synced']} updated, "
            f"{len(data['not_found'])} not found"
        )
    else:
        print(f"[FAIL] Sync failed: {response.status_code} - {response.text}")


def main() -> None:
    print(f"Seeding {len(MODELS)} models into {API_URL}\n")

    with httpx.Client(timeout=30.0) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}

        print()
        counts = {"added": 0, "skipped": 0, "failed": 0}

        for model in MODELS:
            result = seed_model(client, headers, model)
            counts[result] += 1

        print(
            f"\nDone! {counts['added']} added, "
            f"{counts['skipped']} skipped, "
            f"{counts['failed']} failed."
        )

        if counts["added"] > 0:
            sync_prices(client, headers)

    if counts["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
