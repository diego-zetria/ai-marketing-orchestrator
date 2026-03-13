"""Seed database tables from config/rules.yaml.

Populates: team_members, clients, assignment_rules, notification_rules.
Idempotent: skips records that already exist (matched by unique key).

Usage:
    python scripts/seed_from_yaml.py

Environment:
    DATABASE_URL - PostgreSQL async connection string
                   default: postgresql+asyncpg://user:password@localhost:5432/marketing_bot
"""

import asyncio
import os
import uuid
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.admin_models import AssignmentRule, Client, NotificationRule
from src.db.models import TeamMember

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/marketing_bot",
)

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def load_rules() -> dict:
    with open(RULES_PATH) as f:
        return yaml.safe_load(f)


async def seed_team_members(session: AsyncSession, rules: dict) -> int:
    """Seed team_members from team_mapping section. Returns count of inserted rows."""
    team_mapping = rules.get("team_mapping", {})
    inserted = 0

    for clickup_id, info in team_mapping.items():
        result = await session.execute(
            select(TeamMember).where(TeamMember.clickup_user_id == str(clickup_id))
        )
        if result.scalar_one_or_none() is not None:
            print(f"  [skip] team_member {info['name']} (clickup_id={clickup_id}) already exists")
            continue

        member = TeamMember(
            id=uuid.uuid4(),
            name=info["name"],
            clickup_user_id=str(clickup_id),
            role=info.get("role"),
            telegram_chat_id=info.get("telegram_chat_id", 0),
            active=True,
        )
        session.add(member)
        inserted += 1
        print(f"  [add]  team_member {info['name']} (clickup_id={clickup_id})")

    return inserted


async def seed_clients(session: AsyncSession, rules: dict) -> int:
    """Seed clients from client_overrides section. Returns count of inserted rows."""
    client_overrides = rules.get("client_overrides", {})
    inserted = 0

    for client_name, info in client_overrides.items():
        result = await session.execute(
            select(Client).where(Client.name == client_name)
        )
        if result.scalar_one_or_none() is not None:
            print(f"  [skip] client {client_name} already exists")
            continue

        # Look up designer and account TeamMember UUIDs by clickup_user_id
        designer_id = None
        if info.get("designer"):
            res = await session.execute(
                select(TeamMember.id).where(TeamMember.clickup_user_id == str(info["designer"]))
            )
            row = res.scalar_one_or_none()
            if row:
                designer_id = row

        account_id = None
        if info.get("account"):
            res = await session.execute(
                select(TeamMember.id).where(TeamMember.clickup_user_id == str(info["account"]))
            )
            row = res.scalar_one_or_none()
            if row:
                account_id = row

        client = Client(
            id=uuid.uuid4(),
            name=client_name,
            display_name=client_name.replace("_", " ").title(),
            clickup_list_id=info.get("list_id"),
            designer_id=designer_id,
            account_id=account_id,
            is_active=True,
        )
        session.add(client)
        inserted += 1
        print(f"  [add]  client {client_name} (list_id={info.get('list_id')})")

    return inserted


async def seed_assignment_rules(session: AsyncSession, rules: dict) -> int:
    """Seed assignment_rules from assignment_rules section. Returns count of inserted rows."""
    assignment_rules = rules.get("assignment_rules", {})
    inserted = 0

    for service_type, info in assignment_rules.items():
        result = await session.execute(
            select(AssignmentRule).where(AssignmentRule.service_type == service_type)
        )
        if result.scalar_one_or_none() is not None:
            print(f"  [skip] assignment_rule {service_type} already exists")
            continue

        rule = AssignmentRule(
            id=uuid.uuid4(),
            service_type=service_type,
            default_assignee_ids=info.get("default_assignees", []),
            tags=info.get("tags", []),
        )
        session.add(rule)
        inserted += 1
        print(f"  [add]  assignment_rule {service_type}")

    return inserted


async def seed_notification_rules(session: AsyncSession, rules: dict) -> int:
    """Seed notification_rules from notification_rules section. Returns count of inserted rows."""
    notification_rules = rules.get("notification_rules", {})
    inserted = 0

    for status, info in notification_rules.items():
        result = await session.execute(
            select(NotificationRule).where(NotificationRule.status == status)
        )
        if result.scalar_one_or_none() is not None:
            print(f"  [skip] notification_rule {status} already exists")
            continue

        rule = NotificationRule(
            id=uuid.uuid4(),
            status=status,
            notify_roles=info.get("notify_roles", []),
            message_template=info.get("message", ""),
            is_active=True,
        )
        session.add(rule)
        inserted += 1
        print(f"  [add]  notification_rule {status}")

    return inserted


async def main():
    print(f"Loading rules from {RULES_PATH}")
    rules = load_rules()

    print(f"Connecting to {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            print("\n--- Seeding team_members ---")
            tm_count = await seed_team_members(session, rules)

            print("\n--- Seeding clients ---")
            cl_count = await seed_clients(session, rules)

            print("\n--- Seeding assignment_rules ---")
            ar_count = await seed_assignment_rules(session, rules)

            print("\n--- Seeding notification_rules ---")
            nr_count = await seed_notification_rules(session, rules)

        print(f"\nDone! Inserted: {tm_count} team_members, {cl_count} clients, "
              f"{ar_count} assignment_rules, {nr_count} notification_rules")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
