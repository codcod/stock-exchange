"""Instrument registration endpoint."""

from fastapi import APIRouter, Depends, status

from services.gateway.auth import require_api_key
from services.gateway.dependencies import ServiceClients, get_clients
from services.gateway.schemas import RegisterInstrumentRequest
from shared.models.domain import Instrument

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post('', status_code=status.HTTP_201_CREATED)
async def register_instrument(
    req: RegisterInstrumentRequest, clients: ServiceClients = Depends(get_clients)
):
    """Register a new tradeable instrument."""
    instrument = Instrument(
        ticker=req.ticker,
        name=req.name,
        lot_size=req.lot_size,
        max_order_size=req.max_order_size,
        last_price=req.last_price,
    )
    await clients.risk.register_instrument(instrument)
    return {'ticker': instrument.ticker, 'name': instrument.name}
