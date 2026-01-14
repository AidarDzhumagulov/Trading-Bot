from contextlib import asynccontextmanager
from typing import Optional, Literal

import ccxt.pro as ccxtpro

from app.core.config import settings
from app.core.logging import logger


class BinanceWebSocketClient:
    """
    WebSocket client for Binance API (real-time data).

    Uses ccxt.pro for:
    - Order updates (watch_orders)
    - Price updates (watch_ticker)
    - Also supports REST operations for order management

    Usage:
        async with BinanceWebSocketClient.create(key, secret) as client:
            while running:
                orders = await client.watch_orders("ETH/USDT")
                process(orders)
    """

    def __init__(self, api_key: str, api_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret
        self._exchange: Optional[ccxtpro.binance] = None
        self._markets_loaded = False

    @classmethod
    @asynccontextmanager
    async def create(cls, api_key: str, api_secret: str):
        """Factory method with automatic resource cleanup"""
        client = cls(api_key, api_secret)
        await client.connect()
        try:
            yield client
        finally:
            await client.close()

    async def connect(self):
        """Initialize WebSocket connection"""
        self._exchange = ccxtpro.binance(
            {
                "apiKey": self._api_key,
                "secret": self._api_secret,
                "enableRateLimit": True,
            }
        )

        if settings.ENVIRONMENT == "DEV":
            self._exchange.set_sandbox_mode(True)
            logger.debug("Binance WS client: sandbox mode enabled")

    async def close(self):
        """Close WebSocket connection"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None

    @property
    def exchange(self) -> ccxtpro.binance:
        """Raw exchange access for compatibility"""
        self._ensure_connected()
        return self._exchange

    @property
    def is_connected(self) -> bool:
        return self._exchange is not None

    def _ensure_connected(self):
        """Check that client is connected"""
        if not self._exchange:
            raise RuntimeError("Client not connected. Call connect() first.")

    async def _ensure_markets(self):
        """Load markets if not loaded"""
        if not self._markets_loaded and self._exchange:
            await self._exchange.load_markets()
            self._markets_loaded = True

    async def watch_orders(self, symbol: str) -> list:
        """
        Watch for order updates.

        Returns list of updated orders each time.
        Call in a loop to continuously receive updates.
        """
        self._ensure_connected()
        return await self._exchange.watch_orders(symbol)

    async def watch_ticker(self, symbol: str) -> dict:
        """
        Watch for price updates.

        Returns ticker dict with 'last', 'bid', 'ask', etc.
        Call in a loop to continuously receive updates.
        """
        self._ensure_connected()
        return await self._exchange.watch_ticker(symbol)

    async def get_free_balance(self, asset: str) -> float:
        """Get free balance for specific asset"""
        self._ensure_connected()
        balance = await self._exchange.fetch_free_balance()
        return float(balance.get(asset, 0.0))

    async def get_full_balance(self) -> dict:
        """Get full balance info"""
        self._ensure_connected()
        return await self._exchange.fetch_free_balance()

    async def create_limit_order(
        self, symbol: str, side: Literal["buy", "sell"], amount: float, price: float
    ) -> dict:
        """Create limit order"""
        self._ensure_connected()
        logger.info(
            f"[BinanceWS] Создание {side} limit ордера: " f"{amount} {symbol} @ {price}"
        )
        return await self._exchange.create_order(
            symbol=symbol,
            type="limit",
            side=side,
            amount=amount,
            price=price,
        )

    async def create_market_order(
        self, symbol: str, side: Literal["buy", "sell"], amount: float
    ) -> dict:
        """Create market order"""
        self._ensure_connected()
        logger.info(f"[BinanceWS] Создание {side} market ордера: {amount} {symbol}")
        return await self._exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=amount,
        )

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel order by ID"""
        self._ensure_connected()
        logger.info(f"[BinanceWS] Отмена ордера {order_id}")
        return await self._exchange.cancel_order(order_id, symbol)

    async def get_order(self, order_id: str, symbol: str) -> dict:
        """Get order by ID"""
        self._ensure_connected()
        return await self._exchange.fetch_order(order_id, symbol)

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "5m", limit: int = 15
    ) -> list:
        """Get OHLCV candles"""
        self._ensure_connected()
        return await self._exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, limit=limit
        )

    async def get_market(self, symbol: str) -> dict:
        """Get market info"""
        self._ensure_connected()
        await self._ensure_markets()
        return self._exchange.market(symbol)

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """Format amount to exchange precision"""
        self._ensure_connected()
        return self._exchange.amount_to_precision(symbol, amount)

    def price_to_precision(self, symbol: str, price: float) -> str:
        """Format price to exchange precision"""
        self._ensure_connected()
        return self._exchange.price_to_precision(symbol, price)
