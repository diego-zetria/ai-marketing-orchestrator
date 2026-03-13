from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.admin.router import admin_router


def create_app(lifespan=None) -> FastAPI:
    app = FastAPI(title="Marketing Briefing Bot", version="0.1.0", lifespan=lifespan)
    app.include_router(admin_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/observability/status")
    async def observability_status():
        from src.observability import get_budget_status, get_observability_status
        status = get_observability_status()
        if status.get("initialized"):
            status["budget"] = get_budget_status()
        return status

    # Serve frontend SPA (only if build exists)
    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        assets_dir = str(frontend_dist / "assets")
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="static-assets",
        )

        # SPA fallback: non-API routes serve index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            file_path = frontend_dist / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(frontend_dist / "index.html")

    return app
