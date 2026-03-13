import pytest
from pydantic import ValidationError

from src.agents.schemas import PostSchedule, ScheduledPost


def test_scheduled_post_valid():
    post = ScheduledPost(
        date="03/03",
        post_type="POST",
        title="Inauguracao da loja",
        platform="instagram",
    )
    assert post.date == "03/03"
    assert post.post_type == "POST"
    assert post.notes == ""


def test_scheduled_post_with_notes():
    post = ScheduledPost(
        date="10/03",
        post_type="REELS",
        title="Tour pela loja",
        platform="instagram",
        notes="Usar video do cliente",
    )
    assert post.notes == "Usar video do cliente"


def test_post_schedule_valid():
    schedule = PostSchedule(
        posts=[
            ScheduledPost(date="03/03", post_type="POST", title="Post 1", platform="instagram"),
            ScheduledPost(
                date="06/03", post_type="CARROSSEL",
                title="Post 2", platform="instagram",
            ),
        ],
        month="marco",
        year="2026",
        platform="instagram",
        observations="Cronograma otimizado para 2 posts por semana.",
    )
    assert len(schedule.posts) == 2
    assert schedule.month == "marco"


def test_post_schedule_requires_posts():
    with pytest.raises(ValidationError):
        PostSchedule(
            posts=[],
            month="marco",
            year="2026",
            platform="instagram",
            observations="",
        )


def test_scheduled_post_task_name():
    post = ScheduledPost(
        date="03/03",
        post_type="POST",
        title="Inauguracao da loja",
        platform="instagram",
    )
    assert post.task_name == "03/03 - POST Inauguracao da loja"


def test_post_schedule_formatted_text():
    schedule = PostSchedule(
        posts=[
            ScheduledPost(date="03/03", post_type="POST", title="Post 1", platform="instagram"),
            ScheduledPost(
                date="06/03", post_type="CARROSSEL",
                title="Post 2", platform="instagram",
            ),
        ],
        month="marco",
        year="2026",
        platform="instagram",
        observations="Bom cronograma.",
    )
    text = schedule.formatted_text
    assert "1. 03/03 - POST Post 1" in text
    assert "2. 06/03 - CARROSSEL Post 2" in text
    assert "Bom cronograma." in text
