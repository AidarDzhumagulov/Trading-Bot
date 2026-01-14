import asyncio
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.domain.constants import TakeProfitDefaults
from app.domain.exceptions import (
    InsufficientBalanceError,
    BalanceDeviationError,
    OrderCreationError,
    MinNotionalError,
)
from app.domain.services import (
    FeeCalculator,
    CycleUpdater,
    BalanceValidator,
    DustManager,
    TakeProfitCalculator,
    OrderPlacer,
)
from app.infrastructure.persistence.sqlalchemy.models import Order, DcaCycle, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.shared.exchange_helper import TradingUtils
from app.shared.websocket_registry import websocket_registry


class OrderHandler:
    """
    Handles filled order events from exchange.

    Coordinates multiple services to process:
    - Buy order fills (update cycle, create TP, place next order)
    - Sell/TP order fills (close cycle, calculate profit, start new cycle)
    """

    def __init__(self, session: AsyncSession, exchange):
        self.session = session
        self.exchange = exchange

        self.fee_calculator = FeeCalculator(exchange)
        self.cycle_updater = CycleUpdater()
        self.balance_validator = BalanceValidator(exchange)
        self.dust_manager = DustManager(exchange)
        self.tp_calculator = TakeProfitCalculator(exchange)
        self.order_placer = OrderPlacer(exchange, session)
        self.utils = TradingUtils(exchange)

    async def handle_filled_order(self, binance_order: dict):
        """
        Main entry point for processing filled orders.

        Routes to appropriate handler based on order type.
        """
        binance_id = str(binance_order["id"])
        logger.info(f"[OrderHandler] Обработка ордера {binance_id}")

        db_order = await self._find_or_create_order(binance_id, binance_order)
        if not db_order:
            return

        if db_order.status == OrderStatus.FILLED:
            logger.info(
                f"[OrderHandler] Ордер {binance_id} уже обработан (status=filled)"
            )
            return

        cycle = await self.session.get(DcaCycle, db_order.cycle_id)
        config = await self.session.get(BotConfig, cycle.config_id)

        if db_order.order_type == "BUY_SAFETY":
            await self._handle_buy_fill(
                db_order=db_order,
                cycle=cycle,
                config=config,
                binance_order=binance_order,
            )
        elif db_order.order_type == "SELL_TP":
            await self._handle_tp_fill(db_order, cycle, config, binance_order)

        await self.session.commit()

    async def _find_or_create_order(
        self, binance_id: str, binance_order: dict
    ) -> Order | None:
        """Find order in DB or create if it's a TP order found via cycle"""
        stmt = (
            select(Order).where(Order.binance_order_id == binance_id).with_for_update()
        )
        result = await self.session.execute(stmt)
        db_order = result.scalar_one_or_none()

        if db_order:
            return db_order

        stmt = select(DcaCycle).where(DcaCycle.current_tp_order_id == binance_id)
        result = await self.session.execute(stmt)
        cycle_with_tp = result.scalar_one_or_none()

        if cycle_with_tp:
            logger.warning(
                f"[OrderHandler] TP-ордер {binance_id} найден через "
                f"current_tp_order_id, создаем запись в orders"
            )
            db_order = Order(
                cycle_id=cycle_with_tp.id,
                binance_order_id=binance_id,
                order_type="SELL_TP",
                order_index=-1,
                price=float(binance_order.get("price", 0)),
                amount=float(binance_order.get("amount", cycle_with_tp.total_base_qty)),
                status=OrderStatus.ACTIVE,
            )
            self.session.add(db_order)
            await self.session.flush()
            return db_order

        logger.error(f"[OrderHandler] Ордер {binance_id} не найден в БД. Пропускаем.")
        return None

    async def _handle_buy_fill(
        self, db_order: Order, cycle: DcaCycle, config: BotConfig, binance_order: dict
    ):
        """
        Handle buy order fill event.

        Steps:
        1. Calculate fees and net quantity
        2. Update cycle statistics
        3. Cancel old TP order
        4. Validate balance
        5. Process dust
        6. Calculate and create new TP order
        7. Place next safety order
        """
        logger.info(
            f"[OrderHandler] Обработка BUY ордера {db_order.id}, cycle {cycle.id}"
        )
        db_order.status = OrderStatus.FILLED

        fill_result = await self.fee_calculator.calculate_fill_result(
            binance_order=binance_order,
            symbol=config.symbol,
            order_price=db_order.price,
        )

        cycle_stats = self.cycle_updater.update_after_buy(cycle, fill_result)

        if cycle.current_tp_order_id:
            await self.order_placer.cancel_tp_order(
                cycle.current_tp_order_id, config.symbol
            )

        try:
            balance_result = await self.balance_validator.validate_for_sell(
                symbol=config.symbol, expected_amount=float(cycle.total_base_qty)
            )
        except (InsufficientBalanceError, BalanceDeviationError) as e:
            logger.error(f"[OrderHandler] Ошибка валидации баланса: {e.message}")
            return

        dust_result = await self.dust_manager.process_dust(
            amount=balance_result.amount_to_sell,
            accumulated_dust=float(cycle.accumulated_dust or 0.0),
            symbol=config.symbol,
        )

        cycle.accumulated_dust = dust_result.new_dust

        if dust_result.sellable_amount <= 0:
            logger.error("[OrderHandler] Количество после обработки пыли равно нулю")
            return

        market = await self.utils.get_market(config.symbol)
        amount_precision = market.get("precision", {}).get("amount", 8)

        tp_params = await self.tp_calculator.calculate(
            cycle_stats=cycle_stats,
            config_tp_pct=float(config.take_profit_pct),
            symbol=config.symbol,
            amount_precision=amount_precision,
        )

        try:
            await self.order_placer.create_tp_order(
                cycle=cycle,
                symbol=config.symbol,
                amount=dust_result.sellable_amount,
                price=tp_params.tp_price,
                effective_tp_pct=tp_params.effective_tp_pct,
            )
        except (MinNotionalError, OrderCreationError) as e:
            logger.error(f"[OrderHandler] Ошибка создания TP: {e.message}")
            return

        await self.order_placer.place_next_safety_order(
            cycle=cycle, current_order_index=db_order.order_index, symbol=config.symbol
        )

    async def _handle_tp_fill(
        self, db_order: Order, cycle: DcaCycle, config: BotConfig, binance_order: dict
    ):
        """
        Handle take profit (sell) order fill.

        Steps:
        1. Mark order and cycle as closed
        2. Cancel remaining active orders
        3. Calculate actual profit
        4. Log profit analysis
        5. Start new cycle
        """
        db_order.status = OrderStatus.FILLED
        cycle.status = CycleStatus.CLOSED
        cycle.closed_at = datetime.now(UTC)
        cycle.accumulated_dust = 0.0

        logger.info("[OrderHandler] Накопленная пыль сброшена для следующего цикла")

        await self._cancel_remaining_orders(cycle, config.symbol)

        self._log_tp_order_details(binance_order, db_order)

        profit = self._calculate_profit(binance_order, cycle, config, db_order)
        cycle.profit_usdt = profit

        await self.session.commit()

        await self._start_new_cycle(config)

    async def _cancel_remaining_orders(self, cycle: DcaCycle, symbol: str):
        """Cancel all active orders for cycle"""
        stmt = select(Order).where(
            Order.cycle_id == cycle.id, Order.status == OrderStatus.ACTIVE
        )
        result = await self.session.execute(stmt)

        for order in result.scalars():
            try:
                await self.exchange.cancel_order(order.binance_order_id, symbol)
                order.status = OrderStatus.CANCELED
            except Exception as e:
                logger.error(f"Не удалось отменить ордер {order.binance_order_id}: {e}")

    @staticmethod
    def _log_tp_order_details(binance_order: dict, db_order: Order):
        """Log TP order details for debugging"""
        logger.info("Детали TP-ордера с биржи:")
        logger.info(f"  id: {binance_order.get('id')}")
        logger.info(f"  цена: {binance_order.get('price')}")
        logger.info(f"  количество: {binance_order.get('amount')}")
        logger.info(f"  стоимость: {binance_order.get('cost')}")
        logger.info(f"  комиссия: {binance_order.get('fee')}")
        logger.info(f"  цена ордера в БД: {db_order.price}")
        logger.info(f"  количество ордера в БД: {db_order.amount}")

    def _calculate_profit(
        self, binance_order: dict, cycle: DcaCycle, config: BotConfig, db_order: Order
    ) -> float:
        """Calculate and log actual profit from TP fill"""
        base_cost = Decimal(str(binance_order.get("cost", 0)))

        if base_cost == 0:
            price = Decimal(str(binance_order.get("price", db_order.price)))
            amount = Decimal(str(binance_order.get("amount", db_order.amount)))
            base_cost = price * amount
            logger.warning(f"Стоимость не предоставлена, рассчитано: {base_cost}")

        fee_cost = self.fee_calculator.calculate_sell_fee(binance_order)
        total_received = base_cost - fee_cost
        total_spent = Decimal(str(cycle.total_quote_spent or 0.0))

        profit = float(total_received - total_spent)

        actual_profit_pct = (
            (profit / float(total_spent)) * 100 if total_spent > 0 else 0
        )
        expected_min_profit_pct = (
            config.take_profit_pct * TakeProfitDefaults.MIN_PROFIT_CHECK_RATIO
        )

        if actual_profit_pct < expected_min_profit_pct:
            logger.error(
                f"АНОМАЛИЯ! Цикл {cycle.id} закрыт с низкой прибылью: "
                f"{profit:.4f} USDT ({actual_profit_pct:.2f}%), "
                f"ожидалось минимум {expected_min_profit_pct:.2f}%"
            )

        logger.info(
            f"Цикл {cycle.id} закрыт: "
            f"получено={float(total_received):.2f} USDT "
            f"(брутто={float(base_cost):.2f}, комиссия={float(fee_cost):.4f}), "
            f"потрачено={float(total_spent):.2f} USDT, "
            f"прибыль={profit:.2f} USDT ({actual_profit_pct:.2f}%)"
        )

        return profit

    async def _start_new_cycle(self, config: BotConfig):
        """Stop old websocket and start new cycle"""
        from app.domain.bot_manager import BotManager

        old_ws_manager = websocket_registry.get(config.id)
        if old_ws_manager:
            logger.info(f"Остановка WebSocket менеджера для config {config.id}")
            await old_ws_manager.stop()
            await websocket_registry.remove(config.id)
            await asyncio.sleep(0.5)

        manager = BotManager(self.session)
        await manager.start_first_cycle(config)
        logger.info(f"Новый цикл запущен для config {config.id}")
