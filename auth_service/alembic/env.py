"""
Alembic Environment — Auth Service
====================================
Reads DATABASE_URL_SYNC from environment (never from alembic.ini directly).
Uses the synchronous psycopg2 DSN because Alembic does not support asyncpg.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the ORM models so Alembic can detect schema changes
from app.infrastructure.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the environment variable (Rule R6: no hardcoded URLs)
database_url_sync = os.environ.get("DATABASE_URL_SYNC")
if not database_url_sync:
    raise RuntimeError("DATABASE_URL_SYNC environment variable is not set. Copy .env.example to .env and fill in the value.")
config.set_main_option("sqlalchemy.url", database_url_sync)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # 💥 Si Alembic intenta borrar o alterar tablas que no sean 'users', lo ignoramos
    if type_ == "table" and name not in ["users", "alembic_version_auth"]:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version_auth",
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
