import httpx
import pytest
import respx

from src.integrations.clickup.client import ClickUpClient
from src.integrations.clickup.models import CreateTaskRequest


@pytest.fixture
def client():
    return ClickUpClient(api_token="test-token")


@respx.mock
@pytest.mark.asyncio
async def test_create_task(client):
    respx.post("https://api.clickup.com/api/v2/list/list123/task").mock(
        return_value=httpx.Response(
            200,
            json={"id": "task_abc", "name": "Instagram - Loja Bella - Fev 2026"},
        )
    )

    request = CreateTaskRequest(
        name="Instagram - Loja Bella - Fev 2026",
        description="Campanha de verao",
        assignees=[123],
        tags=["design"],
        priority=2,
        status="planejamento",
    )
    result = await client.create_task(list_id="list123", task=request)
    assert result["id"] == "task_abc"


@respx.mock
@pytest.mark.asyncio
async def test_create_subtask(client):
    respx.post("https://api.clickup.com/api/v2/list/list123/task").mock(
        return_value=httpx.Response(
            200,
            json={"id": "sub_123", "name": "Post 1", "parent": "task_abc"},
        )
    )

    request = CreateTaskRequest(
        name="Post 1",
        description="Primeiro post da campanha",
        assignees=[456],
        tags=["design"],
        parent="task_abc",
    )
    result = await client.create_task(list_id="list123", task=request)
    assert result["id"] == "sub_123"


@respx.mock
@pytest.mark.asyncio
async def test_get_team_members(client):
    respx.get("https://api.clickup.com/api/v2/team").mock(
        return_value=httpx.Response(
            200,
            json={
                "teams": [
                    {
                        "id": "team1",
                        "members": [
                            {"user": {"id": 111, "username": "joao", "email": "j@app.com"}},
                            {"user": {"id": 222, "username": "maria", "email": "m@app.com"}},
                        ],
                    }
                ]
            },
        )
    )

    members = await client.get_team_members()
    assert len(members) == 2
    assert members[0]["id"] == 111


@respx.mock
@pytest.mark.asyncio
async def test_auth_header_is_set(client):
    route = respx.get("https://api.clickup.com/api/v2/team").mock(
        return_value=httpx.Response(200, json={"teams": [{"id": "t", "members": []}]})
    )

    await client.get_team_members()

    assert route.calls[0].request.headers["Authorization"] == "test-token"


def test_create_task_request_with_due_date():
    from src.integrations.clickup.models import CreateTaskRequest
    task = CreateTaskRequest(
        name="Test",
        due_date=1709251200000,
    )
    payload = task.model_dump(exclude_none=True)
    assert payload["due_date"] == 1709251200000
    assert "due_date" in payload


def test_create_task_request_without_due_date():
    from src.integrations.clickup.models import CreateTaskRequest
    task = CreateTaskRequest(name="Test")
    payload = task.model_dump(exclude_none=True)
    assert "due_date" not in payload


@respx.mock
@pytest.mark.asyncio
async def test_get_task(client):
    respx.get("https://api.clickup.com/api/v2/task/task_abc").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "task_abc",
                "name": "Post Instagram ClientDelta",
                "status": {"status": "desenvolvimento"},
                "assignees": [{"id": 95324421, "username": "Pedro"}],
                "due_date": "1709251200000",
                "url": "https://app.clickup.com/t/task_abc",
            },
        )
    )
    result = await client.get_task("task_abc")
    assert result["id"] == "task_abc"
    assert result["status"]["status"] == "desenvolvimento"


@respx.mock
@pytest.mark.asyncio
async def test_get_tasks(client):
    respx.get("https://api.clickup.com/api/v2/list/list123/task").mock(
        return_value=httpx.Response(
            200,
            json={
                "tasks": [
                    {"id": "t1", "name": "Task 1", "status": {"status": "desenvolvimento"}},
                    {"id": "t2", "name": "Task 2", "status": {"status": "revisao"}},
                ],
            },
        )
    )
    result = await client.get_tasks("list123")
    assert len(result) == 2
    assert result[0]["id"] == "t1"


