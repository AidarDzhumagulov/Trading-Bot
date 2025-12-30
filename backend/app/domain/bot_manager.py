import asyncio
from ccxt import async_support
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.infrastructure.persistence.sqlalchemy.models import DcaCycle, Order
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.shared.utils import calculate_grid
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.shared.websocket import BinanceWebsocketManager
from app.shared.websocket_registry import websocket_registry
from app.shared.exchange_helper import TradingUtils
from app.core.dependencies import get_session_factory
from app.core.logging import logger
from app.core.config import settings


class BotManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_first_cycle(self, config):
        exchange = async_support.binance({
            'apiKey': config.binance_api_key,
            'secret': config.binance_api_secret,
        })
        if settings.ENVIRONMENT == "DEV":
            exchange.set_sandbox_mode(True)

        try:
            balance = await exchange.fetch_balance()
            usdt_info = balance.get('USDT', {})
            free_usdt = usdt_info.get('free', 0.0)
            
            MIN_TRADING_AMOUNT = 10.0
            
            if free_usdt < MIN_TRADING_AMOUNT:
                raise ValueError(
                    f"Insufficient balance. Minimum {MIN_TRADING_AMOUNT} USDT required. "
                    f"Available: {free_usdt:.2f} USDT"
                )
            
            if config.total_budget > free_usdt:
                logger.warning(
                    f"Budget ({config.total_budget:.2f} USDT) exceeds available balance "
                    f"({free_usdt:.2f} USDT). Using available balance."
                )
                effective_budget = free_usdt * 0.99  # Оставляем 1% запас
            else:
                effective_budget = config.total_budget
            
            ticker = await exchange.fetch_ticker(config.symbol)
            current_price = ticker['last']

            utils = TradingUtils(exchange)
            amount_precision = await utils.get_amount_precision(config.symbol)
            price_precision = await utils.get_price_precision(config.symbol)

            grid_data = calculate_grid(
                current_price=current_price,
                total_budget=effective_budget,
                grid_levels=config.safety_orders_count,
                grid_length_pct=config.grid_length_pct,
                first_step_pct=config.first_order_offset_pct,
                volume_scale_pct=config.volume_scale_pct,
                amount_precision=amount_precision,
                price_precision=price_precision
            )

            logger.info(f"Starting cycle with budget: {effective_budget:.2f} USDT (available: {free_usdt:.2f})")

            new_cycle = DcaCycle(config_id=config.id, status=CycleStatus.OPEN)
            self.session.add(new_cycle)
            await self.session.flush()

            db_orders = []
            for item in grid_data:
                new_order = Order(
                    cycle_id=new_cycle.id,
                    order_index=item['index'],
                    order_type="BUY_SAFETY",
                    price=item['price'],
                    amount=item['amount_base'],
                    status=OrderStatus.PENDING
                )
                self.session.add(new_order)
                db_orders.append(new_order)

            first_order = db_orders[0]
            
            new_cycle.initial_first_order_price = first_order.price
            
            ws_manager = BinanceWebsocketManager(
                api_key=config.binance_api_key,
                api_secret=config.binance_api_secret,
                session_factory=get_session_factory(),
                config_id=config.id,
                symbol=config.symbol
            )
            
            websocket_registry.add(config.id, ws_manager)
            asyncio.create_task(ws_manager.run_forever())
            logger.info(f"WebSocket Manager запущен для config_id: {config.id}")
            
            await asyncio.sleep(1)
            
            safe_amount = await utils.round_amount(config.symbol, first_order.amount)
            safe_price = await utils.round_price(config.symbol, first_order.price)
            
            if not await utils.check_min_notional(config.symbol, safe_amount, safe_price):
                raise ValueError(f"Order amount {safe_amount} * price {safe_price} is below minimum notional for {config.symbol}")
            
            binance_res = await exchange.create_order(
                symbol=config.symbol,
                type='limit',
                side='buy',
                amount=safe_amount,
                price=safe_price
            )

            first_order.binance_order_id = str(binance_res['id'])
            first_order.status = OrderStatus.ACTIVE
            await self.session.commit()
            logger.info(f"[BotManager] Первый ордер создан: binance_id={first_order.binance_order_id}, order_id={first_order.id}")

            return {
                "message": "Bot started successfully",
                "cycle_id": new_cycle.id,
                "first_binance_id": binance_res['id']
            }

        except Exception as e:
            await self.session.rollback()
            raise e
        finally:
            await exchange.close()

    async def shift_grid(self, cycle: DcaCycle, config, current_price: float):
        exchange = async_support.binance({
            'apiKey': config.binance_api_key,
            'secret': config.binance_api_secret,
        })
        if settings.ENVIRONMENT == "DEV":
            exchange.set_sandbox_mode(True)

        try:
            stmt = select(Order).where(
                Order.cycle_id == cycle.id,
                Order.order_type == 'BUY_SAFETY',
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PARTIAL])
            )
            result = await self.session.execute(stmt)
            active_orders = result.scalars().all()

            for order in active_orders:
                if order.binance_order_id:
                    try:
                        await exchange.cancel_order(order.binance_order_id, config.symbol)
                        logger.info(f"Отменен ордер {order.binance_order_id} (index: {order.order_index})")
                    except Exception as e:
                        logger.warning(f"Не удалось отменить ордер {order.binance_order_id}: {e}")
                    
                    order.status = OrderStatus.CANCELED
                    order.binance_order_id = None

            await self.session.flush()

            stmt = select(Order).where(
                Order.cycle_id == cycle.id,
                Order.order_type == 'BUY_SAFETY',
                Order.status != OrderStatus.FILLED
            )
            result = await self.session.execute(stmt)
            orders_to_delete = result.scalars().all()
            
            for order in orders_to_delete:
                await self.session.delete(order)
            
            await self.session.flush()

            utils = TradingUtils(exchange)
            amount_precision = await utils.get_amount_precision(config.symbol)
            price_precision = await utils.get_price_precision(config.symbol)

            grid_data = calculate_grid(
                current_price=current_price,
                total_budget=config.total_budget,
                grid_levels=config.safety_orders_count,
                grid_length_pct=config.grid_length_pct,
                first_step_pct=config.first_order_offset_pct,
                volume_scale_pct=config.volume_scale_pct,
                amount_precision=amount_precision,
                price_precision=price_precision
            )

            db_orders = []
            for item in grid_data:
                new_order = Order(
                    cycle_id=cycle.id,
                    order_index=item['index'],
                    order_type="BUY_SAFETY",
                    price=item['price'],
                    amount=item['amount_base'],
                    status=OrderStatus.PENDING
                )
                self.session.add(new_order)
                db_orders.append(new_order)

            await self.session.flush()

            first_order = db_orders[0]
            
            safe_amount = await utils.round_amount(config.symbol, first_order.amount)
            safe_price = await utils.round_price(config.symbol, first_order.price)
            
            if not await utils.check_min_notional(config.symbol, safe_amount, safe_price):
                raise ValueError(f"Order amount {safe_amount} * price {safe_price} is below minimum notional for {config.symbol}")
            
            binance_res = await exchange.create_order(
                symbol=config.symbol,
                type='limit',
                side='buy',
                amount=safe_amount,
                price=safe_price
            )

            first_order.binance_order_id = str(binance_res['id'])
            first_order.status = OrderStatus.ACTIVE
            
            cycle.initial_first_order_price = first_order.price

            await self.session.commit()
            logger.info(f"Сетка сдвинута. Новый первый ордер: {binance_res['id']} по цене {first_order.price:.2f}")

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка при сдвиге сетки: {e}")
            raise e
        finally:
            await exchange.close()