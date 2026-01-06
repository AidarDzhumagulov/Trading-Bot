import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
from app.core.logging import logger


class DumpDetector:
    """
    Детектор резкого падения цены (dump)

    Отслеживает историю цен и определяет:
    - Скорость падения (% в секунду)
    - Резкие падения (> 2% за 30 секунд)
    """

    def __init__(self, max_history: int = 12):
        self.price_history = []
        self.max_history = max_history

    def add_price(self, price: float):
        """Добавляет цену в историю"""
        self.price_history.append((time.time(), price))

        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)

    def detect_rapid_drop(self, threshold_pct: float = 2.0) -> bool:
        """
        Определяет резкое падение

        Returns: True если падение > threshold_pct за последние 30 секунд
        """
        if len(self.price_history) < 6:
            return False

        price_30s_ago = self.price_history[-6][1]
        current_price = self.price_history[-1][1]

        drop_pct = ((price_30s_ago - current_price) / price_30s_ago) * 100

        return drop_pct > threshold_pct

    def get_drop_velocity(self) -> float:
        """
        Возвращает скорость падения в % в секунду
        """
        if len(self.price_history) < 2:
            return 0.0

        time_diff = self.price_history[-1][0] - self.price_history[0][0]
        if time_diff == 0:
            return 0.0

        price_start = self.price_history[0][1]
        price_end = self.price_history[-1][1]

        price_change_pct = ((price_end - price_start) / price_start) * 100
        velocity = price_change_pct / time_diff

        return velocity

    def clear(self):
        """Очистка истории"""
        self.price_history.clear()


