from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def schedule_prompt_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard shown after briefing analysis to offer schedule generation."""
    buttons = [
        InlineKeyboardButton("Gerar Cronograma", callback_data="schedule_generate"),
        InlineKeyboardButton("Pular", callback_data="schedule_skip"),
    ]
    return InlineKeyboardMarkup([buttons])


def review_action_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for AI review actions: approve or request changes."""
    buttons = [
        InlineKeyboardButton("Aprovar", callback_data=f"review_approve:{task_id}"),
        InlineKeyboardButton("Pedir Alteracao", callback_data=f"review_change:{task_id}"),
    ]
    return InlineKeyboardMarkup([buttons])


def schedule_review_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard shown after schedule is generated for user review."""
    buttons = [
        InlineKeyboardButton("Aprovar", callback_data="schedule_approve"),
        InlineKeyboardButton("Editar", callback_data="schedule_edit"),
        InlineKeyboardButton("Refazer", callback_data="schedule_regenerate"),
    ]
    return InlineKeyboardMarkup([buttons])


def auto_status_confirm_keyboard(
    task_id: str, target_status: str,
) -> InlineKeyboardMarkup:
    """Inline keyboard for A1 auto-status confirmation."""
    payload = f"{task_id}:{target_status}"
    buttons = [
        InlineKeyboardButton(
            "Confirmar",
            callback_data=f"autostatus_confirm:{payload}",
        ),
        InlineKeyboardButton(
            "Ignorar",
            callback_data=f"autostatus_ignore:{payload}",
        ),
    ]
    return InlineKeyboardMarkup([buttons])


def client_approval_confirm_keyboard(
    task_id: str,
) -> InlineKeyboardMarkup:
    """Inline keyboard for client approval confirmation."""
    buttons = [
        InlineKeyboardButton(
            "Enviar para Cliente",
            callback_data=f"clientapproval_confirm:{task_id}",
        ),
        InlineKeyboardButton(
            "Ignorar",
            callback_data=f"clientapproval_ignore:{task_id}",
        ),
    ]
    return InlineKeyboardMarkup([buttons])


def creative_direction_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard shown after creative direction is generated."""
    buttons = [
        InlineKeyboardButton(
            "Incorporar no Cronograma", callback_data="creative_use",
        ),
        InlineKeyboardButton("Pular", callback_data="creative_skip"),
    ]
    return InlineKeyboardMarkup([buttons])
