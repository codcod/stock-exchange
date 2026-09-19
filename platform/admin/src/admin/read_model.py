"""
Read-only refs into the other services' schemas — admin owns no schema of its
own and never writes through these. Column sets mirror each owning service's
own `tables.py` declaration. There's no shared Table definition across
services (admin only depends on `base`, not on the five owning packages), so
this follows the same per-service-redeclares-its-columns convention as
monolith's `stelo.admin.adapters.read_model` rather than adding a workspace
dependency on order_management/clearing/account/notifications.
"""

import sqlalchemy as sa

orders = sa.table(
    'orders',
    sa.column('order_id'),
    sa.column('account_id'),
    sa.column('ticker'),
    sa.column('side'),
    sa.column('quantity'),
    sa.column('price'),
    sa.column('status'),
    sa.column('filled_quantity'),
    sa.column('created_at'),
    sa.column('updated_at'),
    schema='order_management',
)

order_management_outbox = sa.table(
    'outbox',
    sa.column('published_at'),
    schema='order_management',
)

trades = sa.table(
    'trades',
    sa.column('trade_id'),
    sa.column('ticker'),
    sa.column('buy_order_id'),
    sa.column('sell_order_id'),
    sa.column('quantity'),
    sa.column('price'),
    sa.column('executed_at'),
    schema='clearing',
)

accounts = sa.table(
    'accounts',
    sa.column('account_id'),
    sa.column('cash_balance'),
    sa.column('reserved_cash'),
    schema='account',
)

reserved_shares = sa.table(
    'reserved_shares',
    sa.column('account_id'),
    sa.column('ticker'),
    sa.column('quantity'),
    schema='account',
)

notifications = sa.table(
    'notifications',
    sa.column('notification_id'),
    sa.column('created_at'),
    schema='notifications',
)
