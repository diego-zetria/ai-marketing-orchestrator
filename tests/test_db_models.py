import uuid

from src.db.models import BriefingLog, TeamMember


def test_briefing_log_creation():
    log = BriefingLog(
        id=uuid.uuid4(),
        telegram_user_id=123456,
        telegram_message_id=789,
        raw_briefing="Briefing teste",
        analysis_result={"client_name": "Teste"},
        tasks_created={"parent": "task_1", "subtasks": ["sub_1"]},
        status="success",
        tokens_used=150,
        model_id="anthropic/claude-sonnet-4",
    )
    assert log.status == "success"
    assert log.telegram_user_id == 123456


def test_team_member_creation():
    member = TeamMember(
        id=uuid.uuid4(),
        name="Joao Designer",
        clickup_user_id="cu_123",
        telegram_username="joao_d",
        skills=["design"],
        active=True,
    )
    assert member.name == "Joao Designer"
    assert "design" in member.skills
