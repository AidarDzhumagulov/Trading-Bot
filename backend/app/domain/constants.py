from decimal import Decimal


class BalanceThresholds:
    """Thresholds for balance validation"""

    CRITICAL_DEVIATION_PCT = 5.0
    WARNING_DEVIATION_PCT = 1.0
    EXACT_MATCH_THRESHOLD_PCT = 0.1


class FeeDefaults:
    """Default fee rates when exchange data unavailable"""

    FALLBACK_FEE_RATE = Decimal("0.001")
    ESTIMATED_TOTAL_FEE_RATE = 0.002


class TakeProfitDefaults:
    """Take profit calculation constants"""

    MIN_TP_PCT = 0.5
    SAFETY_MARGIN_MULTIPLIER = 1.5
    MIN_PROFIT_CHECK_RATIO = 0.5
