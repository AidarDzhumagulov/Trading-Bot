from fastapi import APIRouter, HTTPException

from app.presentation.schemas.user import BalanceResponse, BalanceCheckRequest
from app.shared.clients import BinanceClient

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/balance/", response_model=BalanceResponse)
async def get_binance_balance(data: BalanceCheckRequest):
    try:
        async with BinanceClient.create(data.api_key, data.api_secret) as client:
            balance = await client.get_balance()
            usdt_info = balance.get("USDT", {})

            return BalanceResponse(
                free_usdt=usdt_info.get("free", 0.0),
                total_usdt=usdt_info.get("total", 0.0),
            )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Binance API Error: {str(e)}")
