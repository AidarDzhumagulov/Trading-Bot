import asyncio
import math
from decimal import Decimal
from datetime import datetime
import ccxt

from sqlalchemy import select, update

from app.infrastructure.persistence.sqlalchemy.models import Order, DcaCycle, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.shared.exchange_helper import TradingUtils
from app.core.logging import logger
from app.domain.bot_manager import BotManager
from app.shared.websocket_registry import websocket_registry


class OrderHandler:
    def __init__(self, session, exchange):
        self.session = session
        self.exchange = exchange
        self.utils = TradingUtils(exchange)

    async def handle_filled_order(self, binance_order: dict):
        binance_id = str(binance_order['id'])
        logger.info(f"[OrderHandler] Обработка ордера {binance_id}")

        stmt = (
            select(Order)
            .where(Order.binance_order_id == binance_id)
            .with_for_update()  # Сделал изза рейс кондишона
        )
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
            logger.info(f"[OrderHandler] Ордер {binance_id} уже обработан другой задачей (status=filled)")
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
        
        order_cost = Decimal(str(binance_order.get('cost', db_order.price * float(filled_qty))))
        new_quote_spent = current_quote_spent + order_cost
        
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

        base_asset = config.symbol.split('/')[0]
        
        try:
            balance = await self.exchange.fetch_free_balance()
            available_base = balance.get(base_asset, 0.0)
            
            expected_amount = float(cycle.total_base_qty)
            
            logger.info(
                f"[OrderHandler] Проверка баланса: "
                f"доступно={available_base:.8f} {base_asset}, "
                f"ожидается={expected_amount:.8f} {base_asset}"
            )
            
            if available_base <= 0:
                logger.error(
                    f"[OrderHandler] Нет доступного {base_asset} для TP-ордера. "
                    f"Ожидается: {expected_amount:.8f}, Доступно: {available_base:.8f}"
                )
                return
            
            if expected_amount > 0:
                deviation = available_base - expected_amount
                deviation_pct = abs(deviation) / expected_amount * 100
                
                logger.info(f"[OrderHandler] Отклонение баланса: {deviation:+.8f} {base_asset} ({deviation_pct:.2f}%)")
                
                if deviation_pct > 5.0:
                    logger.error(
                        f"[OrderHandler] КРИТИЧЕСКОЕ несоответствие баланса! "
                        f"Доступно: {available_base:.8f}, Ожидается: {expected_amount:.8f}, "
                        f"Отклонение: {deviation_pct:.2f}% (порог: 5.0%)"
                    )
                    logger.error(
                        f"[OrderHandler] Возможные причины: "
                        f"1) Ручной вывод/пополнение, "
                        f"2) Несколько ботов на одном аккаунте, "
                        f"3) Ошибка данных API"
                    )
                    return
                
                elif deviation_pct > 1.0:
                    logger.warning(
                        f"[OrderHandler] Обнаружено умеренное несоответствие баланса "
                        f"(отклонение: {deviation_pct:.2f}%). Используем консервативный подход."
                    )
            
            if expected_amount > 0:
                if abs(available_base - expected_amount) / expected_amount < 0.001:  # <0.1%
                    amount_to_sell = available_base
                    logger.info(f"[OrderHandler] Используем точный баланс: {amount_to_sell:.8f} {base_asset}")
                
                elif available_base < expected_amount:
                    amount_to_sell = available_base
                    dust_lost = expected_amount - available_base
                    logger.warning(
                        f"[OrderHandler] Баланс ниже ожидаемого. "
                        f"Продаем: {amount_to_sell:.8f}, Потеряно пыли: {dust_lost:.8f} {base_asset}"
                    )
                
                else:
                    amount_to_sell = expected_amount
                    logger.warning(
                        f"[OrderHandler] Баланс выше ожидаемого. "
                        f"Используем ожидаемое количество для безопасности: {amount_to_sell:.8f} {base_asset}"
                    )
            else:
                amount_to_sell = available_base
                logger.warning(f"[OrderHandler] Нет ожидаемого количества в БД, используем доступный баланс")
            
            if amount_to_sell <= 0:
                logger.error(f"[OrderHandler] Финальное количество равно нулю или отрицательное: {amount_to_sell:.8f}")
                return

            accumulated_dust = float(cycle.accumulated_dust or 0.0)
            total_with_dust = amount_to_sell + accumulated_dust

            logger.info(
                f"[OrderHandler] Накопление пыли: "
                f"текущее={amount_to_sell:.8f}, "
                f"накоплено={accumulated_dust:.8f}, "
                f"всего={total_with_dust:.8f} {base_asset}"
            )

            market = await self.utils.get_market(config.symbol)
            amount_precision = market.get('precision', {}).get('amount', 8)

            if isinstance(amount_precision, int):
                factor = 10 ** amount_precision
                final_amount = math.floor(total_with_dust * factor) / factor
            else:
                final_amount = float(self.exchange.amount_to_precision(config.symbol, total_with_dust))

            new_dust = total_with_dust - final_amount
            cycle.accumulated_dust = new_dust

            logger.info(
                f"[OrderHandler] После округления: "
                f"sellable={final_amount:.8f}, "
                f"new_dust={new_dust:.8f} {base_asset} "
                f"(будет добавлено к следующему циклу)"
            )

            if final_amount <= 0:
                logger.error(f"[OrderHandler] Финальное количество после округления равно нулю: {final_amount:.8f}")
                return

            step_size = 1.0 / factor if isinstance(amount_precision, int) else 0.0001
            max_precision_loss_amount = step_size

            current_price = float(avg_price)
            safe_price_for_calc = await self.utils.round_price(config.symbol, current_price)

            max_precision_loss_usd = max_precision_loss_amount * safe_price_for_calc

            total_fees_usd = float(cycle.total_quote_spent) * 0.002

            total_overhead_usd = max_precision_loss_usd + total_fees_usd

            if float(cycle.total_quote_spent) > 0:
                min_tp_pct = (total_overhead_usd / float(cycle.total_quote_spent)) * 100
            else:
                min_tp_pct = 0.5

            safe_tp_pct = min_tp_pct * 1.5

            effective_tp_pct = max(float(config.take_profit_pct), safe_tp_pct)

            logger.info(
                f"[OrderHandler] Расчет адаптивного TP: "
                f"потеря_точности={max_precision_loss_usd:.4f} USDT, "
                f"комиссии={total_fees_usd:.4f} USDT, "
                f"общие_накладные={total_overhead_usd:.4f} USDT"
            )

            logger.info(
                f"[OrderHandler] Уровни TP: "
                f"мин_безубыточность={min_tp_pct:.2f}%, "
                f"безопасный_tp={safe_tp_pct:.2f}%, "
                f"пользовательский_tp={config.take_profit_pct:.2f}%, "
                f"эффективный_tp={effective_tp_pct:.2f}%"
            )

            tp_price_adaptive = avg_price * (Decimal("1") + Decimal(str(effective_tp_pct)) / Decimal("100"))
            safe_price = await self.utils.round_price(config.symbol, float(tp_price_adaptive))
            
            notional_value = final_amount * safe_price
            if not await self.utils.check_min_notional(config.symbol, final_amount, safe_price):
                logger.warning(
                    f"[OrderHandler] TP ниже минимальной суммы. "
                    f"Количество: {final_amount:.8f}, Цена: {safe_price:.2f}, "
                    f"Сумма: {notional_value:.2f} USDT"
                )
                return

            logger.info(
                f"[OrderHandler] Создание TP-ордера: "
                f"количество={final_amount:.8f} {base_asset}, "
                f"цена={safe_price:.2f} USDT (TP: {effective_tp_pct:.2f}%), "
                f"сумма={notional_value:.2f} USDT"
            )
            
            tp_res = await self.exchange.create_order(
                symbol=config.symbol,
                type='limit',
                side='sell',
                amount=final_amount,
                price=safe_price
            )
            
            logger.info(
                f"[OrderHandler] TP-ордер успешно создан: "
                f"order_id={tp_res['id']}, "
                f"количество={final_amount:.8f} {base_asset}, "
                f"цена={safe_price:.2f} USDT, "
                f"effective_tp={effective_tp_pct:.2f}%, "
                f"expected_profit={(notional_value - float(cycle.total_quote_spent)):.2f} USDT"
            )
            
        except ccxt.NetworkError as e:
            logger.error(f"[OrderHandler] Ошибка сети при создании TP: {e}")
            return
            
        except ccxt.InsufficientFunds as e:
            logger.error(
                f"[OrderHandler] Ошибка недостаточных средств: {e}. "
                f"Этого не должно происходить при проверке баланса!"
            )
            return

        except ccxt.InvalidOrder as e:
            logger.error(f"[OrderHandler] Ошибка невалидного ордера: {e}")
            return

        except Exception as e:
            logger.error(f"[OrderHandler] Неожиданная ошибка при создании TP: {e}", exc_info=True)
            return

        tp_binance_id = str(tp_res['id'])
        cycle.current_tp_order_id = tp_binance_id

        new_tp_order = Order(
            cycle_id=cycle.id,
            binance_order_id=tp_binance_id,
            order_type="SELL_TP",
            order_index=-1,
            price=safe_price,
            amount=final_amount,
            status=OrderStatus.ACTIVE
        )
        self.session.add(new_tp_order)
        logger.info(
            f"[OrderHandler] TP-ордер создан и сохранен в БД: "
            f"binance_id={tp_binance_id}, "
            f"price={safe_price:.2f}, "
            f"amount={final_amount:.8f}, "
            f"effective_tp={effective_tp_pct:.2f}%"
        )

        next_index = db_order.order_index + 1
        stmt = (
            select(Order)
            .where(
                Order.cycle_id == cycle.id,
                Order.order_index == next_index,
                Order.order_type == 'BUY_SAFETY'
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        next_order = res.scalar_one_or_none()

        if next_order:
            next_safe_amount = await self.utils.round_amount(config.symbol, next_order.amount)
            next_safe_price = await self.utils.round_price(config.symbol, next_order.price)
            
            if not await self.utils.check_min_notional(config.symbol, next_safe_amount, next_safe_price):
                logger.warning(f"[OrderHandler] Следующий ордер слишком мал (количество={next_safe_amount}, цена={next_safe_price}), пропускаем")
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
        """Обработка исполнения TP-ордера (продажи) с корректным расчетом прибыли

        Важно: Комиссия при продаже должна быть вычтена из полученной суммы
        """
        db_order.status = OrderStatus.FILLED
        cycle.status = CycleStatus.CLOSED
        cycle.closed_at = datetime.utcnow()
        cycle.accumulated_dust = 0.0
        logger.info(f"[OrderHandler] Накопленная пыль сброшена до 0 для следующего цикла")
        active_orders = await self.session.execute(
            select(Order).where(
                Order.cycle_id == cycle.id,
                Order.status == OrderStatus.ACTIVE
            )
        )
        for order in active_orders.scalars():
            try:
                await self.exchange.cancel_order(order.binance_order_id, config.symbol)
                order.status = OrderStatus.CANCELED
            except Exception as e:
                logger.error(f"Не удалось отменить ордер {order.binance_order_id}: {e}")

        logger.info(f"Детали TP-ордера с биржи:")
        logger.info(f"  id: {binance_order.get('id')}")
        logger.info(f"  цена: {binance_order.get('price')}")
        logger.info(f"  количество: {binance_order.get('amount')}")
        logger.info(f"  стоимость: {binance_order.get('cost')}")
        logger.info(f"  комиссия: {binance_order.get('fee')}")
        logger.info(f"  цена ордера в БД: {db_order.price}")
        logger.info(f"  количество ордера в БД: {db_order.amount}")

        base_cost = Decimal(str(binance_order.get('cost', 0)))

        if base_cost == 0:
            price = Decimal(str(binance_order.get('price', db_order.price)))
            amount = Decimal(str(binance_order.get('amount', db_order.amount)))
            base_cost = price * amount
            logger.warning(f"Стоимость не предоставлена биржей, рассчитано: {base_cost}")

        fee_info = binance_order.get('fee', {})
        fee_cost = Decimal("0")

        if fee_info and isinstance(fee_info, dict):
            fee_currency = fee_info.get('currency', '').upper()

            if fee_currency == 'USDT' or fee_currency == 'USD':
                fee_cost = Decimal(str(fee_info.get('cost', 0)))
                logger.info(f"Комиссия при продаже с биржи: {fee_cost} USDT")
            else:
                logger.warning(f"Валюта комиссии {fee_currency} не USDT, используем 0.1%")
                fee_cost = base_cost * Decimal("0.001")
        else:
            fee_cost = base_cost * Decimal("0.001")
            logger.warning(f"Нет информации о комиссии с биржи, рассчитано 0.1%: {fee_cost}")

        total_received = base_cost - fee_cost

        total_spent = Decimal(str(cycle.total_quote_spent or 0.0))

        profit = float(total_received - total_spent)
        cycle.profit_usdt = profit

        expected_min_profit_pct = config.take_profit_pct * 0.5  # Минимум половина от TP
        actual_profit_pct = (profit / float(total_spent)) * 100 if total_spent > 0 else 0

        if actual_profit_pct < expected_min_profit_pct:
            logger.error(
                f"ОБНАРУЖЕНА АНОМАЛИЯ! Цикл {cycle.id} закрыт с подозрительно низкой прибылью: "
                f"прибыль={profit:.4f} USDT ({actual_profit_pct:.2f}%), "
                f"ожидалось минимум {expected_min_profit_pct:.2f}%"
            )
            logger.error(
                f"Детали: потрачено={float(total_spent):.4f}, "
                f"получено={float(total_received):.4f}, "
                f"средняя_цена={cycle.avg_price:.2f}, "
                f"tp_цена={db_order.price:.2f}"
            )

        logger.info(
            f"Цикл {cycle.id} закрыт: "
            f"получено={float(total_received):.2f} USDT "
            f"(брутто={float(base_cost):.2f}, комиссия={float(fee_cost):.4f}), "
            f"потрачено={float(total_spent):.2f} USDT, "
            f"прибыль={profit:.2f} USDT ({actual_profit_pct:.2f}%)"
        )

        await self.session.commit()
        old_ws_manager = websocket_registry.get(config.id)
        if old_ws_manager:
            logger.info(f"Остановка старого WebSocket менеджера для конфигурации {config.id}")
            await old_ws_manager.stop()
            await websocket_registry.remove(config.id)
            await asyncio.sleep(0.5)
            logger.info(f"Старый WebSocket менеджер остановлен")

        manager = BotManager(self.session)
        await manager.start_first_cycle(config)
        logger.info(f"Новый цикл запущен для конфигурации {config.id}")
