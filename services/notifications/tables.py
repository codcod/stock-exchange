"""Table definitions for the Notifications service."""

from base.db.tables import ensure_tables as _ensure_tables
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text

metadata = MetaData()
_SCHEMAS = ('notifications',)

notifications = Table(
    'notifications',
    metadata,
    Column('notification_id', String, primary_key=True),
    Column('account_id', String, nullable=False),
    Column('event_type', String, nullable=False),
    Column('payload', Text, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    schema='notifications',
)


async def ensure_tables(engine) -> None:
    await _ensure_tables(engine, metadata, _SCHEMAS)
