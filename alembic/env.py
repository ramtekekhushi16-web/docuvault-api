import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

from app.db.session import Base

# Import all models so Alembic can detect them
from app.models.user import User
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.permission import DocumentPermission
from app.models.share_link import ShareLink
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken


# Load environment variables from .env, if available
load_dotenv()

# Alembic Config object
config = context.config

# Use DATABASE_URL from the environment when provided
database_url = os.getenv("DATABASE_URL")

if database_url:
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )


# Configure Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Metadata used for migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

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
    """Run migrations using a live database connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()