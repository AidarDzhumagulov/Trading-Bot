import asyncio
import time
import traceback
import ccxt.pro as ccxtpro
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Callable, TYPE_CHECKING
from uuid import UUID

from app.infrastructure.persistence.sqlalchemy.models import DcaCycle, Order, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.core.logging import logger
from app.core.config import settings

if TYPE_CHECKING:
    from app.domain.order_handler import OrderHandler
    from app.domain.bot_manager import BotManager

price_cache = {}

class BinanceWebsocketManager:
    def __init__(
            self,
            api_key: str,
            api_secret: str,
            session_factory: Callable[[], AsyncSession],
            config_id: UUID,
            symbol: str
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_factory = session_factory
        self.config_id = config_id
        self.symbol = symbol
        self.exchange = None
        self._is_running = False
        self._last_shift_time = None

    async def connect(self):
        self.exchange = ccxtpro.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
        })
        if settings.ENVIRONMENT == "DEV":
            self.exchange.set_sandbox_mode(True)
        self._is_running = True

    async def run_forever(self):
        await self.connect()
        logger.info(f"WebSocket Manager запущен для {self.symbol} (config_id: {self.config_id})...")

        try:
            await asyncio.gather(
                self._watch_orders_loop(),
                self._watch_price_loop(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Критическая ошибка в WebSocket: {e}")

    async def _watch_orders_loop(self):
        logger.info(f"[watch_orders] Начало цикла мониторинга ордеров для {self.symbol}")
        while self._is_running:
            try:
                if not self.exchange:
                    logger.warning(f"[watch_orders] Exchange не инициализирован, переподключение...")
                    await self.connect()
                
                logger.debug(f"[watch_orders] Ожидание обновлений ордеров для {self.symbol}...")
                orders = await self.exchange.watch_orders(self.symbol)
                logger.debug(f"[watch_orders] Получено обновление: {len(orders)} ордеров")
                
                if orders:
                    for order in orders:
                        order_status = order.get('status', '')
                        order_status_lower = order_status.lower()
                        order_id = order.get('id')
                        filled = order.get('filled', 0)
                        amount = order.get('amount', 0)
                        remaining = order.get('remaining', 0)
                        
                        logger.debug(f"[watch_orders] Полный статус ордера {order_id}: status='{order_status}' (lower='{order_status_lower}'), filled={filled}, amount={amount}, remaining={remaining}")
                        logger.debug(f"[watch_orders] Все поля ордера: {list(order.keys())}")
                        
                        if order_status_lower in ['closed', 'filled']:
                            logger.info(f"[watch_orders] Ордер исполнен: {order_id}, статус: {order_status}")
                            await self._process_order_as_trade(order)
                        elif filled > 0 and (filled >= amount * 0.99 or remaining <= amount * 0.01):
                            logger.info(f"[watch_orders] Ордер почти полностью исполнен (filled={filled}, amount={amount}, remaining={remaining}), обрабатываем как filled")
                            await self._process_order_as_trade(order)
                        elif order_status_lower in ['partially_filled', 'partial']:
                            logger.warning(f"[watch_orders] Ордер частично исполнен: {order_id}, filled={filled}, amount={amount}")
                            if filled > 0:
                                logger.info(f"[watch_orders] Обрабатываем частичное исполнение как filled")
                                await self._process_order_as_trade(order)
                        else:
                            logger.debug(f"[watch_orders] Изменение статуса ордера {order_id}: {order_status}")
                else:
                    logger.debug(f"[watch_orders] Пустой список ордеров")
                    
            except Exception as e:
                logger.error(f"Ошибка в цикле watch_orders: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)
                if self._is_running:
                    await self.connect()
    
    async def _process_order_as_trade(self, order: dict):
        from app.domain.order_handler import OrderHandler
        
        order_id = order.get('id')
        if not order_id:
            logger.warning(f"[process_order] Ордер без id. Order data: {order}")
            return
        
        order_id_str = str(order_id)
        logger.info(f"[process_order] Обработка ордера {order_id_str}")
        logger.debug(f"[process_order] Order данные: symbol={order.get('symbol')}, amount={order.get('amount')}, filled={order.get('filled')}, price={order.get('price')}")

        logger.info(f"[process_order] Raw order from exchange:")
        logger.info(f"  filled: {order.get('filled')}")
        logger.info(f"  amount: {order.get('amount')}")
        logger.info(f"  average: {order.get('average')}")
        logger.info(f"  price: {order.get('price')}")
        logger.info(f"  cost: {order.get('cost')}")
        logger.info(f"  fee: {order.get('fee')}")
        
        async with self.session_factory() as session:
            filled_amount = order.get('filled') or order.get('amount')
            avg_price = order.get('average') or order.get('price')

            order_cost = order.get('cost')
            if order_cost is None or order_cost == 0:
                order_cost = filled_amount * avg_price
                logger.warning(f"[process_order] Cost not in order, calculated: {order_cost}")

            binance_order = {
                'id': order_id_str,
                'symbol': order.get('symbol', self.symbol),
                'status': 'closed',
                'amount': filled_amount,
                'price': avg_price,
                'filled': filled_amount,
                'cost': order_cost,
                'fee': order.get('fee', {})
            }

            logger.info(f"[process_order] Prepared binance_order: cost={order_cost}, amount={filled_amount}, price={avg_price}")

            handler = OrderHandler(session, self.exchange)
            await handler.handle_filled_order(binance_order)

    async def _watch_price_loop(self):
        logger.info(f"[watch_price] Начало цикла мониторинга цены для {self.symbol}")
        while self._is_running:
            try:
                if not self.exchange:
                    logger.warning(f"[watch_price] Exchange не инициализирован, переподключение...")
                    await self.connect()
                
                logger.debug(f"[watch_price] Ожидание обновления цены для {self.symbol}...")
                ticker = await self.exchange.watch_ticker(self.symbol)
                current_price = ticker.get('last')
                logger.debug(f"[watch_price] Получена цена: {current_price} для {self.symbol}")
                
                if current_price:
                    price_cache[self.symbol] = current_price
                
                await self._check_grid_shift(ticker)
                    
            except Exception as e:
                logger.error(f"Ошибка в цикле watch_price: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)
                if self._is_running:
                    await self.connect()

    async def _process_order_updates(self, orders: list):
        from app.domain.order_handler import OrderHandler
        
        logger.info(f"[process_orders] Обработка {len(orders)} ордеров")
        
        for order in orders:
            order_status = order.get('status', 'unknown')
            order_id = order.get('id', 'unknown')
            order_symbol = order.get('symbol', 'unknown')
            
            logger.debug(f"[process_orders] Ордер {order_id}: status={order_status}, symbol={order_symbol}")
            
            if order_status == 'closed':
                logger.info(f"Ордер исполнен: {order_id} ({order_symbol})")

                async with self.session_factory() as session:
                    handler = OrderHandler(session, self.exchange)
                    await handler.handle_filled_order(order)
            else:
                logger.debug(f"[process_orders] Ордер {order_id} имеет статус {order_status}, пропускаем")

    async def _check_grid_shift(self, ticker: dict):
        current_price = ticker.get('last')
        if not current_price:
            logger.warning(f"[check_grid_shift] Нет цены в ticker: {ticker}")
            return

        if self._last_shift_time:
            time_since_last_shift = time.time() - self._last_shift_time
            if time_since_last_shift < 15:
                return

        async with self.session_factory() as session:
            stmt = select(DcaCycle).where(
                DcaCycle.config_id == self.config_id,
                DcaCycle.status == CycleStatus.OPEN
            )
            result = await session.execute(stmt)
            cycle = result.scalar_one_or_none()

            if not cycle:
                return

            stmt = select(Order).where(
                Order.cycle_id == cycle.id,
                Order.order_index == 0,
                Order.order_type == 'BUY_SAFETY'
            )
            result = await session.execute(stmt)
            first_order = result.scalar_one_or_none()

            if not first_order:
                return

            if first_order.status == OrderStatus.FILLED:
                return

            config = await session.get(BotConfig, self.config_id)
            if not config:
                return

            reference_order_price = cycle.initial_first_order_price or first_order.price
            
            ideal_entry_price = current_price * (1 - config.first_order_offset_pct / 100)
            
            shift_diff_pct = ((ideal_entry_price - reference_order_price) / reference_order_price) * 100

            if shift_diff_pct >= config.grid_shift_threshold_pct:
                logger.info(f"Сдвиг: Идеальная цена {ideal_entry_price:.2f} выше установленной {reference_order_price:.2f} на {shift_diff_pct:.2f}% (порог: {config.grid_shift_threshold_pct}%)")
                
                from app.domain.bot_manager import BotManager
                
                manager = BotManager(session)
                await manager.shift_grid(cycle, config, current_price)
                
                self._last_shift_time = time.time()
                logger.info(f"Сетка успешно сдвинута для цикла {cycle.id}")

    async def stop(self):
        self._is_running = False
        if self.exchange:
            await self.exchange.close()