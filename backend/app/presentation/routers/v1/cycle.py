from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.infrastructure.persistence.sqlalchemy.models import DcaCycle, Order, BotConfig
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.presentation.schemas.cycle import CycleResponse, StatsResponse
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
        Order.status == OrderStatus.FILLED
    )
    result = await session.execute(stmt)
    filled_orders_count = result.scalar() or 0

    current_market_price = price_cache.get(config.symbol)

    tp_order_price = None
    if cycle.avg_price > 0 and config.take_profit_pct:
        tp_order_price = cycle.avg_price * (1 + config.take_profit_pct / 100)

    return CycleResponse(
        cycle_id=cycle.id,
        status=cycle.status.value,
        filled_orders_count=filled_orders_count,
        average_price=cycle.avg_price or 0.0,
        tp_order_price=tp_order_price,
        tp_order_volume=cycle.total_base_qty or 0.0,
        total_quote_spent=cycle.total_quote_spent or 0.0,
        current_market_price=current_market_price
    )


@router.get("/stats/", response_model=StatsResponse)
async def get_stats(
    config_id: UUID = Query(..., description="ID конфигурации бота"),
    session: AsyncSession = Depends(get_session)
):
    config = await session.get(BotConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    stmt = select(DcaCycle).where(
        DcaCycle.config_id == config_id,
        DcaCycle.status == CycleStatus.CLOSED
    )
    result = await session.execute(stmt)
    closed_cycles = result.scalars().all()

    total_profit_usdt = sum(cycle.profit_usdt or 0.0 for cycle in closed_cycles)
    completed_cycles = len(closed_cycles)

    stmt = select(DcaCycle).where(
        DcaCycle.config_id == config_id,
        DcaCycle.status == CycleStatus.OPEN
    ).order_by(DcaCycle.created_at.desc())
    result = await session.execute(stmt)
    current_cycle = result.scalar_one_or_none()

    current_cycle_response = None
    if current_cycle:
        stmt = select(func.count(Order.id)).where(
            Order.cycle_id == current_cycle.id,
            Order.order_type == "BUY_SAFETY",
            Order.status == OrderStatus.FILLED
        )
        result = await session.execute(stmt)
        filled_orders_count = result.scalar() or 0

        current_market_price = price_cache.get(config.symbol)

        tp_order_price = None
        if current_cycle.avg_price > 0 and config.take_profit_pct:
            tp_order_price = current_cycle.avg_price * (1 + config.take_profit_pct / 100)

        current_cycle_response = CycleResponse(
            cycle_id=current_cycle.id,
            status=current_cycle.status.value,
            filled_orders_count=filled_orders_count,
            average_price=current_cycle.avg_price or 0.0,
            tp_order_price=tp_order_price,
            tp_order_volume=current_cycle.total_base_qty or 0.0,
            total_quote_spent=current_cycle.total_quote_spent or 0.0,
            current_market_price=current_market_price
        )

    return StatsResponse(
        total_profit_usdt=total_profit_usdt,
        completed_cycles=completed_cycles,
        current_cycle=current_cycle_response
    )
