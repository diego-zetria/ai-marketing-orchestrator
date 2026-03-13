"""Matplotlib chart generators for monthly PDF reports."""
import io

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for Lambda

import matplotlib.pyplot as plt  # noqa: E402


def generate_status_bar_chart(
    tasks_by_status: dict[str, int],
    primary_color: str = "#8A6CFF",
) -> bytes:
    """Vertical bar chart of tasks by status. Returns PNG bytes."""
    fig, ax = plt.subplots(figsize=(7, 3.5))

    if not tasks_by_status:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=14, color="#888")
        ax.set_axis_off()
    else:
        statuses = list(tasks_by_status.keys())
        counts = list(tasks_by_status.values())
        bars = ax.bar(statuses, counts, color=primary_color, width=0.6)
        ax.set_ylabel("Tasks")
        ax.set_title("Tasks por Status", fontweight="bold", fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for bar, count in zip(bars, counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(count), ha="center", va="bottom", fontsize=10, fontweight="bold",
            )
        plt.xticks(rotation=30, ha="right", fontsize=9)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_ontime_pie_chart(
    on_time_rate: float,
    primary_color: str = "#8A6CFF",
    secondary_color: str = "#0E2A47",
) -> bytes:
    """Pie chart: on-time vs late. Returns PNG bytes."""
    fig, ax = plt.subplots(figsize=(4, 4))
    late_rate = max(0, 1.0 - on_time_rate)

    if on_time_rate == 0 and late_rate == 0:
        on_time_rate = 1.0  # show 100% if no data

    sizes = [on_time_rate, late_rate]
    labels = ["No prazo", "Atrasado"]
    colors = [primary_color, secondary_color]
    explode = (0.03, 0)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct="%1.0f%%", startangle=90, textprops={"fontsize": 11},
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_color("white")
    ax.set_title("Entregas no Prazo", fontweight="bold", fontsize=12)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_time_per_status_chart(
    time_per_status: dict[str, float],
    primary_color: str = "#8A6CFF",
) -> bytes:
    """Horizontal bar chart of avg hours per status. Returns PNG bytes."""
    fig, ax = plt.subplots(figsize=(7, 3.5))

    if not time_per_status:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=14, color="#888")
        ax.set_axis_off()
    else:
        sorted_data = sorted(time_per_status.items(), key=lambda x: x[1])
        statuses = [s for s, _ in sorted_data]
        hours = [h for _, h in sorted_data]
        bars = ax.barh(statuses, hours, color=primary_color, height=0.6)
        ax.set_xlabel("Horas (media)")
        ax.set_title("Tempo Medio por Status", fontweight="bold", fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for bar, h in zip(bars, hours):
            ax.text(
                bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{h:.1f}h", ha="left", va="center", fontsize=9,
            )

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
