# tests/test_report_charts.py
from lambdas.report_generator.charts import (
    generate_ontime_pie_chart,
    generate_status_bar_chart,
    generate_time_per_status_chart,
)


class TestStatusBarChart:
    def test_returns_png_bytes(self):
        data = {"aprovado": 15, "em criacao": 3, "revisao": 2}
        result = generate_status_bar_chart(data, primary_color="#8A6CFF")
        assert isinstance(result, bytes)
        assert result[:8] == b'\x89PNG\r\n\x1a\n'  # PNG magic bytes

    def test_empty_data_returns_bytes(self):
        result = generate_status_bar_chart({}, primary_color="#8A6CFF")
        assert isinstance(result, bytes)


class TestOntimePieChart:
    def test_returns_png_bytes(self):
        result = generate_ontime_pie_chart(
            on_time_rate=0.8,
            primary_color="#8A6CFF",
            secondary_color="#0E2A47",
        )
        assert isinstance(result, bytes)
        assert result[:8] == b'\x89PNG\r\n\x1a\n'


class TestTimePerStatusChart:
    def test_returns_png_bytes(self):
        data = {"planejamento": 24.5, "em criacao": 48.0, "revisao": 12.0}
        result = generate_time_per_status_chart(data, primary_color="#8A6CFF")
        assert isinstance(result, bytes)
        assert result[:8] == b'\x89PNG\r\n\x1a\n'
