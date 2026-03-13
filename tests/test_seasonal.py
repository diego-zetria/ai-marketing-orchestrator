"""Tests for seasonal calendar loading."""

from pathlib import Path

from src.agents.seasonal import load_seasonal_data


def test_load_seasonal_data_for_month(tmp_path):
    cal = tmp_path / "seasonal_calendar.yaml"
    cal.write_text(
        "months:\n"
        '  "03":\n'
        '    - date: "08/03"\n'
        '      event: "Dia Internacional da Mulher"\n'
        '      segments: ["all"]\n'
        '      priority: "alta"\n'
        '    - date: "15/03"\n'
        '      event: "Dia do Consumidor"\n'
        '      segments: ["e-commerce"]\n'
        '      priority: "alta"\n'
    )
    result = load_seasonal_data("03", calendar_path=cal)
    assert "Dia Internacional da Mulher" in result
    assert "Dia do Consumidor" in result
    assert "08/03" in result


def test_load_seasonal_data_empty_month(tmp_path):
    cal = tmp_path / "seasonal_calendar.yaml"
    cal.write_text(
        "months:\n"
        '  "03":\n'
        '    - date: "08/03"\n'
        '      event: "Teste"\n'
        '      segments: ["all"]\n'
        '      priority: "media"\n'
    )
    result = load_seasonal_data("07", calendar_path=cal)
    assert result == "Nenhuma data sazonal relevante para este periodo."


def test_load_seasonal_data_missing_file():
    result = load_seasonal_data("03", calendar_path=Path("/nonexistent/calendar.yaml"))
    assert result == "Nenhuma data sazonal relevante para este periodo."


def test_load_seasonal_data_default_path():
    # Should work with the real config/seasonal_calendar.yaml
    result = load_seasonal_data("03")
    assert "Dia Internacional da Mulher" in result
