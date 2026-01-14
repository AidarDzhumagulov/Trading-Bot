import asyncio
from datetime import datetime, UTC
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session_factory
from app.core.logging import logger
from app.domain.order_handler import OrderHandler
from app.infrastructure.persistence.sqlalchemy.models import BotConfig, DcaCycle, Order
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.infrastructure.persistence.sqlalchemy.models.order import OrderStatus
from app.shared.clients import BinanceClient
from app.shared.websocket import BinanceWebsocketManager
from app.shared.websocket_registry import websocket_registry


class BotRecoveryService:
    """Сервис для восстановления ботов после рестарта"""

    def __init__(self):
        self.recovered_count = 0
        self.failed_count = 0
        self.recovery_start_time = None
        self.recovery_duration = None

    async def recover_all_active_bots(self) -> dict:
        """
        Основной метод: восстанавливает все активные боты

        Returns:
            dict: Статистика восстановления
        """
        self.recovery_start_time = datetime.now(UTC)
        logger.info("BOT RECOVERY SYSTEM - Starting auto-recovery...")

        session_factory = get_session_factory()

        try:
            async with session_factory() as session:
                active_configs = await self._find_active_configs(session)

                if not active_configs:
                    logger.info("No active bots found - nothing to recover")
                    return self._get_recovery_stats()

                logger.info(f"Found {len(active_configs)} active bot(s) to recover")

                for config in active_configs:
                    try:
                        await self._recover_single_bot(config, session)
                        self.recovered_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to recover bot {config.id}: {e}", exc_info=True
                        )
                        self.failed_count += 1

                        try:
                            config.is_active = False
                            await session.commit()
                            logger.warning(
                                f"Bot {config.id} marked as inactive due to recovery failure"
                            )
                        except Exception as commit_error:
                            logger.error(
                                f"Failed to deactivate bot {config.id}: {commit_error}"
                            )

                self.recovery_duration = (
                    datetime.now(UTC) - self.recovery_start_time
                ).total_seconds()
                stats = self._get_recovery_stats()

                logger.info("=" * 80)
                logger.info(
                    f"Bot recovery completed in {self.recovery_duration:.2f}s"
                )
                logger.info(
                    f"Recovered: {self.recovered_count} | Failed: {self.failed_count}"
                )
                logger.info("=" * 80)

                return stats

        except Exception as e:
            logger.error(f"Critical error in bot recovery: {e}", exc_info=True)
            return self._get_recovery_stats()

    @staticmethod
    async def _find_active_configs(session: AsyncSession) -> List[BotConfig]:
        """Найти все активные конфиги"""
        stmt = select(BotConfig).where(BotConfig.is_active == True)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _recover_single_bot(self, config: BotConfig, session: AsyncSession):
        """
        Восстановить один бот

        Steps:
        1. Найти открытый цикл (если есть)
        2. Синхронизировать ордера с Binance
        3. Обработать missed fills
        4. Переподключить WebSocket
        5. Восстановить Trailing TP state
        """
        logger.info(f"Recovering bot: {config.id}")
        logger.info(f"  Symbol: {config.symbol}")
        logger.info(f"  Budget: {config.total_budget} USDT")

        open_cycle = await self._find_open_cycle(config.id, session)

        if not open_cycle:
            logger.info(f"No open cycle found for bot {config.id}")
            logger.info("Starting fresh cycle...")
            await self._start_fresh_cycle(config)
            return

        logger.info(f"Found open cycle: {open_cycle.id}")
        logger.info(f"  Created: {open_cycle.created_at}")
        logger.info(f"  Avg price: {open_cycle.avg_price} USDT")
        logger.info(f"  Total spent: {open_cycle.total_quote_spent} USDT")

        await self._sync_orders_with_binance(config, open_cycle, session)

        cycle_closed = await self._check_if_cycle_closed(open_cycle, session)

        if cycle_closed:
            logger.info(f"Cycle {open_cycle.id} was closed during downtime")
            await self._start_fresh_cycle(config)
            return

        await self._reconnect_websocket(config)

        logger.info(f"Bot {config.id} recovered successfully")

    @staticmethod
    async def _find_open_cycle(
        config_id: UUID, session: AsyncSession
    ) -> Optional[DcaCycle]:
        """Найти открытый цикл для конфига"""
        stmt = (
            select(DcaCycle)
            .where(DcaCycle.config_id == config_id, DcaCycle.status == CycleStatus.OPEN)
            .order_by(DcaCycle.created_at.desc())
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _sync_orders_with_binance(
        self, config: BotConfig, cycle: DcaCycle, session: AsyncSession
    ):
        """
        Синхронизировать локальные ордера с состоянием на Binance

        Обрабатывает случаи:
        - Ордера исполнились во время downtime (missed fills)
        - Ордера отменились
        - Ордера всё ещё активны
        """
        logger.info(f"Syncing orders with Binance for cycle {cycle.id}...")

        stmt = select(Order).where(
            Order.cycle_id == cycle.id,
            Order.status.in_([OrderStatus.ACTIVE, OrderStatus.PENDING]),
        )
        result = await session.execute(stmt)
        local_orders = result.scalars().all()

        if not local_orders:
            logger.info("No active local orders to sync")
            return

        logger.info(f"Found {len(local_orders)} local orders to sync")

        async with BinanceClient.create(
            config.binance_api_key, config.binance_api_secret
        ) as client:
            try:
                binance_orders = await client.get_open_orders(config.symbol)
                binance_orders_map = {str(o["id"]): o for o in binance_orders}

                logger.info(f"Found {len(binance_orders)} open orders on Binance")

                for local_order in local_orders:
                    await self._sync_single_order(
                        local_order, binance_orders_map, config, session, client
                    )

                await session.commit()
                logger.info("Order sync completed")

            except Exception as e:
                logger.error(f"Error syncing orders with Binance: {e}", exc_info=True)
                raise

    async def _sync_single_order(
        self,
        local_order: Order,
        binance_orders_map: dict,
        config: BotConfig,
        session: AsyncSession,
        client: BinanceClient,
    ):
        """Синхронизировать один ордер"""
        if not local_order.binance_order_id:
            logger.warning(f"Order {local_order.id} has no binance_order_id, skipping")
            return

        binance_order = binance_orders_map.get(local_order.binance_order_id)

        if binance_order:
            logger.info(
                f"Order {local_order.binance_order_id} still active on Binance"
            )

            if binance_order["status"] == "closed":
                logger.info(
                    f"Order {local_order.binance_order_id} was filled during downtime!"
                )
                await self._process_missed_fill(
                    local_order, binance_order, config, session, client
                )
        else:
            logger.warning(
                f"Order {local_order.binance_order_id} not found on Binance"
            )

            try:
                order_details = await client.get_order(
                    local_order.binance_order_id, config.symbol
                )

                if order_details["status"] == "closed":
                    logger.info("Order was filled during downtime!")
                    await self._process_missed_fill(
                        local_order, order_details, config, session, client
                    )

                elif order_details["status"] == "canceled":
                    logger.info("Order was cancelled")
                    local_order.status = OrderStatus.CANCELED

            except Exception as e:
                logger.error(f"Could not fetch order details: {e}")
                local_order.status = OrderStatus.CANCELED

    @staticmethod
    async def _process_missed_fill(
        local_order: Order,
        binance_order: dict,
        config: BotConfig,
        session: AsyncSession,
        client: BinanceClient,
    ):
        """Обработать ордер который исполнился во время downtime"""
        logger.info(
            f"Processing missed fill for order {local_order.binance_order_id}"
        )

        try:
            filled_amount = binance_order.get("filled") or binance_order.get("amount")
            avg_price = binance_order.get("average") or binance_order.get("price")

            order_cost = binance_order.get("cost")
            if not order_cost:
                order_cost = filled_amount * avg_price

            binance_order_data = {
                "id": str(binance_order["id"]),
                "symbol": config.symbol,
                "status": "closed",
                "amount": filled_amount,
                "price": avg_price,
                "filled": filled_amount,
                "cost": order_cost,
                "fee": binance_order.get("fee", {}),
            }

            order_handler = OrderHandler(session, client.exchange)
            await order_handler.handle_filled_order(binance_order_data)

            logger.info("Missed fill processed successfully")

        except Exception as e:
            logger.error(f"Error processing missed fill: {e}", exc_info=True)
            raise

    @staticmethod
    async def _check_if_cycle_closed(
        cycle: DcaCycle, session: AsyncSession
    ) -> bool:
        """Проверить не закрылся ли цикл во время downtime"""
        await session.refresh(cycle)

        if cycle.status == CycleStatus.CLOSED:
            logger.info(f"Cycle {cycle.id} was closed during downtime")
            return True

        return False

    async def _start_fresh_cycle(self, config: BotConfig):
        """Запустить новый цикл для бота"""
        logger.info(f"Starting fresh cycle for bot {config.id}")

        try:
            await self._reconnect_websocket(config)
            logger.info(f"Fresh cycle started for bot {config.id}")

        except Exception as e:
            logger.error(f"Error starting fresh cycle: {e}", exc_info=True)
            raise

    @staticmethod
    async def _reconnect_websocket(config: BotConfig):
        """Переподключить WebSocket для бота"""
        logger.info(f"Reconnecting WebSocket for bot {config.id}...")

        try:
            existing_manager = websocket_registry.get(config.id)
            if existing_manager:
                logger.warning(f"WebSocket already connected for {config.id}")
                return

            session_factory = get_session_factory()

            ws_manager = BinanceWebsocketManager(
                api_key=config.binance_api_key,
                api_secret=config.binance_api_secret,
                session_factory=session_factory,
                config_id=config.id,
                symbol=config.symbol,
            )

            await websocket_registry.add(config.id, ws_manager)
            asyncio.create_task(ws_manager.run_forever())

            await asyncio.sleep(1)

            logger.info(f"WebSocket connected for bot {config.id}")

        except Exception as e:
            logger.error(f"Error reconnecting WebSocket: {e}", exc_info=True)
            raise

    def _get_recovery_stats(self) -> dict:
        """Получить статистику восстановления"""
        return {
            "recovered": self.recovered_count,
            "failed": self.failed_count,
            "total": self.recovered_count + self.failed_count,
            "duration_seconds": self.recovery_duration,
            "started_at": (
                self.recovery_start_time.isoformat() if self.recovery_start_time else None
            ),
        }


bot_recovery_service = BotRecoveryService()


async def graceful_shutdown_bots(timeout: float = 10.0):
    """Graceful shutdown всех ботов перед остановкой бэкенда"""
    logger.info("GRACEFUL SHUTDOWN - Stopping all bots...")

    try:
        await websocket_registry.stop_all(timeout=timeout)

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
