from typing import Optional

from app.core.logging import logger
from app.domain.constants import BalanceThresholds
from app.domain.exceptions import InsufficientBalanceError, BalanceDeviationError
from app.domain.value_objects import BalanceCheckResult


class BalanceValidator:
    """
    Validates available balance against expected amounts.

    Handles:
    - Zero balance checks
    - Critical deviation detection
    - Safe amount determination for selling
    """

    def __init__(self, exchange):
        self.exchange = exchange

    async def validate_for_sell(
        self, symbol: str, expected_amount: float
    ) -> BalanceCheckResult:
        """
        Validate balance and determine safe amount to sell.

        Args:
            symbol: Trading pair symbol
            expected_amount: Expected base asset quantity

        Returns:
            BalanceCheckResult with validation status and amount

        Raises:
            InsufficientBalanceError: When no balance available
            BalanceDeviationError: When deviation is critical
        """
        base_asset = symbol.split("/")[0]

        balance = await self.exchange.fetch_free_balance()
        available = balance.get(base_asset, 0.0)

        logger.info(
            f"[BalanceValidator] Проверка баланса: "
            f"доступно={available:.8f} {base_asset}, "
            f"ожидается={expected_amount:.8f} {base_asset}"
        )

        if available <= 0:
            raise InsufficientBalanceError(
                f"Нет доступного {base_asset} для продажи",
                details={
                    "asset": base_asset,
                    "available": available,
                    "expected": expected_amount,
                },
            )

        deviation_pct = self._calculate_deviation(available, expected_amount)
        warning = self._check_deviation_warning(
            deviation_pct, available, expected_amount
        )

        amount_to_sell = self._determine_sell_amount(
            available=available, expected=expected_amount, deviation_pct=deviation_pct
        )

        if amount_to_sell <= 0:
            raise InsufficientBalanceError(
                "Рассчитанное количество для продажи равно нулю",
                details={"available": available, "expected": expected_amount},
            )

        return BalanceCheckResult(
            available=available,
            expected=expected_amount,
            amount_to_sell=amount_to_sell,
            deviation_pct=deviation_pct,
            is_valid=True,
            warning=warning,
        )

    def _calculate_deviation(self, available: float, expected: float) -> float:
        """Calculate percentage deviation from expected"""
        if expected <= 0:
            return 0.0

        deviation = available - expected
        deviation_pct = abs(deviation) / expected * 100

        logger.info(
            f"[BalanceValidator] Отклонение: {deviation:+.8f} ({deviation_pct:.2f}%)"
        )

        return deviation_pct

    def _check_deviation_warning(
        self, deviation_pct: float, available: float, expected: float
    ) -> Optional[str]:
        """Check if deviation requires warning or error"""

        if deviation_pct > BalanceThresholds.CRITICAL_DEVIATION_PCT:
            raise BalanceDeviationError(
                f"Критическое несоответствие баланса: {deviation_pct:.2f}%",
                details={
                    "available": available,
                    "expected": expected,
                    "deviation_pct": deviation_pct,
                    "threshold": BalanceThresholds.CRITICAL_DEVIATION_PCT,
                    "possible_causes": [
                        "Ручной вывод/пополнение",
                        "Несколько ботов на одном аккаунте",
                        "Ошибка данных API",
                    ],
                },
            )

        if deviation_pct > BalanceThresholds.WARNING_DEVIATION_PCT:
            warning = (
                f"Умеренное несоответствие баланса: {deviation_pct:.2f}%. "
                f"Используем консервативный подход."
            )
            logger.warning(f"[BalanceValidator] {warning}")
            return warning

        return None

    def _determine_sell_amount(
        self, available: float, expected: float, deviation_pct: float
    ) -> float:
        """Determine safe amount to sell based on balance check"""

        if expected <= 0:
            logger.warning(
                "[BalanceValidator] Нет ожидаемого количества в БД, "
                "используем доступный баланс"
            )
            return available

        is_exact_match = deviation_pct < BalanceThresholds.EXACT_MATCH_THRESHOLD_PCT

        if is_exact_match:
            logger.info(f"[BalanceValidator] Используем точный баланс: {available:.8f}")
            return available

        if available < expected:
            dust_lost = expected - available
            logger.warning(
                f"[BalanceValidator] Баланс ниже ожидаемого. "
                f"Продаем: {available:.8f}, Потеряно пыли: {dust_lost:.8f}"
            )
            return available

        logger.warning(
            f"[BalanceValidator] Баланс выше ожидаемого. "
            f"Используем ожидаемое количество: {expected:.8f}"
        )
        return expected
