import logging

import httpx

from src.integrations.clickup.models import CreateTaskRequest

logger = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"


class ClickUpClient:
    def __init__(self, api_token: str):
        self._token = api_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._token,
            "Content-Type": "application/json",
        }

    async def create_task(self, list_id: str, task: CreateTaskRequest) -> dict:
        payload = task.model_dump(exclude_none=True)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/list/{list_id}/task",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s for list %s: %s",
                    response.status_code, list_id, response.text,
                )
            response.raise_for_status()
            return response.json()

    async def get_task(self, task_id: str) -> dict:
        """Get a single task by ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/task/{task_id}",
                headers=self._headers(),
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s for task %s: %s",
                    response.status_code, task_id, response.text,
                )
            response.raise_for_status()
            return response.json()

    async def get_comments(self, task_id: str) -> list[dict]:
        """Get comments for a task."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/task/{task_id}/comment",
                headers=self._headers(),
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s for task %s comments: %s",
                    response.status_code, task_id, response.text,
                )
            response.raise_for_status()
            return response.json().get("comments", [])

    async def get_tasks(
        self, list_id: str, *,
        assignees: list[int] | None = None,
        statuses: list[str] | None = None,
        include_closed: bool = False,
    ) -> list[dict]:
        """Get tasks from a list with optional filters."""
        params: list[tuple[str, str]] = []
        if assignees:
            for uid in assignees:
                params.append(("assignees[]", str(uid)))
        if statuses:
            for s in statuses:
                params.append(("statuses[]", s))
        if include_closed:
            params.append(("include_closed", "true"))

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/list/{list_id}/task",
                headers=self._headers(),
                params=params,
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s for list %s tasks: %s",
                    response.status_code, list_id, response.text,
                )
            response.raise_for_status()
            return response.json().get("tasks", [])

    async def update_task(self, task_id: str, **fields) -> dict:
        """Update task fields (status, assignees, etc.)."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{BASE_URL}/task/{task_id}",
                headers=self._headers(),
                json=fields,
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s updating task %s: %s",
                    response.status_code, task_id, response.text,
                )
            response.raise_for_status()
            return response.json()

    async def add_comment(self, task_id: str, comment_text: str) -> dict:
        """Add a comment to a task."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/task/{task_id}/comment",
                headers=self._headers(),
                json={"comment_text": comment_text},
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s adding comment to %s: %s",
                    response.status_code, task_id, response.text,
                )
            response.raise_for_status()
            return response.json()

    async def get_custom_fields(self, list_id: str) -> list[dict]:
        """Get custom fields for a list."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/list/{list_id}/field",
                headers=self._headers(),
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s for list %s fields: %s",
                    response.status_code, list_id, response.text,
                )
            response.raise_for_status()
            return response.json().get("fields", [])

    async def set_custom_field(self, task_id: str, field_id: str, value) -> dict:
        """Set a custom field value on a task."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/task/{task_id}/field/{field_id}",
                headers=self._headers(),
                json={"value": value},
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s setting field %s on task %s: %s",
                    response.status_code, field_id, task_id, response.text,
                )
            response.raise_for_status()
            return response.json()

    async def create_checklist(self, task_id: str, name: str) -> dict:
        """Create a checklist on a task. Returns the checklist object."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/task/{task_id}/checklist",
                headers=self._headers(),
                json={"name": name},
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s creating checklist on task %s: %s",
                    response.status_code, task_id, response.text,
                )
            response.raise_for_status()
            return response.json().get("checklist", {})

    async def add_checklist_item(self, checklist_id: str, name: str) -> dict:
        """Add an item to a checklist."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/checklist/{checklist_id}/checklist_item",
                headers=self._headers(),
                json={"name": name},
            )
            if response.status_code >= 400:
                logger.error(
                    "ClickUp API error %s adding item to checklist %s: %s",
                    response.status_code, checklist_id, response.text,
                )
            response.raise_for_status()
            return response.json().get("checklist", {})

    async def get_filtered_team_tasks(
        self,
        team_id: str,
        date_done_gt: int | None = None,
        date_done_lt: int | None = None,
    ) -> list[dict]:
        """Fetch workspace-scoped tasks with date filters.

        Uses the ClickUp ``GET /team/{team_id}/task`` endpoint which returns
        tasks across all lists in the workspace.  Paginates automatically
        using ClickUp's ``last_page`` boolean until all matching tasks have
        been collected.

        Args:
            team_id: The ClickUp workspace (team) ID.
            date_done_gt: Only return tasks completed after this Unix-ms timestamp.
            date_done_lt: Only return tasks completed before this Unix-ms timestamp.

        Returns:
            A flat list of task dicts aggregated from all pages.
        """
        all_tasks: list[dict] = []
        page = 0

        while True:
            params: dict[str, str] = {
                "page": str(page),
                "include_closed": "true",
                "subtasks": "true",
            }
            if date_done_gt is not None:
                params["date_done_gt"] = str(date_done_gt)
            if date_done_lt is not None:
                params["date_done_lt"] = str(date_done_lt)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{BASE_URL}/team/{team_id}/task",
                    headers=self._headers(),
                    params=params,
                )
                if response.status_code >= 400:
                    logger.error(
                        "ClickUp API error %s for team %s tasks: %s",
                        response.status_code, team_id, response.text,
                    )
                response.raise_for_status()
                data = response.json()

            tasks = data.get("tasks", [])
            all_tasks.extend(tasks)

            if data.get("last_page", True):
                break
            page += 1

        return all_tasks

    async def get_team_members(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/team",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            members = []
            for team in data.get("teams", []):
                for member in team.get("members", []):
                    members.append(member["user"])
            return members
