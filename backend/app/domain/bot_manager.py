import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session_factory
from app.core.logging import logger
from app.infrastructure.persistence.sqlalchemy.models import DcaCycle, Order
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.shared.clients import BinanceClient
from app.shared.exchange_helper import TradingUtils
from app.shared.utils import GridConfig, GridCalculator
from app.shared.websocket import BinanceWebsocketManager
from app.shared.websocket_registry import websocket_registry

MIN_TRADING_AMOUNT = 10.0
BALANCE_RESERVE_PCT = 0.99


class BotManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_first_cycle(self, config):
        async with BinanceClient.create(
            config.binance_api_key, config.binance_api_secret
        ) as client:
            try:
                free_usdt = await client.get_free_usdt()

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
                    effective_budget = free_usdt * BALANCE_RESERVE_PCT
                else:
                    effective_budget = config.total_budget

                current_price = await client.get_price(config.symbol)

                utils = TradingUtils(client.exchange)
                amount_precision = await utils.get_amount_precision(config.symbol)
                price_precision = await utils.get_price_precision(config.symbol)

                grid_config = GridConfig(
                    current_price=current_price,
                    total_budget=effective_budget,
                    grid_levels=config.safety_orders_count,
                    grid_length_pct=config.grid_length_pct,
                    first_step_pct=config.first_order_offset_pct,
                    volume_scale_pct=config.volume_scale_pct,
                    amount_precision=amount_precision,
                    price_precision=price_precision,
                )
                calculator = GridCalculator(grid_config)
                grid_data = calculator.calculate()

                logger.info(
                    f"Starting cycle with budget: {effective_budget:.2f} USDT "
                    f"(available: {free_usdt:.2f})"
                )

                new_cycle = DcaCycle(config_id=config.id, status=CycleStatus.OPEN)
                self.session.add(new_cycle)

                db_orders = []
                for item in grid_data:
                    new_order = Order(
                        cycle=new_cycle,
                        order_index=item["index"],
                        order_type="BUY_SAFETY",
                        price=item["price"],
                        amount=item["amount_base"],
                        status=OrderStatus.PENDING,
                    )
                    db_orders.append(new_order)
                self.session.add_all(db_orders)

                first_order = db_orders[0]
                new_cycle.initial_first_order_price = first_order.price

                await self._setup_websocket(config)

                await asyncio.sleep(1)

                safe_amount = await utils.round_amount(config.symbol, first_order.amount)
                safe_price = await utils.round_price(config.symbol, first_order.price)

                if not await utils.check_min_notional(
                    config.symbol, safe_amount, safe_price
                ):
                    raise ValueError(
                        f"Order amount {safe_amount} * price {safe_price} "
                        f"is below minimum notional for {config.symbol}"
                    )

                binance_res = await client.create_limit_order(
                    symbol=config.symbol,
                    side="buy",
                    amount=safe_amount,
                    price=safe_price,
                )

                first_order.binance_order_id = str(binance_res["id"])
                first_order.status = OrderStatus.ACTIVE
                config.is_active = True
                await self.session.commit()

                logger.info(
                    f"[BotManager] Первый ордер создан: "
                    f"binance_id={first_order.binance_order_id}, order_id={first_order.id}"
                )

                return {
                    "message": "Bot started successfully",
                    "cycle_id": new_cycle.id,
                    "first_binance_id": binance_res["id"],
                }

            except Exception as e:
                await self.session.rollback()
                raise e

    async def _setup_websocket(self, config):
        """Setup WebSocket manager for config"""
        old_ws_manager = websocket_registry.get(config.id)
        if old_ws_manager:
            logger.warning(
                f"Old WebSocket still running for config {config.id}, stopping..."
            )
            await old_ws_manager.stop()
            await websocket_registry.remove(config.id)
            await asyncio.sleep(0.5)
            logger.info("Old WebSocket stopped successfully")

        ws_manager = BinanceWebsocketManager(
            api_key=config.binance_api_key,
            api_secret=config.binance_api_secret,
            session_factory=get_session_factory(),
            config_id=config.id,
            symbol=config.symbol,
        )

        await websocket_registry.add(config.id, ws_manager)
        asyncio.create_task(ws_manager.run_forever())
        logger.info(f"WebSocket Manager запущен для config_id: {config.id}")

    async def shift_grid(self, cycle: DcaCycle, config, current_price: float):
        async with BinanceClient.create(
            config.binance_api_key, config.binance_api_secret
        ) as client:
            try:
                await self._cancel_pending_orders(cycle, config, client)
                await self._delete_unfilled_orders(cycle)

                utils = TradingUtils(client.exchange)
                amount_precision = await utils.get_amount_precision(config.symbol)
                price_precision = await utils.get_price_precision(config.symbol)

                grid_config = GridConfig(
                    current_price=current_price,
                    total_budget=config.total_budget,
                    grid_levels=config.safety_orders_count,
                    grid_length_pct=config.grid_length_pct,
                    first_step_pct=config.first_order_offset_pct,
                    volume_scale_pct=config.volume_scale_pct,
                    amount_precision=amount_precision,
                    price_precision=price_precision,
                )

                calculator = GridCalculator(grid_config)
                grid_data = calculator.calculate()

                db_orders = []
                for item in grid_data:
                    new_order = Order(
                        cycle_id=cycle.id,
                        order_index=item["index"],
                        order_type="BUY_SAFETY",
                        price=item["price"],
                        amount=item["amount_base"],
                        status=OrderStatus.PENDING,
                    )
                    self.session.add(new_order)
                    db_orders.append(new_order)

                await self.session.flush()

                first_order = db_orders[0]

                safe_amount = await utils.round_amount(config.symbol, first_order.amount)
                safe_price = await utils.round_price(config.symbol, first_order.price)

                if not await utils.check_min_notional(
                    config.symbol, safe_amount, safe_price
                ):
                    raise ValueError(
                        f"Order amount {safe_amount} * price {safe_price} "
                        f"is below minimum notional for {config.symbol}"
                    )

                binance_res = await client.create_limit_order(
                    symbol=config.symbol,
                    side="buy",
                    amount=safe_amount,
                    price=safe_price,
                )

                first_order.binance_order_id = str(binance_res["id"])
                first_order.status = OrderStatus.ACTIVE
                cycle.initial_first_order_price = first_order.price

                await self.session.commit()
                logger.info(
                    f"Сетка сдвинута. Новый первый ордер: "
                    f"{binance_res['id']} по цене {first_order.price:.2f}"
                )

            except Exception as e:
                await self.session.rollback()
                logger.error(f"Ошибка при сдвиге сетки: {e}")
                raise e

    async def _cancel_pending_orders(
        self, cycle: DcaCycle, config, client: BinanceClient
    ):
        """Cancel all pending orders on exchange"""
        stmt = select(Order).where(
            Order.cycle_id == cycle.id,
            Order.order_type == "BUY_SAFETY",
            Order.status.in_(
                [OrderStatus.PENDING, OrderStatus.PARTIAL, OrderStatus.ACTIVE]
            ),
        )
        result = await self.session.execute(stmt)
        orders_to_cancel = result.scalars().all()

        binance_ids_to_cancel = {
            order.binance_order_id
            for order in orders_to_cancel
            if order.binance_order_id
        }

        for binance_id in binance_ids_to_cancel:
            try:
                await client.cancel_order(binance_id, config.symbol)
                logger.info(f"Отменен ордер {binance_id}")
            except Exception as e:
                logger.warning(f"Не удалось отменить ордер {binance_id}: {e}")

        for order in orders_to_cancel:
            order.status = OrderStatus.CANCELED
            order.binance_order_id = None

        await self.session.flush()

    async def _delete_unfilled_orders(self, cycle: DcaCycle):
        """Delete unfilled orders from database"""
        stmt = select(Order).where(
            Order.cycle_id == cycle.id,
            Order.order_type == "BUY_SAFETY",
            Order.status != OrderStatus.FILLED,
        )
        result = await self.session.execute(stmt)
        orders_to_delete = result.scalars().all()

        logger.info(f"Удаляем {len(orders_to_delete)} незаполненных ордеров")

        for order in orders_to_delete:
            await self.session.delete(order)

        await self.session.flush()
