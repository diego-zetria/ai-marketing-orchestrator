"""Tests for frontend static file serving in FastAPI app."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.mark.asyncio
async def test_app_works_without_frontend_dist():
    """App starts normally when frontend/dist does not exist."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_admin_not_mounted_without_dist(tmp_path, monkeypatch):
    """When frontend/dist does not exist, /admin returns 404."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as client:
        resp = await client.get("/admin/")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_static_mount_serves_files_when_dist_exists(tmp_path, monkeypatch):
    """When frontend/dist exists, files are served under /admin."""
    # Create a fake frontend/dist with an index.html
    dist_dir = tmp_path / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Agency Admin</body></html>")
    (dist_dir / "assets").mkdir()
    (dist_dir / "assets" / "main.js").write_text("console.log('ok');")

    # Change working directory so Path("frontend/dist") resolves to our tmp dir
    monkeypatch.chdir(tmp_path)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as client:
        # SPA fallback serves index.html at root
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Agency Admin" in resp.text

        # Static asset served at /assets/
        resp = await client.get("/assets/main.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text

        # Health endpoint still works alongside static mount
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
