"""Instrument registration endpoint."""

from base.domain.models import Instrument
from fastapi import APIRouter, Depends, status

from gateway.auth import require_api_key
from gateway.dependencies import ServiceClients, get_clients
from gateway.schemas import RegisterInstrumentRequest

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
