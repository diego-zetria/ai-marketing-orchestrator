from src.agents.schemas import BriefingAnalysis


def format_success_response(
    analysis: BriefingAnalysis,
    tasks_info: list[dict],
) -> str:
    urgency_label = "Urgente" if analysis.urgency == "urgent" else "Normal"

    lines = [
        f"*Briefing analisado - Cliente: {analysis.client_name}*",
        "",
        f"Card criado: *{analysis.card_title}*",
        f"Prioridade: {urgency_label}",
        "",
        f"{len(tasks_info)} subtask(s) criada(s):",
    ]

    for task in tasks_info:
        assignees_str = ", ".join(task["assignees"]) if task["assignees"] else "sem atribuicao"
        lines.append(f"  - {task['title']} -> {assignees_str}")

    if analysis.observations:
        lines.append("")
        lines.append(f"*Obs:* {analysis.observations}")

    return "\n".join(lines)


def format_error_response(message: str) -> str:
    safe_msg = message.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
    return f"*Erro no processamento*\n\n{safe_msg}\n\nTente novamente ou reformule o briefing."
