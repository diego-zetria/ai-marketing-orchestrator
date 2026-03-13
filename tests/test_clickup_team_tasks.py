import httpx
import pytest
import respx

from src.integrations.clickup.client import ClickUpClient


@pytest.fixture
def client():
    return ClickUpClient(api_token="test-token")


class TestGetFilteredTeamTasks:
    @respx.mock
    @pytest.mark.asyncio
    async def test_single_page_returns_tasks(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [
                    {"id": "t1", "name": "Task 1", "status": {"status": "aprovado"}},
                    {"id": "t2", "name": "Task 2", "status": {"status": "em criacao"}},
                ],
                "last_page": True,
            })
        )
        tasks = await client.get_filtered_team_tasks(
            team_id="team123", date_done_gt=1000, date_done_lt=2000,
        )
        assert len(tasks) == 2
        assert tasks[0]["id"] == "t1"
        assert tasks[1]["name"] == "Task 2"
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_paginates_until_last_page(self, client):
        page0 = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            side_effect=[
                httpx.Response(200, json={
                    "tasks": [{"id": f"t{i}"} for i in range(100)],
                    "last_page": False,
                }),
                httpx.Response(200, json={
                    "tasks": [{"id": "t100"}],
                    "last_page": True,
                }),
            ]
        )
        tasks = await client.get_filtered_team_tasks(
            team_id="team123", date_done_gt=1000, date_done_lt=2000,
        )
        assert len(tasks) == 101
        assert page0.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_includes_closed_tasks(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [{"id": "t1"}],
                "last_page": True,
            })
        )
        await client.get_filtered_team_tasks(
            team_id="team123", date_done_gt=1000, date_done_lt=2000,
        )
        request = route.calls[0].request
        assert "include_closed=true" in str(request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_date_done_params(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [],
                "last_page": True,
            })
        )
        await client.get_filtered_team_tasks(
            team_id="team123", date_done_gt=1000, date_done_lt=2000,
        )
        url = str(route.calls[0].request.url)
        assert "date_done_gt=1000" in url
        assert "date_done_lt=2000" in url

    @respx.mock
    @pytest.mark.asyncio
    async def test_omits_date_params_when_none(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [],
                "last_page": True,
            })
        )
        await client.get_filtered_team_tasks(team_id="team123")
        url = str(route.calls[0].request.url)
        assert "date_done_gt" not in url
        assert "date_done_lt" not in url

    @respx.mock
    @pytest.mark.asyncio
    async def test_includes_subtasks(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [],
                "last_page": True,
            })
        )
        await client.get_filtered_team_tasks(team_id="team123")
        url = str(route.calls[0].request.url)
        assert "subtasks=true" in url

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_auth_header(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [],
                "last_page": True,
            })
        )
        await client.get_filtered_team_tasks(team_id="team123")
        assert route.calls[0].request.headers["Authorization"] == "test-token"

    @respx.mock
    @pytest.mark.asyncio
    async def test_raises_on_api_error(self, client):
        respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(401, json={"err": "Unauthorized"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_filtered_team_tasks(team_id="team123")

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_tasks_response(self, client):
        respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            return_value=httpx.Response(200, json={
                "tasks": [],
                "last_page": True,
            })
        )
        tasks = await client.get_filtered_team_tasks(team_id="team123")
        assert tasks == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_page_param_increments_correctly(self, client):
        route = respx.get("https://api.clickup.com/api/v2/team/team123/task").mock(
            side_effect=[
                httpx.Response(200, json={
                    "tasks": [{"id": "t1"}],
                    "last_page": False,
                }),
                httpx.Response(200, json={
                    "tasks": [{"id": "t2"}],
                    "last_page": False,
                }),
                httpx.Response(200, json={
                    "tasks": [{"id": "t3"}],
                    "last_page": True,
                }),
            ]
        )
        tasks = await client.get_filtered_team_tasks(team_id="team123")
        assert len(tasks) == 3
        assert route.call_count == 3
        # Verify page params: 0, 1, 2
        assert "page=0" in str(route.calls[0].request.url)
        assert "page=1" in str(route.calls[1].request.url)
        assert "page=2" in str(route.calls[2].request.url)
