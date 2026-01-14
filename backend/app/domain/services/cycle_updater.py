from decimal import Decimal

from app.core.logging import logger
from app.domain.value_objects import FillResult, CycleStats


class CycleUpdater:
    """
    Updates DCA cycle statistics after order fills.
    
    Manages:
    - Total base quantity
    - Total quote spent
    - Average entry price
    """
    
    def update_after_buy(self, cycle, fill_result: FillResult) -> CycleStats:
        """
        Update cycle statistics after buy order fill.
        
        Args:
            cycle: DcaCycle model instance
            fill_result: Result from FeeCalculator
            
        Returns:
            Updated CycleStats
        """
        current_base_qty = Decimal(str(cycle.total_base_qty or 0.0))
        current_quote_spent = Decimal(str(cycle.total_quote_spent or 0.0))
        
        new_base_qty = current_base_qty + fill_result.net_qty
        new_quote_spent = current_quote_spent + fill_result.order_cost
        
        avg_price = (
            new_quote_spent / new_base_qty 
            if new_base_qty > 0 
            else Decimal("0")
        )
        
        cycle.total_base_qty = float(new_base_qty)
        cycle.total_quote_spent = float(new_quote_spent)
        cycle.avg_price = float(avg_price)
        
        logger.info(
            f"[CycleUpdater] Обновлен цикл {cycle.id}: "
            f"base_qty={cycle.total_base_qty:.8f}, "
            f"quote_spent={cycle.total_quote_spent:.2f}, "
            f"avg_price={cycle.avg_price:.2f}"
        )
        
        return CycleStats(
            total_base_qty=new_base_qty,
            total_quote_spent=new_quote_spent,
            avg_price=avg_price
        )
