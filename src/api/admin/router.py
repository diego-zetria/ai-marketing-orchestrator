from fastapi import APIRouter, Depends

from src.api.admin.activity import activity_router
from src.api.admin.agents import agents_router
from src.api.admin.approvals import approvals_router
from src.api.admin.auth import auth_router, get_current_admin, roles_router, users_router
from src.api.admin.automations import automations_router
from src.api.admin.brands import brands_router
from src.api.admin.clients import clients_router
from src.api.admin.dashboard import dashboard_router
from src.api.admin.health import health_router
from src.api.admin.knowledge import knowledge_router
from src.api.admin.media import media_router
from src.api.admin.models import models_router
from src.api.admin.notifications import notifications_router
from src.api.admin.rules import rules_router
from src.api.admin.system import system_router
from src.api.admin.team import team_router
from src.api.admin.tools import tools_router
from src.api.admin.topics import topics_router
from src.api.admin.webhooks import webhooks_router
from src.api.admin.workflows import workflows_router

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_router.include_router(auth_router)
admin_router.include_router(team_router)
admin_router.include_router(clients_router)
admin_router.include_router(rules_router)
admin_router.include_router(agents_router)
admin_router.include_router(brands_router)
admin_router.include_router(tools_router)
admin_router.include_router(knowledge_router)
admin_router.include_router(models_router)
admin_router.include_router(system_router)
admin_router.include_router(approvals_router)
admin_router.include_router(dashboard_router)
admin_router.include_router(notifications_router)
admin_router.include_router(activity_router)
admin_router.include_router(workflows_router)
admin_router.include_router(automations_router)
admin_router.include_router(topics_router)
admin_router.include_router(webhooks_router)
admin_router.include_router(media_router)
admin_router.include_router(health_router)
admin_router.include_router(users_router)
admin_router.include_router(roles_router)


@admin_router.get("/test-auth")
async def test_auth(admin: str = Depends(get_current_admin)):
    return {"authenticated": True}
