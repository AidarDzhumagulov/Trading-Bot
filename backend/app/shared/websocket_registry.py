import asyncio
from typing import Dict
from uuid import UUID
from app.core.logging import logger


class WebSocketRegistry:
    """Registry для управления WebSocket соединениями с блокировками"""

    def __init__(self):
        self.managers: Dict[UUID, any] = {}
        self._lock = asyncio.Lock()

    async def add(self, config_id: UUID, manager):
        """Добавляет WebSocket Manager, останавливая старый если есть"""
        async with self._lock:
            if config_id in self.managers:
                old_manager = self.managers[config_id]
                logger.warning(
                    f"Replacing existing WebSocket manager for config {config_id}. "
                    f"Stopping old manager..."
                )
                asyncio.create_task(self._stop_manager_safely(old_manager, config_id))

            self.managers[config_id] = manager
            logger.info(f"WebSocket Manager добавлен для config_id: {config_id}")

    async def _stop_manager_safely(self, manager, config_id):
        """Безопасно останавливает manager"""
        try:
            await manager.stop()
            logger.info(f"Old WebSocket manager stopped for config {config_id}")
        except Exception as e:
            logger.error(f"Error stopping old WebSocket manager: {e}")

    def get(self, config_id: UUID):
        """Получает WebSocket Manager по config_id"""
        return self.managers.get(config_id)

    async def remove(self, config_id: UUID):
        """Удаляет WebSocket Manager из registry"""
        async with self._lock:
            if config_id in self.managers:
                manager = self.managers.pop(config_id)
                logger.info(f"WebSocket Manager удален для config_id: {config_id}")
                return manager
            return None

    def get_all(self):
        """Возвращает все активные менеджеры"""
        return list(self.managers.values())

    async def stop_all(self, timeout: float = 10.0):
        """
        Останавливает все WebSocket менеджеры с таймаутом

        Args:
            timeout: Максимальное время ожидания (секунды)
        """
        async with self._lock:
            if not self.managers:
                logger.info("No WebSocket managers to stop")
                return

            logger.info(
                f"Shutting down {len(self.managers)} WebSocket managers (timeout: {timeout}s)..."
            )

            stop_tasks = [
                self._stop_manager_safely(manager, config_id)
                for config_id, manager in self.managers.items()
            ]

            try:
                await asyncio.wait_for(
                    asyncio.gather(*stop_tasks, return_exceptions=True), timeout=timeout
                )
                logger.info("All managers stopped successfully")
            except asyncio.TimeoutError:
                logger.error(f"Timeout stopping managers after {timeout}s")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                self.managers.clear()
                logger.info("WebSocket registry cleared")


websocket_registry = WebSocketRegistry()
