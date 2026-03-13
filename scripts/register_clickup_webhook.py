"""Register ClickUp webhook for task status, comment, and creation events.

Usage:
    python scripts/register_clickup_webhook.py                     # List existing webhooks
    python scripts/register_clickup_webhook.py <endpoint_url>      # Register new webhook
    python scripts/register_clickup_webhook.py --delete <id>       # Delete webhook

Example:
    python scripts/register_clickup_webhook.py https://your-domain.com/webhooks/clickup
"""
import asyncio
import sys

import httpx

from src.config.settings import Settings

CLICKUP_API = "https://api.clickup.com/api/v2"


async def register_webhook(endpoint_url: str):
    settings = Settings()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{CLICKUP_API}/team/{settings.clickup_team_id}/webhook",
            headers={
                "Authorization": settings.clickup_api_token,
                "Content-Type": "application/json",
            },
            json={
                "endpoint": endpoint_url,
                "events": [
                    "taskStatusUpdated",
                    "taskCommentPosted",
                    "taskCreated",
                ],
                "secret": settings.clickup_webhook_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        print("Webhook registered successfully!")
        print(f"  ID: {data.get('id')}")
        print(f"  Endpoint: {data.get('endpoint')}")
        print(f"  Events: {data.get('events')}")


async def list_webhooks():
    settings = Settings()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CLICKUP_API}/team/{settings.clickup_team_id}/webhook",
            headers={"Authorization": settings.clickup_api_token},
        )
        response.raise_for_status()
        data = response.json()
        webhooks = data.get("webhooks", [])
        if not webhooks:
            print("No webhooks registered.")
            return
        print(f"{len(webhooks)} webhook(s) registered:")
        for wh in webhooks:
            status = "active" if wh.get("active") else "inactive"
            endpoint = wh.get('endpoint')
            events = wh.get('events')
            print(f"  ID: {wh['id']} | {status} | {endpoint} | Events: {events}")


async def delete_webhook(webhook_id: str):
    settings = Settings()

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{CLICKUP_API}/webhook/{webhook_id}",
            headers={"Authorization": settings.clickup_api_token},
        )
        if response.status_code == 200:
            print(f"Webhook {webhook_id} deleted.")
        else:
            print(f"Error deleting webhook: {response.status_code} {response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Listing existing webhooks...")
        asyncio.run(list_webhooks())
    elif sys.argv[1] == "--delete" and len(sys.argv) > 2:
        asyncio.run(delete_webhook(sys.argv[2]))
    else:
        endpoint = sys.argv[1]
        print(f"Registering webhook for: {endpoint}")
        asyncio.run(register_webhook(endpoint))
