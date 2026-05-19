"""Account registration and retrieval endpoints."""

import typing as tp

from fastapi import APIRouter, Depends, HTTPException, status

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
    # The Clearing service is the authoritative source for account state
    # and notifies the Risk Engine of any updates.
    await clients.clearing.register_account(account)
    return account_to_response(account)


@router.get('/{account_id}', response_model=AccountResponse)
async def get_account(account_id: str, clients: ServiceClients = Depends(get_clients)):
    """Retrieve account details, including cash, positions, and reservations."""
    account = await clients.clearing.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return account_to_response(account)


@router.get('/{account_id}/orders', response_model=tp.List[OrderResponse])
async def list_orders(account_id: str, clients: ServiceClients = Depends(get_clients)):
    """List all historical and open orders for a specific account."""
    orders = await clients.oms.get_orders_for_account(account_id)
    return [order_to_response(o) for o in orders]
