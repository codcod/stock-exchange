from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.gateway.auth import require_api_key
from services.gateway.dependencies import ServiceClients, get_clients
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
    req: SubmitOrderRequest, clients: ServiceClients = Depends(get_clients)
):
    order = Order(
        account_id=req.account_id,
        ticker=req.ticker,
        side=req.side,
        order_type=req.order_type,
        quantity=req.quantity,
        price=req.price,
    )
    return order_to_response(await clients.oms.submit_order(order))


@router.get('/{order_id}', response_model=OrderResponse)
async def get_order(order_id: str, clients: ServiceClients = Depends(get_clients)):
    order = await clients.oms.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return order_to_response(order)


@router.delete('/{order_id}', response_model=CancelledResponse)
async def cancel_order(
    order_id: str,
    account_id: str = Query(...),
    clients: ServiceClients = Depends(get_clients),
):
    return CancelledResponse(
        cancelled=await clients.oms.cancel_order(order_id, account_id)
    )
