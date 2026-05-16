from fastapi import APIRouter, Depends, HTTPException, Query, status

from exchange.main import Exchange
from services.gateway.auth import require_api_key
from services.gateway.dependencies import get_exchange
from services.gateway.schemas import (
    CancelledResponse,
    OrderResponse,
    SubmitOrderRequest,
    order_to_response,
)
from shared.models.domain import Order

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post('', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def submit_order(
    req: SubmitOrderRequest, exchange: Exchange = Depends(get_exchange)
):
    order = Order(
        account_id=req.account_id,
        ticker=req.ticker,
        side=req.side,
        order_type=req.order_type,
        quantity=req.quantity,
        price=req.price,
    )
    return order_to_response(await exchange.submit_order(order))


@router.get('/{order_id}', response_model=OrderResponse)
async def get_order(order_id: str, exchange: Exchange = Depends(get_exchange)):
    order = exchange.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return order_to_response(order)


@router.delete('/{order_id}', response_model=CancelledResponse)
async def cancel_order(
    order_id: str,
    account_id: str = Query(...),
    exchange: Exchange = Depends(get_exchange),
):
    return CancelledResponse(
        cancelled=await exchange.cancel_order(order_id, account_id)
    )
