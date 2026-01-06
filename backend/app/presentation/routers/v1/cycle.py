from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.infrastructure.persistence.sqlalchemy.models import DcaCycle, Order, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.presentation.schemas.cycle import CycleResponse, EnhancedStatsResponse
from app.shared.websocket import price_cache

router = APIRouter(tags=["cycles"])


@router.get("/{cycle_id}", response_model=CycleResponse)
async def get_cycle(cycle_id: UUID, session: AsyncSession = Depends(get_session)):
    cycle = await session.get(DcaCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    config = await session.get(BotConfig, cycle.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    stmt = select(func.count(Order.id)).where(
        Order.cycle_id == cycle.id,
        Order.order_type == "BUY_SAFETY",
        Order.status == OrderStatus.FILLED,
    )
    result = await session.execute(stmt)
    filled_orders_count = result.scalar() or 0

    current_market_price = price_cache.get(config.symbol)

    tp_order_price = None
    effective_tp_pct = None
    expected_profit = None

    if cycle.current_tp_order_id:
        stmt = select(Order).where(Order.binance_order_id == cycle.current_tp_order_id)
        result = await session.execute(stmt)
        tp_order = result.scalar_one_or_none()

        if tp_order:
            tp_order_price = float(tp_order.price)

            if cycle.avg_price and cycle.avg_price > 0:
                effective_tp_pct = ((tp_order_price / cycle.avg_price) - 1) * 100

                if cycle.total_quote_spent:
                    expected_revenue = float(tp_order.amount) * tp_order_price
                    expected_profit = expected_revenue - float(cycle.total_quote_spent)

    unrealized_profit = None
    if (
        cycle.status == CycleStatus.OPEN
        and current_market_price
        and cycle.total_base_qty
    ):
        current_value = float(cycle.total_base_qty) * current_market_price
        unrealized_profit = current_value - float(cycle.total_quote_spent or 0)

    return CycleResponse(
        cycle_id=cycle.id,
        status=cycle.status.value,
        filled_orders_count=filled_orders_count,
        average_price=cycle.avg_price or 0.0,
        tp_order_price=tp_order_price,
        effective_tp_pct=effective_tp_pct,
        expected_profit=expected_profit,
        tp_order_volume=cycle.total_base_qty or 0.0,
        total_quote_spent=cycle.total_quote_spent or 0.0,
        current_market_price=current_market_price,
        unrealized_profit=unrealized_profit,
        accumulated_dust=cycle.accumulated_dust or 0.0,
    )


@router.get("/stats/", response_model=EnhancedStatsResponse)
async def get_stats(
    config_id: UUID = Query(..., description="ID конфигурации бота"),
    session: AsyncSession = Depends(get_session),
):
    config = await session.get(BotConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    stmt = select(DcaCycle).where(
        DcaCycle.config_id == config_id, DcaCycle.status == CycleStatus.CLOSED
    )
    result = await session.execute(stmt)
    closed_cycles = result.scalars().all()

    total_profit_usdt = sum(cycle.profit_usdt or 0.0 for cycle in closed_cycles)
    total_invested = sum(cycle.total_quote_spent or 0.0 for cycle in closed_cycles)
    completed_cycles = len(closed_cycles)

    win_rate = 0.0
    avg_profit_per_cycle = 0.0
    avg_cycle_duration = 0.0
    roi_pct = 0.0
    best_cycle_profit = 0.0
    worst_cycle_profit = 0.0

    if completed_cycles > 0:
        winning_cycles = sum(1 for c in closed_cycles if (c.profit_usdt or 0) > 0)
        win_rate = (winning_cycles / completed_cycles) * 100

        avg_profit_per_cycle = total_profit_usdt / completed_cycles

        durations = []
        for cycle in closed_cycles:
            if cycle.closed_at and cycle.created_at:
                duration = (cycle.closed_at - cycle.created_at).total_seconds() / 3600
                durations.append(duration)

        if durations:
            avg_cycle_duration = sum(durations) / len(durations)

        if total_invested > 0:
            roi_pct = (total_profit_usdt / total_invested) * 100

        profits = [c.profit_usdt or 0.0 for c in closed_cycles]
        if profits:
            best_cycle_profit = max(profits)
            worst_cycle_profit = min(profits)

    stmt = (
        select(DcaCycle)
        .where(DcaCycle.config_id == config_id, DcaCycle.status == CycleStatus.OPEN)
        .order_by(DcaCycle.created_at.desc())
    )
    result = await session.execute(stmt)
    current_cycle = result.scalar_one_or_none()

    current_cycle_response = None
    if current_cycle:
        current_cycle_response = await get_cycle(current_cycle.id, session)

    return EnhancedStatsResponse(
        total_profit_usdt=total_profit_usdt,
        completed_cycles=completed_cycles,
        current_cycle=current_cycle_response,
        total_invested=total_invested,
        roi_pct=roi_pct,
        win_rate=win_rate,
        avg_profit_per_cycle=avg_profit_per_cycle,
        avg_cycle_duration_hours=avg_cycle_duration,
        best_cycle_profit=best_cycle_profit,
        worst_cycle_profit=worst_cycle_profit,
        current_unrealized_profit=current_cycle_response.unrealized_profit
        if current_cycle_response
        else None,
        current_expected_profit=current_cycle_response.expected_profit
        if current_cycle_response
        else None,
    )
