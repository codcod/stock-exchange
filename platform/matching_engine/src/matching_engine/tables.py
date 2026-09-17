"""Table definitions for the Matching Engine service."""

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text

metadata = MetaData(schema='matching_engine')

outbox = Table(
    'outbox',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('event_id', String, nullable=False),
    Column('event_type', String, nullable=False),
    Column('destination', String, nullable=False),
    Column('payload', Text, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('published_at', DateTime(timezone=True), nullable=True),
    schema='matching_engine',
)
