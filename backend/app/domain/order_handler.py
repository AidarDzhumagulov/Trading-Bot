from decimal import Decimal
from datetime import datetime

from sqlalchemy import select, update

from app.infrastructure.persistence.sqlalchemy.models import Order, DcaCycle, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.shared.exchange_helper import TradingUtils
from app.core.logging import logger


class OrderHandler:
    def __init__(self, session, exchange):
        self.session = session
        self.exchange = exchange
        self.utils = TradingUtils(exchange)

    async def handle_filled_order(self, binance_order: dict):
        binance_id = str(binance_order['id'])
        logger.info(f"[OrderHandler] Обработка ордера {binance_id}")

        stmt = select(Order).where(Order.binance_order_id == binance_id)
        result = await self.session.execute(stmt)
        db_order = result.scalar_one_or_none()

        if not db_order:
            stmt = select(DcaCycle).where(DcaCycle.current_tp_order_id == binance_id)
            result = await self.session.execute(stmt)
            cycle_with_tp = result.scalar_one_or_none()
            
            if cycle_with_tp:
                logger.warning(f"[OrderHandler] TP-ордер {binance_id} найден через current_tp_order_id, но отсутствует в таблице orders. Создаем запись.")
                db_order = Order(
                    cycle_id=cycle_with_tp.id,
                    binance_order_id=binance_id,
                    order_type="SELL_TP",
                    order_index=-1,
                    price=float(binance_order.get('price', 0)),
                    amount=float(binance_order.get('amount', cycle_with_tp.total_base_qty)),
                    status=OrderStatus.ACTIVE
                )
                self.session.add(db_order)
                await self.session.flush()
            else:
                logger.error(f"[OrderHandler] Ордер {binance_id} не найден в БД и не является текущим TP-ордером. Пропускаем.")
                all_orders = await self.session.execute(select(Order))
                logger.info(f"[OrderHandler] Всего ордеров в БД: {len(all_orders.scalars().all())}")
                return

        if db_order.status == OrderStatus.FILLED:
            logger.info(f"[OrderHandler] Ордер {binance_id} уже обработан (status=filled)")
            return

        cycle = await self.session.get(DcaCycle, db_order.cycle_id)
        config = await self.session.get(BotConfig, cycle.config_id)

        if db_order.order_type == "BUY_SAFETY":
            await self._handle_buy_fill(db_order, cycle, config, binance_order)
        elif db_order.order_type == "SELL_TP":
            await self._handle_tp_fill(db_order, cycle, config, binance_order)

        await self.session.commit()

    async def _handle_buy_fill(self, db_order, cycle, config, binance_order):
        logger.info(f"[OrderHandler] Обработка BUY ордера {db_order.id}, cycle {cycle.id}")
        db_order.status = OrderStatus.FILLED

        filled_qty = Decimal(str(binance_order['amount']))
        logger.info(f"[OrderHandler] Исполнено: {filled_qty}, цена: {db_order.price}")
        
        fee_info = binance_order.get('fee', {})
        fee_qty = Decimal("0")
        base_currency = config.symbol.split('/')[0].upper()
        
        if fee_info:
            if isinstance(fee_info, dict):
                fee_cost = Decimal(str(fee_info.get('cost', 0)))
                fee_currency = fee_info.get('currency', '').upper()
                
                if fee_currency == base_currency:
                    fee_qty = fee_cost
                elif fee_currency == 'USDT' or fee_currency == 'USD':
                    if db_order.price > 0:
                        fee_qty = fee_cost / Decimal(str(db_order.price))
                    else:
                        fee_qty = Decimal("0")
                else:
                    logger.warning(f"Неизвестная валюта комиссии: {fee_currency}, используем fallback")
                    fee_rate = Decimal("0.001")
                    fee_qty = filled_qty * fee_rate
            else:
                fee_qty = Decimal(str(fee_info))
        else:
            try:
                await self.exchange.load_markets()
                market = self.exchange.market(config.symbol)
                taker_fee = market.get('taker', 0.001)
                fee_rate = Decimal(str(taker_fee))
                fee_qty = filled_qty * fee_rate
            except Exception as e:
                logger.warning(f"Не удалось получить комиссию с биржи, используем fallback 0.1%: {e}")
                fee_rate = Decimal("0.001")
                fee_qty = filled_qty * fee_rate
        
        net_qty = filled_qty - fee_qty

        current_base_qty = Decimal(str(cycle.total_base_qty or 0.0))
        current_quote_spent = Decimal(str(cycle.total_quote_spent or 0.0))
        
        new_base_qty = current_base_qty + net_qty
        new_quote_spent = current_quote_spent + (Decimal(str(db_order.price)) * filled_qty)
        
        cycle.total_base_qty = float(new_base_qty)
        cycle.total_quote_spent = float(new_quote_spent)

        avg_price = new_quote_spent / new_base_qty if new_base_qty > 0 else Decimal("0")
        cycle.avg_price = float(avg_price)
        
        logger.info(f"[OrderHandler] Обновлен цикл {cycle.id}: base_qty={cycle.total_base_qty}, quote_spent={cycle.total_quote_spent}, avg_price={cycle.avg_price}")

        tp_price = avg_price * (Decimal("1") + Decimal(str(config.take_profit_pct)) / Decimal("100"))

        if cycle.current_tp_order_id:
            try:
                await self.exchange.cancel_order(cycle.current_tp_order_id, config.symbol)
                stmt = update(Order).where(
                    Order.binance_order_id == cycle.current_tp_order_id
                ).values(status=OrderStatus.CANCELED)
                await self.session.execute(stmt)
                logger.info(f"[OrderHandler] Старый TP-ордер {cycle.current_tp_order_id} отменен и помечен как CANCELED в БД")
            except Exception as e:
                logger.error(f"Не удалось отменить старый TP: {e}")

        safe_amount = await self.utils.round_amount(config.symbol, cycle.total_base_qty)
        safe_price = await self.utils.round_price(config.symbol, float(tp_price))
        
        if not await self.utils.check_min_notional(config.symbol, safe_amount, safe_price):
            logger.warning(f"[OrderHandler] TP Order too small (amount={safe_amount}, price={safe_price}), waiting for more fills")
            return
        
        tp_res = await self.exchange.create_order(
            symbol=config.symbol,
            type='limit',
            side='sell',
            amount=safe_amount,
            price=safe_price
        )

        tp_binance_id = str(tp_res['id'])
        cycle.current_tp_order_id = tp_binance_id

        new_tp_order = Order(
            cycle_id=cycle.id,
            binance_order_id=tp_binance_id,
            order_type="SELL_TP",
            order_index=-1,
            price=safe_price,
            amount=safe_amount,
            status=OrderStatus.ACTIVE
        )
        self.session.add(new_tp_order)
        logger.info(f"[OrderHandler] TP-ордер создан и сохранен в БД: binance_id={tp_binance_id}, price={tp_price:.2f}, amount={cycle.total_base_qty}")

        next_index = db_order.order_index + 1
        stmt = select(Order).where(
            Order.cycle_id == cycle.id,
            Order.order_index == next_index
        )
        res = await self.session.execute(stmt)
        next_order = res.scalar_one_or_none()

        if next_order:
            next_safe_amount = await self.utils.round_amount(config.symbol, next_order.amount)
            next_safe_price = await self.utils.round_price(config.symbol, next_order.price)
            
            if not await self.utils.check_min_notional(config.symbol, next_safe_amount, next_safe_price):
                logger.warning(f"[OrderHandler] Next order too small (amount={next_safe_amount}, price={next_safe_price}), skipping")
            else:
                next_binance_res = await self.exchange.create_order(
                    symbol=config.symbol,
                    type='limit',
                    side='buy',
                    amount=next_safe_amount,
                    price=next_safe_price
                )
                next_order.binance_order_id = str(next_binance_res['id'])
                next_order.status = OrderStatus.ACTIVE
                logger.info(f"[OrderHandler] Следующий ордер создан: binance_id={next_order.binance_order_id}, order_id={next_order.id}")

    async def _handle_tp_fill(self, db_order, cycle, config, binance_order: dict):
        logger.info(f"[OrderHandler] Обработка исполнения TP ордера {db_order.binance_order_id}")
        
        db_order.status = OrderStatus.FILLED
        cycle.status = CycleStatus.CLOSED
        cycle.closed_at = datetime.utcnow()

        stmt = select(Order).where(
            Order.cycle_id == cycle.id,
            Order.status == OrderStatus.ACTIVE,
            Order.order_type == "BUY_SAFETY"
        )
        res = await self.session.execute(stmt)
        active_buys = res.scalars().all()

        for buy_order in active_buys:
            try:
                await self.exchange.cancel_order(buy_order.binance_order_id, config.symbol)
                buy_order.status = OrderStatus.CANCELED
            except Exception as e:
                logger.warning(f"Не удалось отменить buy-ордер {buy_order.binance_order_id}: {e}")

        final_sell_price = Decimal(str(binance_order.get('price') or db_order.price))
        final_sell_amount = Decimal(str(binance_order.get('amount') or db_order.amount))
        
        total_received = final_sell_price * final_sell_amount
        total_spent = Decimal(str(cycle.total_quote_spent or 0.0))
        
        profit = float(total_received - total_spent)
        cycle.profit_usdt = profit

        logger.info(f"Цикл {cycle.id} успешно закрыт с профитом {profit:.2f} USDT!")

        from app.domain.bot_manager import BotManager
        
        manager = BotManager(self.session)
        await manager.start_first_cycle(config)
