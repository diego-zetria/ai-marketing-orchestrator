"""fpdf2-based PDF report generator with Agency branding."""
from __future__ import annotations

import io
import logging

from fpdf import FPDF

from lambdas.report_generator.charts import (
    generate_ontime_pie_chart,
    generate_status_bar_chart,
    generate_time_per_status_chart,
)
from src.agents.schemas import MonthlyReport

logger = logging.getLogger(__name__)

# Agency Brand colors
PULSE_VIOLET = "#8A6CFF"
QUANTUM_BLUE = "#0E2A47"
LIGHT_GRAY = "#F5F5F5"
WHITE = "#FFFFFF"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string like '#8A6CFF' to an (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _create_base_pdf() -> FPDF:
    """Create a base FPDF instance with standard A4 settings.

    Uses cp1252 encoding to support em-dash, bullet, and other
    Windows-1252 characters with built-in Helvetica font.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = "cp1252"
    pdf.set_auto_page_break(auto=True, margin=20)
    return pdf


def _add_header(pdf: FPDF, client_name: str, period: str) -> None:
    """Add branded header to current page."""
    r, g, b = _hex_to_rgb(QUANTUM_BLUE)
    pdf.set_fill_color(r, g, b)
    pdf.rect(0, 0, 210, 35, "F")

    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, f"Relatorio Mensal — {client_name}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, period, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(42)


def _add_kpi_cards(pdf: FPDF, report: MonthlyReport) -> None:
    """Add KPI summary cards row."""
    pdf.set_font("Helvetica", "B", 11)
    r, g, b = _hex_to_rgb(PULSE_VIOLET)

    cards = [
        ("Tasks Concluidas", str(report.total_tasks_completed)),
        ("No Prazo", f"{report.on_time_rate:.0%}"),
        ("1a Aprovacao", f"{report.approval_metrics.first_approval_rate:.0%}"),
        ("Alteracoes", str(report.approval_metrics.total_alterations)),
    ]

    card_w = 42
    margin = 4
    start_x = (210 - (card_w * 4 + margin * 3)) / 2

    y = pdf.get_y()
    for i, (label, value) in enumerate(cards):
        x = start_x + i * (card_w + margin)
        pdf.set_fill_color(r, g, b)
        pdf.set_xy(x, y)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(card_w, 12, value, align="C", fill=True)
        pdf.set_xy(x, y + 12)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(card_w, 7, label, align="C", fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + 25)


def _add_executive_summary(pdf: FPDF, text: str) -> None:
    """Add the executive summary section."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Resumo Executivo", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, text)
    pdf.ln(5)


def _add_chart_image(pdf: FPDF, png_bytes: bytes, w: float = 170) -> None:
    """Embed a PNG chart image centered on the page."""
    buf = io.BytesIO(png_bytes)
    pdf.image(buf, x=(210 - w) / 2, w=w)
    pdf.ln(5)


def _add_section_title(pdf: FPDF, title: str) -> None:
    """Add a colored section title."""
    r, g, b = _hex_to_rgb(PULSE_VIOLET)
    pdf.set_text_color(r, g, b)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _add_bullet_list(pdf: FPDF, items: list[str]) -> None:
    """Add a bulleted list of items."""
    pdf.set_font("Helvetica", "", 10)
    for item in items:
        pdf.cell(5)
        pdf.cell(0, 6, f"•  {item}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _add_approval_table(pdf: FPDF, report: MonthlyReport) -> None:
    """Add approval metrics as a simple table."""
    am = report.approval_metrics
    _add_section_title(pdf, "Metricas de Aprovacao")
    pdf.set_font("Helvetica", "", 10)
    rows = [
        ("Assets revisados", str(am.total_assets_reviewed)),
        ("Taxa primeira aprovacao", f"{am.first_approval_rate:.0%}"),
        ("Media dias para decisao", f"{am.avg_review_days:.1f} dias"),
        ("Total alteracoes", str(am.total_alterations)),
    ]
    for label, value in rows:
        pdf.cell(90, 7, f"  {label}", border="B")
        pdf.cell(0, 7, value, border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)


def _add_footer(pdf: FPDF) -> None:
    """Add branded footer at the bottom of the current page."""
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 8)
    r, g, b = _hex_to_rgb(PULSE_VIOLET)
    pdf.set_text_color(r, g, b)
    pdf.cell(0, 10, "Agencia Agency — Relatorio gerado automaticamente", align="C")
    pdf.set_text_color(0, 0, 0)


