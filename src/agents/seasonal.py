"""Seasonal calendar loader for the Creative Director agent (F5.1)."""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_PATH = Path("config/seasonal_calendar.yaml")


def load_seasonal_data(
    month: str,
    calendar_path: Path | None = None,
) -> str:
    """Load seasonal opportunities for a given month as formatted text.

    Args:
        month: Two-digit month string, e.g. "03" for March.
        calendar_path: Path to the seasonal calendar YAML. Defaults to
            config/seasonal_calendar.yaml.

    Returns:
        Formatted text with seasonal opportunities, or a fallback message.
    """
    path = calendar_path or DEFAULT_CALENDAR_PATH
    if not path.exists():
        logger.warning("Seasonal calendar not found at %s", path)
        return "Nenhuma data sazonal relevante para este periodo."

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        logger.exception("Error loading seasonal calendar from %s", path)
        return "Nenhuma data sazonal relevante para este periodo."

    months = data.get("months", {})
    month_key = month.zfill(2)
    events = months.get(month_key, [])

    if not events:
        return "Nenhuma data sazonal relevante para este periodo."

    lines = []
    for ev in events:
        date = ev.get("date", "")
        event = ev.get("event", "")
        segments = ", ".join(ev.get("segments", []))
        priority = ev.get("priority", "media")
        lines.append(f"- {date}: {event} (segmentos: {segments}) [prioridade: {priority}]")

    return "\n".join(lines)
