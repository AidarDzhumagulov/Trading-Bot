from decimal import Decimal, ROUND_DOWN
from typing import TypedDict, List
from dataclasses import dataclass


class GridOrder(TypedDict):
    """Typed dictionary for grid order structure."""
    index: int
    price: float
    amount_usdt: float
    amount_base: float


@dataclass(frozen=True)
class GridConfig:
    """Immutable configuration for grid calculation.

    All percentage values should be in range 0-100 (e.g., 5.0 for 5%).
    """
    current_price: float
    total_budget: float
    grid_levels: int
    grid_length_pct: float
    first_step_pct: float
    volume_scale_pct: float
    amount_precision: int = 4
    price_precision: int = 2

    def __post_init__(self):
        """Validate configuration on initialization."""
        if self.current_price <= 0:
            raise ValueError("current_price must be positive")
        if self.total_budget <= 0:
            raise ValueError("total_budget must be positive")
        if self.grid_levels < 1:
            raise ValueError("grid_levels must be at least 1")
        if not 0 <= self.grid_length_pct <= 100:
            raise ValueError("grid_length_pct must be between 0 and 100")
        if not 0 <= self.first_step_pct <= 100:
            raise ValueError("first_step_pct must be between 0 and 100")
        if self.volume_scale_pct < 0:
            raise ValueError("volume_scale_pct cannot be negative")


class GridCalculator:
    """
    Calculates DCA grid orders with configurable parameters.

    The grid strategy places orders below current price with:
    - First order offset from current price
    - Exponentially increasing volumes (martingale-style)
    - Equal price steps between orders
    """

    def __init__(self, config: GridConfig):
        self.config = config

    def calculate(self) -> List[GridOrder]:
        """
        Calculate all grid orders based on configuration.

        Returns:
            List of grid orders sorted by index (0 = first order)
        """
        first_price = self._calculate_first_order_price()
        last_price = self._calculate_last_order_price(first_price)
        price_step = self._calculate_price_step(first_price, last_price)

        volume_weights = self._calculate_volume_weights()
        first_order_volume = self.config.total_budget / volume_weights

        return [
            self._create_order(
                index=i,
                price=first_price - (i * price_step),
                volume_usdt=first_order_volume * self._get_volume_multiplier(i)
            )
            for i in range(self.config.grid_levels)
        ]

    def _calculate_first_order_price(self) -> float:
        """Calculate price for the first order (closest to current price)."""
        offset_multiplier = 1 - (self.config.first_step_pct / 100)
        return self.config.current_price * offset_multiplier

    def _calculate_last_order_price(self, first_price: float) -> float:
        """Calculate price for the last order (furthest from current price)."""
        grid_multiplier = 1 - (self.config.grid_length_pct / 100)
        return first_price * grid_multiplier

    def _calculate_price_step(self, first_price: float, last_price: float) -> float:
        """Calculate uniform price step between consecutive orders."""
        if self.config.grid_levels <= 1:
            return 0.0
        return (first_price - last_price) / (self.config.grid_levels - 1)

    def _calculate_volume_weights(self) -> float:
        """
        Calculate sum of volume weights for budget distribution.

        With volume_scale_pct = 0: all orders have equal weight (1.0)
        With volume_scale_pct > 0: later orders have exponentially larger weights

        """
        multiplier = self._get_volume_multiplier(1)
        return sum(multiplier ** i for i in range(self.config.grid_levels))

    def _get_volume_multiplier(self, order_index: int) -> float:
        """Get volume multiplier for order at given index."""
        base_multiplier = 1 + (self.config.volume_scale_pct / 100)
        return base_multiplier ** order_index

    def _create_order(self, index: int, price: float, volume_usdt: float) -> GridOrder:
        """
        Create a single grid order with proper precision.

        Args:
            index: Order index in grid (0 = first)
            price: Order price in quote currency
            volume_usdt: Order volume in quote currency (USDT)

        Returns:
            GridOrder with rounded values according to precision settings
        """
        amount_base = volume_usdt / price

        return GridOrder(
            index=index,
            price=round(price, self.config.price_precision),
            amount_usdt=round(volume_usdt, 2),
            amount_base=self._truncate_to_precision(
                amount_base,
                self.config.amount_precision
            )
        )

    @staticmethod
    def _truncate_to_precision(value: float, precision: int) -> float:
        """
        Truncate value to specified decimal precision (rounds down).

        This is critical for exchange orders to avoid "insufficient balance" errors.
        Always rounds DOWN to ensure we don't try to trade more than we have.

        Args:
            value: Value to truncate
            precision: Number of decimal places

        Returns:
            Truncated value as float

        """
        decimal_value = Decimal(str(value))
        quantizer = Decimal("0.1") ** precision
        return float(decimal_value.quantize(quantizer, rounding=ROUND_DOWN))