def build_client_pdf(report: MonthlyReport) -> bytes:
    """Build the client-facing PDF (no bottlenecks, polished).

    Args:
        report: The MonthlyReport data to render.

    Returns:
        Raw PDF bytes ready for storage or email attachment.
    """
    pdf = _create_base_pdf()

    # Page 1: Header + KPIs + Summary
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)
    _add_kpi_cards(pdf, report)
    _add_executive_summary(pdf, report.resumo_executivo)
    _add_footer(pdf)

    # Page 2: Charts + Approval table
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)

    status_chart = generate_status_bar_chart(report.tasks_by_status, PULSE_VIOLET)
    _add_chart_image(pdf, status_chart)

    ontime_chart = generate_ontime_pie_chart(report.on_time_rate, PULSE_VIOLET, QUANTUM_BLUE)
    _add_chart_image(pdf, ontime_chart, w=90)

    _add_approval_table(pdf, report)
    _add_footer(pdf)

    # Page 3: Time per status + Recommendations + Highlights
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)

    if report.time_per_status:
        time_chart = generate_time_per_status_chart(report.time_per_status, PULSE_VIOLET)
        _add_chart_image(pdf, time_chart)

    if report.recommendations:
        _add_section_title(pdf, "Recomendacoes")
        _add_bullet_list(pdf, report.recommendations)

    if report.highlights:
        _add_section_title(pdf, "Destaques do Mes")
        _add_bullet_list(pdf, report.highlights)

    _add_footer(pdf)

    return bytes(pdf.output())


def build_internal_pdf(report: MonthlyReport) -> bytes:
    """Build the internal PDF (includes bottlenecks + extra details).

    The internal version contains everything the client PDF has, plus
    a dedicated page for bottleneck analysis that should not be shared
    externally.

    Args:
        report: The MonthlyReport data to render.

    Returns:
        Raw PDF bytes ready for storage or email attachment.
    """
    pdf = _create_base_pdf()

    # Page 1: Header + KPIs + Summary
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)
    _add_kpi_cards(pdf, report)
    _add_executive_summary(pdf, report.resumo_executivo)
    _add_footer(pdf)

    # Page 2: Charts + Approval table
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)
    status_chart = generate_status_bar_chart(report.tasks_by_status, PULSE_VIOLET)
    _add_chart_image(pdf, status_chart)
    ontime_chart = generate_ontime_pie_chart(report.on_time_rate, PULSE_VIOLET, QUANTUM_BLUE)
    _add_chart_image(pdf, ontime_chart, w=90)
    _add_approval_table(pdf, report)
    _add_footer(pdf)

    # Page 3: Time per status + Recommendations + Highlights
    pdf.add_page()
    _add_header(pdf, report.client_name, report.period)
    if report.time_per_status:
        time_chart = generate_time_per_status_chart(report.time_per_status, PULSE_VIOLET)
        _add_chart_image(pdf, time_chart)
    if report.recommendations:
        _add_section_title(pdf, "Recomendacoes")
        _add_bullet_list(pdf, report.recommendations)
    if report.highlights:
        _add_section_title(pdf, "Destaques do Mes")
        _add_bullet_list(pdf, report.highlights)
    _add_footer(pdf)

    # Page 4: Bottlenecks (internal only)
    if report.bottlenecks:
        pdf.add_page()
        _add_header(pdf, report.client_name, report.period)
        _add_section_title(pdf, "Analise de Gargalos (Interno)")
        _add_bullet_list(pdf, report.bottlenecks)
        _add_footer(pdf)

    return bytes(pdf.output())
