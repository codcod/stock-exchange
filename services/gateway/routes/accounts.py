"""Account registration, retrieval, and notification endpoints."""

import typing as tp

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.gateway.auth import require_api_key
from services.gateway.dependencies import ServiceClients, get_clients
from services.gateway.schemas import (
    AccountResponse,
    OrderResponse,
    RegisterAccountRequest,
    account_to_response,
    order_to_response,
)
from shared.domain.models import Account

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post('', response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def register_account(
    req: RegisterAccountRequest, clients: ServiceClients = Depends(get_clients)
):
    """Register a new trading account."""
    account = Account(
        account_id=req.account_id, name=req.name, cash_balance=req.cash_balance
    )
    account.positions = dict(req.positions)
    await clients.account.register_account(account)
    return account_to_response(account)


@router.get('/{account_id}', response_model=AccountResponse)
async def get_account(account_id: str, clients: ServiceClients = Depends(get_clients)):
    """Retrieve account details, including cash, positions, and reservations."""
    account = await clients.account.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return account_to_response(account)


@router.get('/{account_id}/orders', response_model=tp.List[OrderResponse])
async def list_orders(account_id: str, clients: ServiceClients = Depends(get_clients)):
    """List all historical and open orders for a specific account."""
    orders = await clients.oms.get_orders_for_account(account_id)
    return [order_to_response(o) for o in orders]


@router.get('/{account_id}/notifications')
async def get_notifications(
    account_id: str,
    since: tp.Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    clients: ServiceClients = Depends(get_clients),
) -> tp.List[dict]:
    """Return recent notifications for an account."""
    return await clients.notifications.get_notifications(
        account_id, since=since, limit=limit
    )
