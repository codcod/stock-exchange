import os
from logging.config import fileConfig

from alembic import context
from base.db.migrations import run_migrations_online
from risk_engine.tables import metadata as target_metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if context.is_offline_mode():
    context.configure(
        url=os.environ['DATABASE_URL'],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        version_table_schema=target_metadata.schema,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online(target_metadata)
