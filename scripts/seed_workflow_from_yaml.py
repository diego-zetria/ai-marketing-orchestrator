#!/usr/bin/env python3
"""Seed workflow_definitions, automation_rules, and telegram_topics from YAML + comment_patterns.

Idempotent: upserts by ``name`` field. Safe to re-run.

Usage:
    python -m scripts.seed_workflow_from_yaml
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.workflow_models import AutomationRule, TelegramTopic, WorkflowDefinition  # noqa: E402

# Default statuses from ClickUp workspace
DEFAULT_STATUSES = [
    "ativar",
    "planejamento",
    "desenvolvimento",
    "em criacao",
    "revisao",
    "alteracao",
    "aprovado",
    "pronto",
]

# Transitions derived from auto_status + notification_rules in rules.yaml
DEFAULT_TRANSITIONS: dict[str, list[dict]] = {
    "ativar": [{"to": "planejamento", "roles": ["account", "admin"], "label": "Iniciar Planejamento"}],
    "planejamento": [{"to": "desenvolvimento", "roles": ["account", "admin"], "label": "Iniciar Desenvolvimento"}],
    "desenvolvimento": [{"to": "em criacao", "roles": ["designer", "admin"], "label": "Iniciar Criacao"}],
    "em criacao": [{"to": "revisao", "roles": ["designer", "admin"], "label": "Enviar para Revisao"}],
    "revisao": [
        {"to": "aprovado", "roles": ["strategy_reviewer", "content_reviewer", "admin"], "label": "Aprovar"},
        {"to": "alteracao", "roles": ["strategy_reviewer", "content_reviewer", "admin"], "label": "Solicitar Alteracao"},
    ],
    "alteracao": [{"to": "revisao", "roles": ["designer", "admin"], "label": "Reenviar para Revisao"}],
    "aprovado": [{"to": "pronto", "roles": ["account", "admin"], "label": "Finalizar"}],
}

DEFAULT_TRANSITION_ACTIONS: dict[str, dict] = {
    "em criacao->revisao": {"notify": True},
    "revisao->aprovado": {"notify": True},
    "revisao->alteracao": {"notify": True},
    "aprovado->pronto": {"notify": True},
}

# Automation rules derived from comment_patterns.py
AUTOMATION_RULES = [
    {
        "name": "client_approval",
        "display_name": "Aprovacao do Cliente",
        "intent_type": "client_approval",
        "patterns": [
            r"\baprova[cç][aã]o do cliente\b",
            r"\benviar para (?:o )?cliente\b",
            r"\bmandar para (?:o )?cliente\b",
            r"\bsegue para (?:o )?cliente\b",
            r"\bcliente aprovar\b",
            r"\bencaminhar para (?:o )?cliente\b",
            r"\benviar ao cliente\b",
        ],
        "allowed_roles": ["account", "admin"],
        "valid_from_statuses": ["aprovado"],
        "target_status": "",
        "mode": "confirm",
        "special_action": "client_approval",
        "priority": 10,
    },
    {
        "name": "approval",
        "display_name": "Aprovacao Interna",
        "intent_type": "approval",
        "patterns": [
            r"\baprovado\b",
            r"\bpor mim okk?\b",
            r"\btudo aprovado\b",
            r"\bamassou\b",
            r"\baprovo\b",
        ],
        "allowed_roles": ["strategy_reviewer", "content_reviewer", "admin"],
        "valid_from_statuses": ["revisao"],
        "target_status": "aprovado",
        "mode": "confirm",
        "special_action": None,
        "priority": 20,
    },
    {
        "name": "delivery",
        "display_name": "Entrega para Revisao",
        "intent_type": "delivery",
        "patterns": [
            r"\bsegue para aprova[cç][aã]o\b",
            r"\bfinalizado\b",
            r"\bcaptado\b",
            r"\bentrega finalizada\b",
        ],
        "allowed_roles": ["designer", "admin"],
        "valid_from_statuses": ["em criacao", "alteracao"],
        "target_status": "revisao",
        "mode": "confirm",
        "special_action": None,
        "priority": 30,
    },
    {
        "name": "alteration_done",
        "display_name": "Alteracao Concluida",
        "intent_type": "alteration_done",
        "patterns": [
            r"\balterado\b",
            r"\baltera[cç][aã]o feita\b",
            r"\batualizei\b",
            r"\bajustado\b",
            r"\bcorrigido\b",
        ],
        "allowed_roles": ["designer", "admin"],
        "valid_from_statuses": ["alteracao"],
        "target_status": "revisao",
        "mode": "confirm",
        "special_action": None,
        "priority": 40,
    },
]


async def seed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Workflow Definition (default)
        result = await session.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.name == "default")
        )
        wf = result.scalar_one_or_none()
        if wf is None:
            wf = WorkflowDefinition(
                name="default",
                display_name="Fluxo Padrao",
                description="Fluxo padrao de producao da agencia Agency",
                statuses=DEFAULT_STATUSES,
                transitions=DEFAULT_TRANSITIONS,
                transition_actions=DEFAULT_TRANSITION_ACTIONS,
                is_default=True,
            )
            session.add(wf)
            print("  Created workflow: default")
        else:
            wf.statuses = DEFAULT_STATUSES
            wf.transitions = DEFAULT_TRANSITIONS
            wf.transition_actions = DEFAULT_TRANSITION_ACTIONS
            print("  Updated workflow: default")

        await session.flush()

        # 2. Automation Rules
        for rule_data in AUTOMATION_RULES:
            result = await session.execute(
                select(AutomationRule).where(AutomationRule.name == rule_data["name"])
            )
            rule = result.scalar_one_or_none()
            if rule is None:
                rule = AutomationRule(**rule_data)
                session.add(rule)
                print(f"  Created automation rule: {rule_data['name']}")
            else:
                for key, value in rule_data.items():
                    if key != "name":
                        setattr(rule, key, value)
                print(f"  Updated automation rule: {rule_data['name']}")

        # 3. Telegram Topics from rules.yaml
        rules_path = ROOT / "config" / "rules.yaml"
        if rules_path.exists():
            with open(rules_path) as f:
                yaml_config = yaml.safe_load(f)

            topics = yaml_config.get("telegram_topics", {})
            for topic_name, topic_data in topics.items():
                result = await session.execute(
                    select(TelegramTopic).where(TelegramTopic.name == topic_name)
                )
                topic = result.scalar_one_or_none()
                if topic is None:
                    topic = TelegramTopic(
                        name=topic_name,
                        label=topic_data.get("label", topic_name),
                        topic_id=topic_data.get("topic_id", 0),
                    )
                    session.add(topic)
                    print(f"  Created telegram topic: {topic_name}")
                else:
                    topic.label = topic_data.get("label", topic_name)
                    topic.topic_id = topic_data.get("topic_id", 0)
                    print(f"  Updated telegram topic: {topic_name}")

        await session.commit()
        print("\nSeed complete.")

    await engine.dispose()


def main() -> None:
    import os

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/marketing_bot",
    )
    print(f"Seeding workflow data to: {database_url.split('@')[-1]}")
    asyncio.run(seed(database_url))


if __name__ == "__main__":
    main()
