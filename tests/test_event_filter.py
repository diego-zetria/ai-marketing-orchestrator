import time

from src.bot.event_filter import EventFilter


class TestIsBotEvent:
    def test_detects_bot_in_history_items(self):
        ef = EventFilter(bot_user_id="12345")
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "history_items": [
                {"field": "status", "user": {"id": 12345, "username": "Bot"}},
            ],
        }
        assert ef.is_bot_event(event) is True

    def test_detects_bot_in_history_items_string_id(self):
        ef = EventFilter(bot_user_id="12345")
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "history_items": [
                {"field": "status", "user": {"id": "12345", "username": "Bot"}},
            ],
        }
        assert ef.is_bot_event(event) is True

    def test_ignores_human_event(self):
        ef = EventFilter(bot_user_id="12345")
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "history_items": [
                {"field": "status", "user": {"id": 99999, "username": "Human"}},
            ],
        }
        assert ef.is_bot_event(event) is False

    def test_detects_bot_in_top_level_user(self):
        ef = EventFilter(bot_user_id="12345")
        event = {
            "event": "taskCreated",
            "task_id": "t1",
            "user": {"id": 12345},
        }
        assert ef.is_bot_event(event) is True

    def test_empty_bot_user_id_never_matches(self):
        ef = EventFilter(bot_user_id="")
        event = {
            "event": "taskStatusUpdated",
            "history_items": [
                {"field": "status", "user": {"id": 12345}},
            ],
        }
        assert ef.is_bot_event(event) is False

    def test_empty_event_returns_false(self):
        ef = EventFilter(bot_user_id="12345")
        assert ef.is_bot_event({}) is False


class TestIsDebounced:
    def test_first_event_is_not_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        assert ef.is_debounced("t1", "taskStatusUpdated") is False

    def test_second_event_within_window_is_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        ef.is_debounced("t1", "taskStatusUpdated")  # first: records it
        assert ef.is_debounced("t1", "taskStatusUpdated") is True

    def test_different_task_ids_not_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        ef.is_debounced("t1", "taskStatusUpdated")
        assert ef.is_debounced("t2", "taskStatusUpdated") is False

    def test_different_event_types_not_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        ef.is_debounced("t1", "taskStatusUpdated")
        assert ef.is_debounced("t1", "taskCommentPosted") is False

    def test_event_after_window_not_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=1)
        ef.is_debounced("t1", "taskStatusUpdated")
        # Simulate time passing
        ef._recent["t1:taskStatusUpdated"] = time.monotonic() - 2
        assert ef.is_debounced("t1", "taskStatusUpdated") is False

    def test_empty_task_id_never_debounced(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        assert ef.is_debounced("", "taskStatusUpdated") is False
        assert ef.is_debounced("", "taskStatusUpdated") is False


class TestPrune:
    def test_prune_removes_old_entries(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        now = time.monotonic()
        # Add an old entry manually
        ef._recent["old_task:taskStatusUpdated"] = now - 400
        ef._recent["recent_task:taskStatusUpdated"] = now - 10

        ef._prune(now)

        assert "old_task:taskStatusUpdated" not in ef._recent
        assert "recent_task:taskStatusUpdated" in ef._recent

    def test_prune_called_on_debounce_check(self):
        ef = EventFilter(bot_user_id="", debounce_seconds=30)
        now = time.monotonic()
        ef._recent["old:taskStatusUpdated"] = now - 400

        ef.is_debounced("new_task", "taskStatusUpdated")

        assert "old:taskStatusUpdated" not in ef._recent
