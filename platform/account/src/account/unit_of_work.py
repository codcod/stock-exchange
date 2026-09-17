"""Unit of work for the Account service."""

from __future__ import annotations

import typing as tp
from typing import Self

from base.unit_of_work import SqlAlchemyUnitOfWork

from account.repository import AccountRepository


class AccountUnitOfWork(SqlAlchemyUnitOfWork):
    accounts: AccountRepository

    @tp.override
    async def __aenter__(self) -> Self:
        _ = await super().__aenter__()
        self.accounts = AccountRepository(self.connection)
        return self
