from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    name: str
    description: str = ""
    assignees: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    priority: int | None = None  # 1=urgent, 2=high, 3=normal, 4=low
    status: str | None = None
    parent: str | None = None  # parent task ID for subtasks
    due_date: int | None = None  # Unix timestamp in milliseconds
