from decimal import Decimal

from app.core.logging import logger
from app.domain.constants import FeeDefaults
from app.domain.value_objects import FeeInfo, FillResult


class FeeCalculator:
    """
    Calculates trading fees from exchange order data.
    
    Handles multiple fee formats:
    - Direct base currency fee
    - Quote currency fee (converted to base)
    - Fallback estimation when fee data unavailable
    """
    
    def __init__(self, exchange):
        self.exchange = exchange
    
    async def calculate_fill_result(
        self,
        binance_order: dict,
        symbol: str,
        order_price: float
    ) -> FillResult:
        """
        Process filled order and calculate net quantity after fees.
        
        Args:
            binance_order: Raw order data from exchange
            symbol: Trading pair symbol
            order_price: Order price from database
            
        Returns:
            FillResult with filled_qty, fee_qty, net_qty, order_cost
        """
        filled_qty = Decimal(str(binance_order["amount"]))
        base_currency = symbol.split("/")[0].upper()
        
        raw_fee = binance_order.get("fee")
        fee_qty = await self._calculate_fee_qty_from_raw(
            raw_fee=raw_fee,
            filled_qty=filled_qty,
            base_currency=base_currency,
            order_price=order_price,
            symbol=symbol
        )
        
        net_qty = filled_qty - fee_qty
        
        order_cost = Decimal(
            str(binance_order.get("cost", order_price * float(filled_qty)))
        )
        
        logger.info(
            f"[FeeCalculator] Исполнено: {filled_qty}, "
            f"комиссия: {fee_qty}, нетто: {net_qty}"
        )
        
        return FillResult(
            filled_qty=filled_qty,
            fee_qty=fee_qty,
            net_qty=net_qty,
            order_cost=order_cost
        )
    
    async def _calculate_fee_qty_from_raw(
        self,
        raw_fee,
        filled_qty: Decimal,
        base_currency: str,
        order_price: float,
        symbol: str
    ) -> Decimal:
        """
        Calculate fee quantity from raw fee data.
        
        Handles:
        - dict format: {"cost": X, "currency": "Y"}
        - numeric format: direct fee value
        - None/empty: estimate from market
        """
        if raw_fee:
            if isinstance(raw_fee, dict):
                fee_info = FeeInfo.from_dict(raw_fee)
                if fee_info and fee_info.cost > 0:
                    return self._convert_fee_to_base(
                        fee_info=fee_info,
                        filled_qty=filled_qty,
                        base_currency=base_currency,
                        order_price=order_price
                    )
            else:
                return Decimal(str(raw_fee))
        
        return await self._estimate_fee_from_market(symbol, filled_qty)
    
    def _convert_fee_to_base(
        self,
        fee_info: FeeInfo,
        filled_qty: Decimal,
        base_currency: str,
        order_price: float
    ) -> Decimal:
        """Convert fee to base currency amount"""
        
        if fee_info.currency == base_currency:
            return fee_info.cost
        
        if fee_info.currency in ("USDT", "USD"):
            if order_price > 0:
                return fee_info.cost / Decimal(str(order_price))
            return Decimal("0")
        
        logger.warning(
            f"Неизвестная валюта комиссии: {fee_info.currency}, "
            f"используем fallback {FeeDefaults.FALLBACK_FEE_RATE * 100}%"
        )
        return filled_qty * FeeDefaults.FALLBACK_FEE_RATE
    
    async def _estimate_fee_from_market(
        self,
        symbol: str,
        filled_qty: Decimal
    ) -> Decimal:
        """Estimate fee from market data or use fallback"""
        try:
            await self.exchange.load_markets()
            market = self.exchange.market(symbol)
            taker_fee = market.get("taker", float(FeeDefaults.FALLBACK_FEE_RATE))
            fee_rate = Decimal(str(taker_fee))
            return filled_qty * fee_rate
        except Exception as e:
            logger.warning(
                f"Не удалось получить комиссию с биржи, "
                f"используем fallback {FeeDefaults.FALLBACK_FEE_RATE * 100}%: {e}"
            )
            return filled_qty * FeeDefaults.FALLBACK_FEE_RATE
    
    def calculate_sell_fee(self, binance_order: dict) -> Decimal:
        """
        Calculate fee for sell order (in quote currency).
        
        Used when closing cycle to calculate actual profit.
        """
        base_cost = Decimal(str(binance_order.get("cost", 0)))
        
        if base_cost == 0:
            price = Decimal(str(binance_order.get("price", 0)))
            amount = Decimal(str(binance_order.get("amount", 0)))
            base_cost = price * amount
        
        fee_info = FeeInfo.from_dict(binance_order.get("fee"))
        
        if fee_info and fee_info.currency in ("USDT", "USD"):
            logger.info(f"Комиссия при продаже с биржи: {fee_info.cost} USDT")
            return fee_info.cost
        
        estimated_fee = base_cost * FeeDefaults.FALLBACK_FEE_RATE
        logger.warning(
            f"Нет информации о комиссии с биржи, "
            f"рассчитано {FeeDefaults.FALLBACK_FEE_RATE * 100}%: {estimated_fee}"
        )
        return estimated_fee