class TrailingTPManager:
    """
    Production-ready менеджер для Trailing Take Profit

    Включает:
    - Activation confirmation (3 тика или +0.2%)
    - Rate limiting (10s между обновлениями)
    - Emergency exit monitor
    - Market order при dump
    - Adaptive callback (based on ATR)
    - Safe order status check
    """

    def __init__(self, exchange, config):
        self.exchange = exchange
        self.config = config

        self.callback_pct = float(config.trailing_callback_pct or 0.8)
        self.min_profit_pct = float(config.trailing_min_profit_pct or 1.0)

        self._last_update_time = {}
        self.min_update_interval = 10

        self.dump_detector = DumpDetector()

        self._tp_touch_counts = {}
        self._tp_touch_times = {}

        self._last_atr_calc = 0
        self._cached_atr = None

    def is_enabled(self) -> bool:
        """Проверка включен ли trailing"""
        return bool(self.config.trailing_enabled)

    async def should_activate(
        self, cycle, current_price: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Проверяет нужно ли активировать trailing (С ПОДТВЕРЖДЕНИЕМ!)

        Активируется только если:
        1. Trailing включен
        2. Еще не активирован
        3. Цена достигла TP
        4. ПОДТВЕРЖДЕНИЕ: 3 тика подряд ИЛИ цена > TP на 0.2%+

        Returns: (should_activate, starting_max_price)
        """
        if not self.is_enabled():
            return False, None

        if cycle.trailing_active:
            return False, None

        if not cycle.current_tp_price:
            return False, None

        tp_price = float(cycle.current_tp_price)

        if current_price >= tp_price:
            if cycle.id not in self._tp_touch_counts:
                self._tp_touch_counts[cycle.id] = 0
                self._tp_touch_times[cycle.id] = time.time()

            self._tp_touch_counts[cycle.id] += 1

            if self._tp_touch_counts[cycle.id] >= 3:
                logger.info(
                    f"Activation confirmed: {self._tp_touch_counts[cycle.id]} touches"
                )
                self._tp_touch_counts.pop(cycle.id, None)
                self._tp_touch_times.pop(cycle.id, None)
                return True, tp_price

            if current_price >= tp_price * 1.002:
                logger.info(
                    f"Activation confirmed: price +{((current_price / tp_price - 1) * 100):.2f}% above TP"
                )
                self._tp_touch_counts.pop(cycle.id, None)
                self._tp_touch_times.pop(cycle.id, None)

                return True, tp_price

            time_since_first_touch = time.time() - self._tp_touch_times[cycle.id]
            if time_since_first_touch > 30:
                logger.info(
                    f"Activation confirmed: timeout ({time_since_first_touch:.0f}s)"
                )
                self._tp_touch_counts.pop(cycle.id, None)
                self._tp_touch_times.pop(cycle.id, None)
                return True, current_price

            logger.debug(
                f"Activation pending: {self._tp_touch_counts[cycle.id]}/3 touches"
            )
            return False, None
        else:
            if cycle.id in self._tp_touch_counts:
                logger.debug("Цена упала ниже TP, сброс счетчика активации")
                self._tp_touch_counts.pop(cycle.id, None)
                self._tp_touch_times.pop(cycle.id, None)
            return False, None

    async def activate(
        self, cycle, current_price: float, starting_max_price: Optional[float] = None
    ):
        """
        Активирует trailing для цикла

        Args:
            starting_max_price: Используется при gap (обычно = TP price)
        """
        cycle.trailing_active = True
        cycle.trailing_activation_price = current_price
        cycle.trailing_activation_time = datetime.utcnow()

        if starting_max_price:
            cycle.max_price_tracked = starting_max_price
            logger.info(
                f"Gap detected: starting max set to {starting_max_price:.2f} "
                f"(current price: {current_price:.2f})"
            )
        else:
            cycle.max_price_tracked = current_price

        logger.info(
            f"Trailing TP ACTIVATED for cycle {cycle.id}:\n"
            f"   Activation price: {current_price:.2f} USDT\n"
            f"   Starting max: {cycle.max_price_tracked:.2f} USDT\n"
            f"   Callback: {self.callback_pct}%\n"
            f"   Min profit protection: {self.min_profit_pct}%"
        )

        self.dump_detector.clear()
        self.dump_detector.add_price(current_price)

    async def calculate_atr(self, symbol: str, period: int = 14) -> float:
        """
        Рассчитывает Average True Range (волатильность)

        Returns: ATR в процентах от цены
        """
        try:
            if self._cached_atr and (time.time() - self._last_atr_calc) < 300:
                return self._cached_atr

            ohlcv = await self.exchange.fetch_ohlcv(
                symbol, timeframe="5m", limit=period + 1
            )

            if len(ohlcv) < period + 1:
                logger.warning(f"Not enough candles for ATR: {len(ohlcv)}")
                return 2.0

            true_ranges = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i - 1][4]

                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                true_ranges.append(tr)

            atr = sum(true_ranges) / len(true_ranges)
            current_price = ohlcv[-1][4]
            atr_pct = (atr / current_price) * 100

            self._cached_atr = atr_pct
            self._last_atr_calc = time.time()

            logger.debug(f"ATR calculated: {atr_pct:.2f}%")
            return atr_pct

        except Exception as e:
            logger.error(f"Failed to calculate ATR: {e}")
            return 2.0

    async def get_adaptive_callback(self, symbol: str) -> float:
        """
        Возвращает адаптивный callback на основе волатильности

        Логика:
        - ATR > 5%: callback × 2.0 (очень волатильно)
        - ATR > 3%: callback × 1.5 (волатильно)
        - ATR < 1%: callback × 0.7 (спокойно)
        - Иначе: base callback
        """
        atr_pct = await self.calculate_atr(symbol)
        base_callback = self.callback_pct

        if atr_pct > 5.0:
            adaptive = base_callback * 2.0
            logger.info(
                f"Высокая волатильность (ATR: {atr_pct:.2f}%), "
                f"используем более широкий callback: {adaptive:.2f}%"
            )
        elif atr_pct > 3.0:
            adaptive = base_callback * 1.5
            logger.info(
                f"Средняя волатильность (ATR: {atr_pct:.2f}%), "
                f"callback: {adaptive:.2f}%"
            )
        elif atr_pct < 1.0:
            adaptive = base_callback * 0.7
            logger.debug(
                f"Низкая волатильность (ATR: {atr_pct:.2f}%), "
                f"более узкий callback: {adaptive:.2f}%"
            )
        else:
            adaptive = base_callback

        return adaptive

    def update_max_price(self, cycle, current_price: float) -> bool:
        """
        Обновляет максимальную цену если нужно

        Returns: True если максимум обновлен
        """
        if not cycle.trailing_active:
            return False

        current_max = float(cycle.max_price_tracked or 0)

        if current_price > current_max:
            old_max = current_max
            cycle.max_price_tracked = current_price

            improvement_pct = (
                ((current_price - old_max) / old_max * 100) if old_max > 0 else 0
            )

            logger.info(
                f"Новая максимальная цена для цикла {cycle.id}: "
                f"{old_max:.2f} → {current_price:.2f} USDT "
                f"(+{improvement_pct:.2f}%)"
            )

            return True

        return False

    def calculate_callback_price(
        self, max_price: float, callback_pct: Optional[float] = None
    ) -> float:
        """
        Рассчитывает цену для продажи на основе callback
        """
        if callback_pct is None:
            callback_pct = self.callback_pct

        callback_multiplier = 1 - (callback_pct / 100)
        return max_price * callback_multiplier

    def calculate_min_profit_price(self, cycle) -> float:
        """
        Рассчитывает минимальную цену продажи для защиты прибыли

        Использует ADAPTIVE подход:
        - Если effective TP был высокий (4%+) → min_profit = 66% от TP
        - Если effective TP был низкий (2%) → min_profit = 66% от TP
        """
        if not cycle.avg_price or not cycle.current_tp_price:
            return 0

        effective_tp_pct = (
            (float(cycle.current_tp_price) / float(cycle.avg_price)) - 1
        ) * 100

        adaptive_min_profit_pct = effective_tp_pct * 0.66

        final_min_profit_pct = max(adaptive_min_profit_pct, self.min_profit_pct)

        return float(cycle.avg_price) * (1 + final_min_profit_pct / 100)

    async def should_exit(
        self, cycle, current_price: float, symbol: str
    ) -> Tuple[bool, float, str]:
        """
        Проверяет нужно ли продать

        Returns: (should_exit, exit_price, reason)
        """
        if not cycle.trailing_active:
            return False, 0, "Trailing not active"

        if not cycle.max_price_tracked:
            return False, 0, "No max price tracked"

        adaptive_callback = await self.get_adaptive_callback(symbol)

        callback_price = self.calculate_callback_price(
            float(cycle.max_price_tracked), adaptive_callback
        )

        min_profit_price = self.calculate_min_profit_price(cycle)

        final_exit_price = max(callback_price, min_profit_price)

        if current_price <= final_exit_price:
            if (
                final_exit_price == min_profit_price
                and min_profit_price > callback_price
            ):
                reason = f"Min profit protection ({self.min_profit_pct}%)"
            else:
                reason = f"Callback triggered ({adaptive_callback:.2f}% from max)"

            max_tracked = float(cycle.max_price_tracked)
            drawdown_from_max = (max_tracked - current_price) / max_tracked * 100
            profit_from_entry = (
                ((current_price / cycle.avg_price - 1) * 100) if cycle.avg_price else 0
            )

            logger.info(
                f"Trailing EXIT triggered for cycle {cycle.id}:\n"
                f"   Current price: {current_price:.2f} USDT\n"
                f"   Callback price: {callback_price:.2f} USDT (adaptive: {adaptive_callback:.2f}%)\n"
                f"   Min profit price: {min_profit_price:.2f} USDT\n"
                f"   Final exit price: {final_exit_price:.2f} USDT\n"
                f"   Max tracked: {max_tracked:.2f} USDT\n"
                f"   Drawdown from max: {drawdown_from_max:.2f}%\n"
                f"   Profit from entry: {profit_from_entry:.2f}%\n"
                f"   Reason: {reason}"
            )

            return True, final_exit_price, reason

        return False, 0, "Price above exit threshold"

    async def monitor_emergency_exit(
        self, cycle, current_price: float, session
    ) -> bool:
        """
        КРИТИЧНАЯ ФУНКЦИЯ: Мониторинг аварийного выхода

        Проверяется при КАЖДОМ обновлении цены

        Триггеры:
        1. Цена упала на 0.5% ниже min_profit
        2. Dump detected (падение > 2% за 30 секунд)

        Returns: True если был emergency exit
        """
        if not cycle.trailing_active:
            return False

        self.dump_detector.add_price(current_price)

        min_profit_price = self.calculate_min_profit_price(cycle)
        emergency_threshold = min_profit_price * 0.995

        if current_price < emergency_threshold:
            loss_pct = (
                ((current_price / cycle.avg_price - 1) * 100) if cycle.avg_price else 0
            )

            logger.error(
                f"EMERGENCY EXIT TRIGGER #1: Price below min profit!\n"
                f"   Current: {current_price:.2f} USDT\n"
                f"   Min profit: {min_profit_price:.2f} USDT\n"
                f"   Threshold: {emergency_threshold:.2f} USDT\n"
                f"   Current loss: {loss_pct:.2f}%"
            )

            success = await self.emergency_market_sell(
                cycle, session, "Below min_profit"
            )
            return success

        if self.dump_detector.detect_rapid_drop(threshold_pct=2.0):
            velocity = self.dump_detector.get_drop_velocity()

            logger.error(
                f"EMERGENCY EXIT TRIGGER #2: DUMP DETECTED!\n"
                f"   Drop velocity: {velocity:.3f}%/second\n"
                f"   Current price: {current_price:.2f} USDT\n"
                f"   Max tracked: {cycle.max_price_tracked:.2f} USDT"
            )

            success = await self.emergency_market_sell(cycle, session, "Dump detected")
            return success

        return False

    async def emergency_market_sell(self, cycle, session, reason: str) -> bool:
        """
        Выполняет НЕМЕДЛЕННУЮ продажу по рынку

        Шаги:
        1. Отменяет все активные ордера
        2. Продает ВСЁ по market order
        3. Помечает в БД

        Returns: True если успешно
        """
        try:
            logger.error(f"ВЫПОЛНЕНИЕ АВАРИЙНОЙ ПРОДАЖИ ПО РЫНКУ: {reason}")

            if cycle.current_tp_order_id:
                try:
                    await self.exchange.cancel_order(
                        cycle.current_tp_order_id, self.config.symbol
                    )
                    logger.info(f"Отменен TP-ордер: {cycle.current_tp_order_id}")
                except Exception as e:
                    logger.warning(
                        f"Не удалось отменить TP (возможно уже исполнен): {e}"
                    )

            balance = await self.exchange.fetch_free_balance()
            base_asset = self.config.symbol.split("/")[0]
            available = balance.get(base_asset, 0)

            if available <= 0:
                logger.error(f"Нет доступного {base_asset} для аварийной продажи!")
                return False

            logger.info(f"Доступно для аварийной продажи: {available:.8f} {base_asset}")

            order = await self.exchange.create_order(
                symbol=self.config.symbol, type="market", side="sell", amount=available
            )

            logger.info(
                f"АВАРИЙНАЯ ПРОДАЖА ПО РЫНКУ ЗАВЕРШЕНА:\n"
                f"   Order ID: {order['id']}\n"
                f"   Количество: {available:.8f} {base_asset}\n"
                f"   Средняя цена: ~{order.get('average', 'N/A')} USDT\n"
                f"   Причина: {reason}"
            )

            cycle.emergency_exit = True
            cycle.emergency_exit_reason = reason
            cycle.emergency_exit_time = datetime.utcnow()

            return True

        except Exception as e:
            logger.error(f"АВАРИЙНАЯ ПРОДАЖА НЕ УДАЛАСЬ: {e}", exc_info=True)
            return False

    async def can_update_tp(self, cycle_id) -> bool:
        """
        Проверяет можно ли обновить TP (rate limiting)

        Returns: True если прошло достаточно времени
        """
        last_update = self._last_update_time.get(cycle_id, 0)
        time_since_update = time.time() - last_update

        if time_since_update < self.min_update_interval:
            logger.debug(
                f"Обновление TP ограничено по частоте: "
                f"{time_since_update:.1f}s < {self.min_update_interval}s"
            )
            return False

        return True

    async def is_order_still_open(self, order_id: str, symbol: str) -> bool:
        """
        Проверяет что ордер еще активен (защита от race condition)

        Returns: True если ордер активен
        """
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            status = order.get("status", "").lower()

            if status in ["closed", "filled", "canceled"]:
                logger.info(
                    f"Ордер {order_id} имеет статус {status}, пропускаем обновление"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"Could not fetch order status: {e}")
            return False

    async def create_or_update_tp_order(
        self, cycle, new_tp_price: float, amount: float, symbol: str, session
    ) -> bool:
        """
        Создает или обновляет TP ордер с защитой от race conditions

        Returns: True если успешно
        """
        try:
            if not await self.can_update_tp(cycle.id):
                return False

            if cycle.current_tp_order_id:
                if not await self.is_order_still_open(
                    cycle.current_tp_order_id, symbol
                ):
                    logger.info("Old TP order already processed, skipping update")
                    return False

            if cycle.current_tp_order_id:
                try:
                    await self.exchange.cancel_order(cycle.current_tp_order_id, symbol)
                    logger.info(f"Отменен старый TP: {cycle.current_tp_order_id}")
                except Exception as e:
                    logger.warning(f"Не удалось отменить старый TP: {e}")

            new_tp_order = await self.exchange.create_order(
                symbol=symbol,
                type="limit",
                side="sell",
                amount=amount,
                price=new_tp_price,
            )

            cycle.current_tp_order_id = str(new_tp_order["id"])
            cycle.current_tp_price = new_tp_price

            expected_revenue = amount * new_tp_price
            expected_profit = expected_revenue - float(cycle.total_quote_spent)
            expected_profit_pct = (
                (expected_profit / float(cycle.total_quote_spent) * 100)
                if cycle.total_quote_spent
                else 0
            )

            logger.info(
                f"TP-ордер обновлен через trailing:\n"
                f"   Order ID: {new_tp_order['id']}\n"
                f"   Цена: {new_tp_price:.2f} USDT\n"
                f"   Количество: {amount:.8f}\n"
                f"   Ожидаемая прибыль: {expected_profit:.2f} USDT ({expected_profit_pct:.2f}%)"
            )

            await session.commit()

            self._last_update_time[cycle.id] = time.time()

            return True

        except Exception as e:
            logger.error(f"Не удалось обновить TP-ордер: {e}", exc_info=True)
            return False

    def get_trailing_stats(self, cycle) -> Optional[dict]:
        """
        Возвращает статистику trailing для цикла
        """
        if not cycle.trailing_active:
            return None

        stats = {
            "active": True,
            "activation_price": float(cycle.trailing_activation_price or 0),
            "activation_time": (
                cycle.trailing_activation_time.isoformat()
                if cycle.trailing_activation_time
                else None
            ),
            "max_price_tracked": float(cycle.max_price_tracked or 0),
            "callback_pct": self.callback_pct,
            "min_profit_pct": self.min_profit_pct,
        }

        if cycle.max_price_tracked and cycle.trailing_activation_price:
            max_growth = (
                cycle.max_price_tracked / cycle.trailing_activation_price - 1
            ) * 100
            stats["max_growth_from_activation"] = max_growth

        return stats
