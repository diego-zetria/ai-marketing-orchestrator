#!/usr/bin/env python3
"""Setup Instagram Graph API token for a client.

Usage:
    python scripts/setup_instagram_token.py --client client_alpha

Requires META_APP_ID and META_APP_SECRET in .env file.
"""

import argparse
import asyncio
import logging
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
from sqlalchemy import text

# Add project root to path so 'src' is importable regardless of cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import Settings  # noqa: E402
from src.db.session import create_session_factory  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v21.0"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPES = "pages_show_list,instagram_basic,instagram_manage_insights,pages_read_engagement"

# Global to capture OAuth code from callback handler
_auth_code: str | None = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth redirect and capture the auth code."""

    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Autorizacao concluida! Pode fechar esta aba.</h1>")
        else:
            error = params.get("error_description", ["Unknown error"])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<h1>Erro: {error}</h1>".encode())

    def log_message(self, format, *args):
        """Suppress default HTTP request logs."""


def start_oauth_flow(app_id: str) -> str:
    """Open browser for Facebook Login and capture the auth code via local redirect."""
    global _auth_code
    _auth_code = None

    auth_url = (
        f"https://www.facebook.com/v21.0/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={SCOPES}"
        f"&response_type=code"
    )

    server = HTTPServer(("localhost", 8765), OAuthCallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("\nAbrindo navegador para autorizacao...")
    print(f"Se nao abrir automaticamente, acesse:\n{auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)
    server.server_close()

    if not _auth_code:
        raise RuntimeError("Nao recebeu codigo de autorizacao. Tente novamente.")

    return _auth_code


async def exchange_tokens(app_id: str, app_secret: str, code: str) -> dict:
    """Exchange OAuth code for long-lived token, then resolve IG Business Account."""
    async with httpx.AsyncClient() as client:
        # 1. Exchange code for short-lived token
        resp = await client.get(
            f"{GRAPH_URL}/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )
        resp.raise_for_status()
        short_token = resp.json()["access_token"]
        print("Short-lived token obtido.")

        # 2. Exchange for long-lived token (60 days)
        resp = await client.get(
            f"{GRAPH_URL}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
        )
        resp.raise_for_status()
        long_data = resp.json()
        long_token = long_data["access_token"]
        expires_in = long_data.get("expires_in", 5184000)  # default 60 days
        print(f"Long-lived token obtido (expira em {expires_in // 86400} dias).")

        # 3. Get Facebook Pages linked to this user
        resp = await client.get(
            f"{GRAPH_URL}/me/accounts",
            params={"access_token": long_token},
        )
        resp.raise_for_status()
        pages = resp.json().get("data", [])

        if not pages:
            raise RuntimeError(
                "Nenhuma Facebook Page encontrada. A conta precisa ter uma Page."
            )

        # Let user pick if multiple pages
        if len(pages) == 1:
            page = pages[0]
        else:
            print("\nFacebook Pages encontradas:")
            for i, p in enumerate(pages, 1):
                print(f"  {i}. {p['name']} (ID: {p['id']})")
            choice = int(input("Escolha a Page (numero): ")) - 1
            page = pages[choice]

        page_id = page["id"]
        page_token = page["access_token"]
        print(f"Page selecionada: {page['name']} (ID: {page_id})")

        # 4. Get Instagram Business Account linked to the Page
        resp = await client.get(
            f"{GRAPH_URL}/{page_id}",
            params={
                "fields": "instagram_business_account",
                "access_token": page_token,
            },
        )
        resp.raise_for_status()
        ig_data = resp.json().get("instagram_business_account")

        if not ig_data:
            raise RuntimeError(
                f"Page '{page['name']}' nao tem uma conta Instagram Business vinculada."
            )

        ig_user_id = ig_data["id"]

        # 5. Get IG username for confirmation
        resp = await client.get(
            f"{GRAPH_URL}/{ig_user_id}",
            params={
                "fields": "username",
                "access_token": long_token,
            },
        )
        resp.raise_for_status()
        ig_username = resp.json().get("username", "")
        print(f"Instagram Business Account: @{ig_username} (ID: {ig_user_id})")

        return {
            "access_token": long_token,
            "expires_in": expires_in,
            "page_id": page_id,
            "ig_user_id": ig_user_id,
            "ig_username": ig_username,
        }


async def save_to_db(
    session_factory,
    client_name: str,
    token_data: dict,
) -> None:
    """Save or update Instagram account credentials in database."""
    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        seconds=token_data["expires_in"]
    )
    async with session_factory() as session:
        await session.execute(
            text("""
                INSERT INTO marketing_bot.instagram_accounts
                    (client_name, ig_user_id, ig_username, access_token,
                     token_expires_at, page_id)
                VALUES (:client_name, :ig_user_id, :ig_username, :access_token,
                        :token_expires_at, :page_id)
                ON CONFLICT (client_name) DO UPDATE SET
                    ig_user_id = EXCLUDED.ig_user_id,
                    ig_username = EXCLUDED.ig_username,
                    access_token = EXCLUDED.access_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    page_id = EXCLUDED.page_id,
                    updated_at = NOW()
            """),
            {
                "client_name": client_name,
                "ig_user_id": token_data["ig_user_id"],
                "ig_username": token_data["ig_username"],
                "access_token": token_data["access_token"],
                "token_expires_at": expires_at,
                "page_id": token_data["page_id"],
            },
        )
        await session.commit()
    print(f"\nSalvo no banco de dados para cliente '{client_name}'.")
    print(f"Token expira em: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}")


async def main():
    parser = argparse.ArgumentParser(
        description="Setup Instagram Graph API token for a client"
    )
    parser.add_argument(
        "--client", required=True, help="Client name (e.g., ClientDelta, ClientAlpha)"
    )
    args = parser.parse_args()

    settings = Settings()

    if not settings.meta_app_id or not settings.meta_app_secret:
        print("ERROR: META_APP_ID e META_APP_SECRET devem estar no .env")
        sys.exit(1)

    print(f"=== Setup Instagram Token para {args.client} ===\n")

    # Step 1: OAuth flow (browser + local HTTP callback)
    code = start_oauth_flow(settings.meta_app_id)

    # Step 2: Exchange code for long-lived token + resolve IG account
    token_data = await exchange_tokens(
        settings.meta_app_id,
        settings.meta_app_secret,
        code,
    )

    # Step 3: Persist to database
    session_factory = create_session_factory(settings.database_url)
    await save_to_db(session_factory, args.client, token_data)

    print(f"\nPronto! Conta @{token_data['ig_username']} conectada para {args.client}.")
    print("O bot vai sincronizar automaticamente nos proximos ciclos.")


if __name__ == "__main__":
    asyncio.run(main())
