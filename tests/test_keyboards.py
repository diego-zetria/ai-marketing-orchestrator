from src.bot.keyboards import schedule_prompt_keyboard, schedule_review_keyboard


def test_schedule_prompt_keyboard_has_two_buttons():
    kb = schedule_prompt_keyboard()
    assert len(kb.inline_keyboard) == 1
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].text == "Gerar Cronograma"
    assert buttons[0].callback_data == "schedule_generate"
    assert buttons[1].text == "Pular"
    assert buttons[1].callback_data == "schedule_skip"


def test_schedule_review_keyboard_has_three_buttons():
    kb = schedule_review_keyboard()
    assert len(kb.inline_keyboard) == 1
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 3
    assert buttons[0].callback_data == "schedule_approve"
    assert buttons[1].callback_data == "schedule_edit"
    assert buttons[2].callback_data == "schedule_regenerate"
