"""Sync homologated models with OpenRouter API pricing and specs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.admin_models import HomologatedModel

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_HEADERS = {"User-Agent": "Agency-Backoffice/1.0"}


@dataclass
class SyncResult:
    synced: int = 0
    not_found: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def fetch_openrouter_models(
    timeout: float = 30.0, retries: int = 3,
) -> list[dict]:
    """Fetch all models from OpenRouter public API (no auth required)."""
    async with httpx.AsyncClient(timeout=timeout, headers=_HEADERS) as client:
        last_exc: Exception | None = None
        for attempt in range(retries):
            resp = await client.get(OPENROUTER_MODELS_URL)
            if resp.status_code in {408, 429, 503} and attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                continue
            resp.raise_for_status()
            return resp.json()["data"]
        raise last_exc  # type: ignore[misc]


def _update_model_from_openrouter(db_model: HomologatedModel, or_data: dict) -> None:
    """Update a DB model with fresh data from OpenRouter."""
    db_model.context_length = or_data.get("context_length", 0)

    pricing = or_data.get("pricing", {})
    prompt_price = float(pricing.get("prompt", "0"))
    completion_price = float(pricing.get("completion", "0"))
    # OpenRouter uses negative prices for variable/unknown pricing — store as None
    db_model.prompt_price_per_m = (
        round(prompt_price * 1_000_000, 4) if prompt_price >= 0 else None
    )
    db_model.completion_price_per_m = (
        round(completion_price * 1_000_000, 4) if completion_price >= 0 else None
    )

    arch = or_data.get("architecture", {})
    modalities = arch.get("input_modalities", ["text"])
    db_model.input_modalities = modalities
    db_model.supports_images = "image" in modalities
    db_model.supports_audio = "audio" in modalities
    db_model.supports_video = "video" in modalities

    params = or_data.get("supported_parameters", [])
    db_model.supports_tools = "tools" in params

    db_model.openrouter_data = or_data
    db_model.last_synced_at = datetime.now(timezone.utc)


async def sync_models(session: AsyncSession) -> SyncResult:
    """Sync pricing and specs from OpenRouter for all active homologated models."""
    result = SyncResult()

    or_models = await fetch_openrouter_models()
    or_lookup = {m["id"]: m for m in or_models}

    stmt = select(HomologatedModel).where(HomologatedModel.is_active == True)  # noqa: E712
    db_models = (await session.execute(stmt)).scalars().all()

    for db_model in db_models:
        or_data = or_lookup.get(db_model.model_id)
        if not or_data:
            result.not_found.append(db_model.model_id)
            continue
        try:
            _update_model_from_openrouter(db_model, or_data)
            result.synced += 1
        except Exception as e:
            result.errors.append(f"{db_model.model_id}: {str(e)}")

    await session.commit()
    return result
