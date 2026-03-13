import asyncio
import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Load .env so DATABASE_URL is always available without manual export
load_dotenv()

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.models import Base
import src.db.admin_models  # noqa: F401 — register admin tables for autogenerate

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with DATABASE_URL env var if set
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="marketing_bot",
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """Only manage objects in the marketing_bot schema; ignore public schema."""
    if type_ == "table" and hasattr(object, "schema"):
        return object.schema == "marketing_bot"
    if type_ == "table" and not hasattr(object, "schema"):
        # Reflected tables from public schema — skip them
        return False
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="marketing_bot",
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
