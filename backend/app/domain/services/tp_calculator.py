from decimal import Decimal

from app.core.logging import logger
from app.domain.constants import FeeDefaults, TakeProfitDefaults
from app.domain.value_objects import TakeProfitParams, CycleStats
from app.shared.exchange_helper import TradingUtils


class TakeProfitCalculator:
    """
    Calculates adaptive take profit price.

    Ensures TP covers:
    - Trading fees (buy + sell)
    - Precision loss from rounding
    - User-configured profit target
    """

    def __init__(self, exchange):
        self.exchange = exchange
        self.utils = TradingUtils(exchange)

    async def calculate(
        self,
        cycle_stats: CycleStats,
        config_tp_pct: float,
        symbol: str,
        amount_precision: int,
    ) -> TakeProfitParams:
        """
        Calculate adaptive take profit parameters.

        The effective TP is the maximum of:
        - User configured TP
        - Minimum profitable TP (covers fees + precision loss)

        Args:
            cycle_stats: Current cycle statistics
            config_tp_pct: User configured take profit %
            symbol: Trading pair symbol
            amount_precision: Exchange amount precision

        Returns:
            TakeProfitParams with effective TP price and percentages
        """
        step_size = (
            1.0 / (10**amount_precision)
            if isinstance(amount_precision, int)
            else 0.0001
        )

        avg_price_float = float(cycle_stats.avg_price)
        safe_price_for_calc = await self.utils.round_price(symbol, avg_price_float)

        max_precision_loss_usd = step_size * safe_price_for_calc

        total_quote_spent = float(cycle_stats.total_quote_spent)
        total_fees_usd = total_quote_spent * FeeDefaults.ESTIMATED_TOTAL_FEE_RATE

        total_overhead_usd = max_precision_loss_usd + total_fees_usd

        if total_quote_spent > 0:
            min_tp_pct = (total_overhead_usd / total_quote_spent) * 100
        else:
            min_tp_pct = TakeProfitDefaults.MIN_TP_PCT

        safe_tp_pct = min_tp_pct * TakeProfitDefaults.SAFETY_MARGIN_MULTIPLIER

        effective_tp_pct = max(config_tp_pct, safe_tp_pct)

        tp_price_decimal = cycle_stats.avg_price * (
            Decimal("1") + Decimal(str(effective_tp_pct)) / Decimal("100")
        )
        tp_price = await self.utils.round_price(symbol, float(tp_price_decimal))

        logger.info(
            f"[TPCalculator] Расчет адаптивного TP: "
            f"потеря_точности={max_precision_loss_usd:.4f} USDT, "
            f"комиссии={total_fees_usd:.4f} USDT, "
            f"общие_накладные={total_overhead_usd:.4f} USDT"
        )

        logger.info(
            f"[TPCalculator] Уровни TP: "
            f"мин_безубыточность={min_tp_pct:.2f}%, "
            f"безопасный_tp={safe_tp_pct:.2f}%, "
            f"пользовательский_tp={config_tp_pct:.2f}%, "
            f"эффективный_tp={effective_tp_pct:.2f}%"
        )

        return TakeProfitParams(
            effective_tp_pct=effective_tp_pct,
            tp_price=tp_price,
            min_tp_pct=min_tp_pct,
            overhead_usd=total_overhead_usd,
        )
