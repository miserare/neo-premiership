import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
# Use the async engine creator from SQLAlchemy
from sqlalchemy.ext.asyncio import async_engine_from_config

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

# Override the placeholder URL in alembic.ini with the real one from our
# pydantic-settings config, so migrations always target the same database
# the application itself connects to.
config.set_main_option("sqlalchemy.url", settings.database_url)

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
    
    # Read configuration and create the async engine
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Establish an async connection, then use run_sync to execute
    # our synchronous migration function inside the async context.
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_offline():
    """Run migrations in 'offline' mode (e.g., generating SQL scripts)."""
    url = config.get_main_option("sqlalchemy.url")
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