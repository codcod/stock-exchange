"""
shared/platform/db/tables.py

DDL helper — creates schemas and tables for one service at startup.
Each service calls this with its own MetaData and schema list.
"""

from sqlalchemy import text
from sqlalchemy.schema import CreateTable

# Arbitrary fixed lock ID — serialises DDL across all services at startup.
_DDL_LOCK_ID = 20260516


async def ensure_tables(engine, metadata, schemas) -> None:
    """
    Create the given schemas and tables if they do not already exist.

    Uses a PostgreSQL advisory lock so concurrent service startups don't
    race on DDL. `IF NOT EXISTS` makes the operation idempotent.
    """
    async with engine.begin() as conn:
        await conn.execute(text(f'SELECT pg_advisory_xact_lock({_DDL_LOCK_ID})'))
        for schema in schemas:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
        for table in metadata.sorted_tables:
            await conn.execute(CreateTable(table, if_not_exists=True))
