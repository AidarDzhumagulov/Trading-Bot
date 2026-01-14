import ccxt
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.domain.exceptions import OrderCreationError, MinNotionalError
from app.infrastructure.persistence.sqlalchemy.models import Order
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.shared.exchange_helper import TradingUtils


class OrderPlacer:
    """
    Handles order creation and cancellation on exchange.

    Provides:
    - TP order creation with validation
    - Next safety order placement
    - Order cancellation with DB update
    """

    def __init__(self, exchange, session: AsyncSession):
        self.exchange = exchange
        self.session = session
        self.utils = TradingUtils(exchange)

    async def cancel_tp_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel existing TP order on exchange and update DB.

        Args:
            order_id: Binance order ID
            symbol: Trading pair symbol

        Returns:
            True if cancelled successfully
        """
        try:
            await self.exchange.cancel_order(order_id, symbol)

            stmt = (
                update(Order)
                .where(Order.binance_order_id == order_id)
                .values(status=OrderStatus.CANCELED)
            )
            await self.session.execute(stmt)

            logger.info(
                f"[OrderPlacer] TP-ордер {order_id} отменен и помечен как CANCELED"
            )
            return True

        except Exception as e:
            logger.error(f"[OrderPlacer] Не удалось отменить TP: {e}")
            return False

    async def create_tp_order(
        self, cycle, symbol: str, amount: float, price: float, effective_tp_pct: float
    ) -> Order:
        """
        Create take profit (sell) order.

        Args:
            cycle: DcaCycle model instance
            symbol: Trading pair symbol
            amount: Amount to sell
            price: TP price
            effective_tp_pct: Effective TP percentage for logging

        Returns:
            Created Order model instance

        Raises:
            MinNotionalError: If order value below minimum
            OrderCreationError: If exchange order fails
        """
        if not await self.utils.check_min_notional(symbol, amount, price):
            notional = amount * price
            raise MinNotionalError(
                f"TP ниже минимальной суммы: {notional:.2f} USDT",
                details={"amount": amount, "price": price, "notional": notional},
            )

        base_asset = symbol.split("/")[0]
        notional_value = amount * price

        logger.info(
            f"[OrderPlacer] Создание TP-ордера: "
            f"количество={amount:.8f} {base_asset}, "
            f"цена={price:.2f} USDT (TP: {effective_tp_pct:.2f}%), "
            f"сумма={notional_value:.2f} USDT"
        )

        try:
            binance_res = await self.exchange.create_order(
                symbol=symbol,
                type="limit",
                side="sell",
                amount=amount,
                price=price,
            )
        except ccxt.NetworkError as e:
            raise OrderCreationError(f"Ошибка сети: {e}")
        except ccxt.InsufficientFunds as e:
            raise OrderCreationError(f"Недостаточно средств: {e}")
        except ccxt.InvalidOrder as e:
            raise OrderCreationError(f"Невалидный ордер: {e}")
        except Exception as e:
            raise OrderCreationError(f"Неожиданная ошибка: {e}")

        tp_binance_id = str(binance_res["id"])

        cycle.current_tp_order_id = tp_binance_id
        cycle.current_tp_price = price

        new_tp_order = Order(
            cycle_id=cycle.id,
            binance_order_id=tp_binance_id,
            order_type="SELL_TP",
            order_index=-1,
            price=price,
            amount=amount,
            status=OrderStatus.ACTIVE,
        )
        self.session.add(new_tp_order)

        expected_profit = notional_value - float(cycle.total_quote_spent)

        logger.info(
            f"[OrderPlacer] TP-ордер создан: "
            f"binance_id={tp_binance_id}, "
            f"price={price:.2f}, "
            f"amount={amount:.8f}, "
            f"effective_tp={effective_tp_pct:.2f}%, "
            f"expected_profit={expected_profit:.2f} USDT"
        )

        return new_tp_order

    async def place_next_safety_order(
        self, cycle, current_order_index: int, symbol: str
    ) -> Order | None:
        """
        Place next safety order in the grid.

        Args:
            cycle: DcaCycle model instance
            current_order_index: Index of just-filled order
            symbol: Trading pair symbol

        Returns:
            Created Order or None if no next order
        """
        next_index = current_order_index + 1

        stmt = (
            select(Order)
            .where(
                Order.cycle_id == cycle.id,
                Order.order_index == next_index,
                Order.order_type == "BUY_SAFETY",
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        next_order = result.scalar_one_or_none()

        if not next_order:
            logger.info(f"[OrderPlacer] Нет следующего ордера с индексом {next_index}")
            return None

        safe_amount = await self.utils.round_amount(symbol, next_order.amount)
        safe_price = await self.utils.round_price(symbol, next_order.price)

        if not await self.utils.check_min_notional(symbol, safe_amount, safe_price):
            logger.warning(
                f"[OrderPlacer] Следующий ордер слишком мал "
                f"(количество={safe_amount}, цена={safe_price}), пропускаем"
            )
            return None

        try:
            binance_res = await self.exchange.create_order(
                symbol=symbol,
                type="limit",
                side="buy",
                amount=safe_amount,
                price=safe_price,
            )

            next_order.binance_order_id = str(binance_res["id"])
            next_order.status = OrderStatus.ACTIVE

            logger.info(
                f"[OrderPlacer] Следующий ордер создан: "
                f"binance_id={next_order.binance_order_id}, "
                f"order_id={next_order.id}"
            )

            return next_order

        except Exception as e:
            logger.error(f"[OrderPlacer] Ошибка создания следующего ордера: {e}")
            return None
