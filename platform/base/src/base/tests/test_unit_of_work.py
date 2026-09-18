"""
Tests for SqlAlchemyUnitOfWork's own commit/rollback state machine.

Drives the real __aenter__/commit/__aexit__ path via fake AsyncEngine/
AsyncConnection/AsyncTransaction doubles, rather than through the
Fake*UnitOfWork(AbstractUnitOfWork) doubles services use, which bypass
SqlAlchemyUnitOfWork entirely.
"""

import pytest

from base.unit_of_work import SqlAlchemyUnitOfWork


class FakeTransaction:
    def __init__(self) -> None:
        self.committed = False
        self.rollback_calls = 0

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rollback_calls += 1


class FakeConnection:
    def __init__(self) -> None:
        self.transaction = FakeTransaction()
        self.closed = False

    async def begin(self) -> FakeTransaction:
        return self.transaction

    async def close(self) -> None:
        self.closed = True


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    async def connect(self) -> FakeConnection:
        return self.connection


async def test_commit_then_normal_exit_does_not_roll_back():
    engine = FakeEngine()
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.commit()

    transaction = engine.connection.transaction
    assert transaction.committed is True
    assert transaction.rollback_calls == 0
    assert engine.connection.closed is True


async def test_exit_without_commit_rolls_back():
    engine = FakeEngine()
    async with SqlAlchemyUnitOfWork(engine):
        pass

    transaction = engine.connection.transaction
    assert transaction.committed is False
    assert transaction.rollback_calls == 1


async def test_exit_via_exception_rolls_back():
    engine = FakeEngine()
    with pytest.raises(ValueError):
        async with SqlAlchemyUnitOfWork(engine):
            raise ValueError('boom')

    assert engine.connection.transaction.rollback_calls == 1


async def test_rollback_never_called_twice():
    engine = FakeEngine()
    async with SqlAlchemyUnitOfWork(engine) as uow:
        await uow.commit()
        await uow.rollback()

    assert engine.connection.transaction.rollback_calls == 0
