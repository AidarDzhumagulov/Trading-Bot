import math

from app.core.logging import logger
from app.domain.value_objects import DustResult
from app.shared.exchange_helper import TradingUtils


class DustManager:
    """
    Manages dust (small amounts below precision) accumulation.
    
    Dust occurs when order amount is truncated to match exchange precision.
    Accumulated dust is added to next order to prevent loss.
    """
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.utils = TradingUtils(exchange)
    
    async def process_dust(
        self,
        amount: float,
        accumulated_dust: float,
        symbol: str
    ) -> DustResult:
        """
        Process amount with accumulated dust and calculate sellable quantity.
        
        Args:
            amount: Base amount to sell
            accumulated_dust: Previously accumulated dust
            symbol: Trading pair symbol
            
        Returns:
            DustResult with sellable_amount and new_dust
        """
        total_with_dust = amount + accumulated_dust
        base_asset = symbol.split("/")[0]
        
        logger.info(
            f"[DustManager] Накопление пыли: "
            f"текущее={amount:.8f}, "
            f"накоплено={accumulated_dust:.8f}, "
            f"всего={total_with_dust:.8f} {base_asset}"
        )
        
        market = await self.utils.get_market(symbol)
        amount_precision = market.get("precision", {}).get("amount", 8)
        
        sellable_amount = self._truncate_to_precision(
            total_with_dust, amount_precision, symbol
        )
        
        new_dust = total_with_dust - sellable_amount
        
        logger.info(
            f"[DustManager] После округления: "
            f"sellable={sellable_amount:.8f}, "
            f"new_dust={new_dust:.8f} {base_asset}"
        )
        
        return DustResult(
            sellable_amount=sellable_amount,
            new_dust=new_dust
        )
    
    def _truncate_to_precision(
        self,
        amount: float,
        precision: int | float,
        symbol: str = None
    ) -> float:
        """Truncate amount to exchange precision (always rounds down)"""
        
        if isinstance(precision, int):
            factor = 10 ** precision
            return math.floor(amount * factor) / factor
        
        return float(
            self.exchange.amount_to_precision(symbol or "BTC/USDT", amount)
        )
    
    def get_step_size(self, precision: int | float) -> float:
        """Get minimum step size for amount precision"""
        if isinstance(precision, int):
            return 1.0 / (10 ** precision)
        return 0.0001
