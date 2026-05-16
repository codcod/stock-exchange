from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from exchange.main import Exchange
from services.gateway.auth import require_api_key
from services.gateway.dependencies import get_exchange
from services.gateway.schemas import (
    AccountResponse,
    OrderResponse,
    RegisterAccountRequest,
    account_to_response,
    order_to_response,
)
from shared.models.domain import Account

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post('', response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def register_account(
    req: RegisterAccountRequest, exchange: Exchange = Depends(get_exchange)
):
    account = Account(
        account_id=req.account_id, name=req.name, cash_balance=req.cash_balance
    )
    await exchange.register_account(account)
    return account_to_response(account)


@router.get('/{account_id}', response_model=AccountResponse)
async def get_account(account_id: str, exchange: Exchange = Depends(get_exchange)):
    account = exchange.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return account_to_response(account)


@router.get('/{account_id}/orders', response_model=List[OrderResponse])
async def list_orders(account_id: str, exchange: Exchange = Depends(get_exchange)):
    return [order_to_response(o) for o in exchange.get_orders(account_id)]