@respx.mock
@pytest.mark.asyncio
async def test_get_tasks_with_assignee_filter(client):
    route = respx.get("https://api.clickup.com/api/v2/list/list123/task").mock(
        return_value=httpx.Response(200, json={"tasks": []})
    )
    await client.get_tasks("list123", assignees=[95324421])
    assert "assignees" in str(route.calls[0].request.url)


@respx.mock
@pytest.mark.asyncio
async def test_update_task_status(client):
    respx.put("https://api.clickup.com/api/v2/task/task_abc").mock(
        return_value=httpx.Response(
            200,
            json={"id": "task_abc", "status": {"status": "revisao"}},
        )
    )
    result = await client.update_task("task_abc", status="revisao")
    assert result["status"]["status"] == "revisao"


@respx.mock
@pytest.mark.asyncio
async def test_get_task_error_handling(client):
    respx.get("https://api.clickup.com/api/v2/task/invalid").mock(
        return_value=httpx.Response(404, json={"err": "Task not found"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_task("invalid")


@respx.mock
@pytest.mark.asyncio
async def test_add_comment(client):
    respx.post("https://api.clickup.com/api/v2/task/task_abc/comment").mock(
        return_value=httpx.Response(200, json={"id": "c1", "comment_text": "Boa!"})
    )
    result = await client.add_comment("task_abc", "Boa!")
    assert result["comment_text"] == "Boa!"


@respx.mock
@pytest.mark.asyncio
async def test_add_comment_error(client):
    respx.post("https://api.clickup.com/api/v2/task/invalid/comment").mock(
        return_value=httpx.Response(404, json={"err": "Task not found"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.add_comment("invalid", "test")


# === New methods: custom fields, checklists ===

@respx.mock
@pytest.mark.asyncio
async def test_get_custom_fields(client):
    respx.get("https://api.clickup.com/api/v2/list/list123/field").mock(
        return_value=httpx.Response(
            200,
            json={
                "fields": [
                    {"id": "f1", "name": "Entregas dentro do prazo", "type": "number"},
                    {"id": "f2", "name": "N de alteracoes", "type": "number"},
                ],
            },
        )
    )
    result = await client.get_custom_fields("list123")
    assert len(result) == 2
    assert result[0]["id"] == "f1"


@respx.mock
@pytest.mark.asyncio
async def test_set_custom_field(client):
    respx.post("https://api.clickup.com/api/v2/task/task_abc/field/f2").mock(
        return_value=httpx.Response(200, json={})
    )
    result = await client.set_custom_field("task_abc", "f2", 3)
    assert result == {}


@respx.mock
@pytest.mark.asyncio
async def test_set_custom_field_error(client):
    respx.post("https://api.clickup.com/api/v2/task/invalid/field/f1").mock(
        return_value=httpx.Response(404, json={"err": "Task not found"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.set_custom_field("invalid", "f1", 1)


@respx.mock
@pytest.mark.asyncio
async def test_create_checklist(client):
    respx.post("https://api.clickup.com/api/v2/task/task_abc/checklist").mock(
        return_value=httpx.Response(
            200,
            json={"checklist": {"id": "cl1", "name": "Review Checklist", "items": []}},
        )
    )
    result = await client.create_checklist("task_abc", "Review Checklist")
    assert result["id"] == "cl1"
    assert result["name"] == "Review Checklist"


@respx.mock
@pytest.mark.asyncio
async def test_add_checklist_item(client):
    respx.post("https://api.clickup.com/api/v2/checklist/cl1/checklist_item").mock(
        return_value=httpx.Response(
            200,
            json={
                "checklist": {
                    "id": "cl1",
                    "items": [{"id": "i1", "name": "Check branding"}],
                },
            },
        )
    )
    result = await client.add_checklist_item("cl1", "Check branding")
    assert result["items"][0]["name"] == "Check branding"


@respx.mock
@pytest.mark.asyncio
async def test_add_checklist_item_error(client):
    respx.post("https://api.clickup.com/api/v2/checklist/invalid/checklist_item").mock(
        return_value=httpx.Response(404, json={"err": "Checklist not found"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.add_checklist_item("invalid", "item")
