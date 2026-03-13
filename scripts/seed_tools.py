"""Seed the Agent Tools registry via the Admin API.

Authenticates with the admin endpoint, then POSTs each tool definition.
Existing tools (HTTP 409) are skipped gracefully.

Usage:
    python scripts/seed_tools.py

Environment:
    API_URL        - Base URL of the backoffice API (default: http://localhost:8000)
    ADMIN_PASSWORD - Admin login password (default: changeme)
"""

from __future__ import annotations

import os
import sys

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

TOOLS: list[dict] = [
    {
        "tool_key": "clickup_create_task",
        "display_name": "Criar Task no ClickUp",
        "description": "Cria uma nova task no ClickUp com titulo, descricao, assignees e tags.",
        "category": "clickup",
    },
    {
        "tool_key": "clickup_update_task",
        "display_name": "Atualizar Task no ClickUp",
        "description": "Atualiza status, assignees ou campos de uma task existente.",
        "category": "clickup",
    },
    {
        "tool_key": "clickup_get_task",
        "display_name": "Consultar Task no ClickUp",
        "description": "Busca detalhes de uma task pelo ID, incluindo status e comentarios.",
        "category": "clickup",
    },
    {
        "tool_key": "clickup_add_comment",
        "display_name": "Comentar em Task",
        "description": "Adiciona um comentario a uma task no ClickUp.",
        "category": "clickup",
    },
    {
        "tool_key": "telegram_send_message",
        "display_name": "Enviar Mensagem Telegram",
        "description": "Envia uma mensagem para um chat ou grupo no Telegram.",
        "category": "telegram",
    },
    {
        "tool_key": "search_web",
        "display_name": "Busca na Web",
        "description": "Realiza buscas na internet para obter informacoes atualizadas.",
        "category": "pesquisa",
    },
    {
        "tool_key": "load_brand_guidelines",
        "display_name": "Carregar Diretrizes de Marca",
        "description": "Carrega as diretrizes de marca do cliente para orientar a revisao de conteudo.",
        "category": "conhecimento",
    },
]


def login(client: httpx.Client) -> str:
    """Authenticate and return the JWT token."""
    response = client.post(
        f"{API_URL}/api/admin/auth/login",
        json={"password": ADMIN_PASSWORD},
    )
    if response.status_code != 200:
        print(f"[FAIL] Login failed: {response.status_code} - {response.text}")
        sys.exit(1)

    token = response.json()["token"]
    print(f"[OK]   Authenticated with {API_URL}")
    return token


def seed_tool(client: httpx.Client, headers: dict, tool: dict) -> str:
    """POST a single tool to the registry.

    Returns: "added", "skipped", or "failed".
    """
    response = client.post(
        f"{API_URL}/api/admin/tools",
        json=tool,
        headers=headers,
    )

    key = tool["tool_key"]

    if response.status_code == 201:
        print(f"  [ADD]  {key} - {tool['display_name']}")
        return "added"

    if response.status_code == 409:
        print(f"  [SKIP] {key} - already exists")
        return "skipped"

    print(f"  [FAIL] {key} - {response.status_code}: {response.text}")
    return "failed"


def main() -> None:
    print(f"Seeding tools into {API_URL}\n")

    with httpx.Client(timeout=30.0) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}

        print()
        counts = {"added": 0, "skipped": 0, "failed": 0}

        for tool in TOOLS:
            result = seed_tool(client, headers, tool)
            counts[result] += 1

        print(
            f"\nDone! {counts['added']} added, "
            f"{counts['skipped']} skipped, "
            f"{counts['failed']} failed."
        )

    if counts["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
