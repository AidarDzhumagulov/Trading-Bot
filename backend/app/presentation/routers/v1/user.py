from ccxt import async_support
from fastapi import APIRouter, HTTPException

from app.presentation.schemas.user import BalanceResponse, BalanceCheckRequest

router = APIRouter(prefix="/user", tags=["user"])

@router.post("/balance/", response_model=BalanceResponse)
async def get_binance_balance(data: BalanceCheckRequest):
    exchange = async_support.binance({
        'apiKey': data.api_key,
        'secret': data.api_secret,
    })

    try:
        # exchange.set_sandbox_mode(True)
        balance = await exchange.fetch_balance()
        usdt_info = balance.get('USDT', {})

        return BalanceResponse(
            free_usdt=usdt_info.get('free', 0.0),
            total_usdt=usdt_info.get('total', 0.0)
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Binance API Error: {str(e)}")
    finally:
        await exchange.close()