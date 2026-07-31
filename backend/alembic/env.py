import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
# Use the async engine creator from SQLAlchemy
from sqlalchemy.ext.asyncio import create_async_engine

# ==============================================================================
# 1. IMPORT YOUR BASE & MODELS HERE
# ==============================================================================
# Alembic needs these imports to populate Base.metadata. If you miss a model here,
# autogenerate will think the table was deleted and try to drop it!
from app.config import settings
from app.database import Base
# Importing the package runs app/models/__init__.py, which imports every model
# and therefore fully populates Base.metadata. Listing them explicitly keeps
# autogenerate honest: a model missing from metadata looks like a dropped table.
from app.models import (  # noqa: F401 - imported for their side effect on Base.metadata
    AdminSession,
    AdminUser,
    Announcement,
    LoginAttempt,
    Match,
    MatchGame,
    MatchPokemon,
    Player,
    Season,
    SeasonEntry,
    SeasonRosterPokemon,
    SiteLinks,
)

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# NOTE: deliberately NOT config.set_main_option("sqlalchemy.url", ...).
# That routes the value through configparser interpolation, so a '%' in a
# URL-encoded password raises ValueError - and the exception message contains
# the full URL, printing the password into the logs. The engine is built
# directly from settings instead.

# Provide Alembic access to your models' metadata
target_metadata = Base.metadata

def do_run_migrations(connection):
    """The standard synchronous migration runner."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """Run migrations in 'online' mode using an async engine."""
    
    # Built straight from settings, so the URL never passes through
    # configparser and the password cannot end up in an interpolation error.
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)

    # Establish an async connection, then use run_sync to execute
    # our synchronous migration function inside the async context.
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_offline():
    """Run migrations in 'offline' mode (e.g., generating SQL scripts)."""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# Determine if we are running offline or online
if context.is_offline_mode():
    run_migrations_offline()
else:
    # Trigger the async event loop to run online migrations
    asyncio.run(run_migrations_online())