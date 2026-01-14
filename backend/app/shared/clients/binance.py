from contextlib import asynccontextmanager
from typing import Optional, Literal

from ccxt import async_support

from app.core.config import settings
from app.core.logging import logger


class BinanceClient:
    """
    REST client for Binance API.
    
    Handles:
    - Balance queries
    - Price queries
    - Order creation/cancellation
    - Market data
    
    Usage:
        async with BinanceClient.create(api_key, api_secret) as client:
            balance = await client.get_free_usdt()
            price = await client.get_price("ETH/USDT")
    """
    
    def __init__(self, api_key: str, api_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret
        self._exchange: Optional[async_support.binance] = None
        self._markets_loaded = False
    
    @classmethod
    @asynccontextmanager
    async def create(cls, api_key: str, api_secret: str):
        """
        Factory method with automatic resource cleanup.
        
        Usage:
            async with BinanceClient.create(key, secret) as client:
                ...
        """
        client = cls(api_key, api_secret)
        await client.connect()
        try:
            yield client
        finally:
            await client.close()
    
    async def connect(self):
        """Initialize exchange connection"""
        self._exchange = async_support.binance({
            "apiKey": self._api_key,
            "secret": self._api_secret,
            "enableRateLimit": True,
        })
        
        if settings.ENVIRONMENT == "DEV":
            self._exchange.set_sandbox_mode(True)
            logger.debug("Binance client: sandbox mode enabled")
    
    async def close(self):
        """Close exchange connection"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
    
    @property
    def exchange(self) -> async_support.binance:
        """Raw exchange access for TradingUtils compatibility"""
        self._ensure_connected()
        return self._exchange
    
    def _ensure_connected(self):
        """Check that client is connected"""
        if not self._exchange:
            raise RuntimeError("Client not connected. Call connect() first.")
    
    async def _ensure_markets(self):
        """Load markets if not loaded"""
        if not self._markets_loaded and self._exchange:
            await self._exchange.load_markets()
            self._markets_loaded = True
    
    async def get_balance(self) -> dict:
        """Get full balance info"""
        self._ensure_connected()
        return await self._exchange.fetch_balance()
    
    async def get_free_usdt(self) -> float:
        """Get free USDT balance"""
        balance = await self.get_balance()
        usdt_info = balance.get("USDT", {})
        return float(usdt_info.get("free", 0.0))
    
    async def get_total_usdt(self) -> float:
        """Get total USDT balance"""
        balance = await self.get_balance()
        usdt_info = balance.get("USDT", {})
        return float(usdt_info.get("total", 0.0))
    
    async def get_free_balance(self, asset: str) -> float:
        """Get free balance for specific asset"""
        self._ensure_connected()
        balance = await self._exchange.fetch_free_balance()
        return float(balance.get(asset, 0.0))
    
    async def get_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        self._ensure_connected()
        ticker = await self._exchange.fetch_ticker(symbol)
        return float(ticker.get("last", 0.0))
    
    async def get_ticker(self, symbol: str) -> dict:
        """Get full ticker data"""
        self._ensure_connected()
        return await self._exchange.fetch_ticker(symbol)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        amount: float,
        price: float
    ) -> dict:
        """
        Create limit order.
        
        Returns:
            Order response with 'id', 'status', etc.
        """
        self._ensure_connected()
        logger.info(
            f"[BinanceClient] Создание {side} limit ордера: "
            f"{amount} {symbol} @ {price}"
        )
        return await self._exchange.create_order(
            symbol=symbol,
            type="limit",
            side=side,
            amount=amount,
            price=price,
        )
    
    async def create_market_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        amount: float
    ) -> dict:
        """
        Create market order.
        
        Returns:
            Order response with 'id', 'status', 'average', etc.
        """
        self._ensure_connected()
        logger.info(
            f"[BinanceClient] Создание {side} market ордера: {amount} {symbol}"
        )
        return await self._exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=amount,
        )
    
    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel order by ID"""
        self._ensure_connected()
        logger.info(f"[BinanceClient] Отмена ордера {order_id}")
        return await self._exchange.cancel_order(order_id, symbol)
    
    async def get_order(self, order_id: str, symbol: str) -> dict:
        """Get order by ID"""
        self._ensure_connected()
        return await self._exchange.fetch_order(order_id, symbol)
    
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 15
    ) -> list:
        """
        Get OHLCV candles for ATR calculation.
        
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        self._ensure_connected()
        return await self._exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, limit=limit
        )
    
    async def get_market(self, symbol: str) -> dict:
        """Get market info (precision, limits, etc.)"""
        self._ensure_connected()
        await self._ensure_markets()
        return self._exchange.market(symbol)
    
    async def get_amount_precision(self, symbol: str) -> int:
        """Get amount precision for symbol"""
        market = await self.get_market(symbol)
        precision = market.get("precision", {}).get("amount", 8)
        return precision if isinstance(precision, int) else 8
    
    async def get_price_precision(self, symbol: str) -> int:
        """Get price precision for symbol"""
        market = await self.get_market(symbol)
        precision = market.get("precision", {}).get("price", 2)
        return precision if isinstance(precision, int) else 2
    
    async def get_min_notional(self, symbol: str) -> float:
        """Get minimum order value for symbol"""
        market = await self.get_market(symbol)
        return market.get("limits", {}).get("cost", {}).get("min", 0.0)
    
    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """Format amount to exchange precision"""
        self._ensure_connected()
        return self._exchange.amount_to_precision(symbol, amount)
    
    def price_to_precision(self, symbol: str, price: float) -> str:
        """Format price to exchange precision"""
        self._ensure_connected()
        return self._exchange.price_to_precision(symbol, price)
