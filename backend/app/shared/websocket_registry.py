from typing import Dict
from uuid import UUID
from app.shared.websocket import BinanceWebsocketManager
from app.core.logging import logger


class WebSocketRegistry:
    _instance = None
    _managers: Dict[UUID, BinanceWebsocketManager] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def add(self, config_id: UUID, manager: BinanceWebsocketManager):
        self._managers[config_id] = manager
        logger.info(f"WebSocket Manager добавлен для config_id: {config_id}")
    
    def get(self, config_id: UUID) -> BinanceWebsocketManager | None:
        return self._managers.get(config_id)
    
    def remove(self, config_id: UUID):
        if config_id in self._managers:
            del self._managers[config_id]
            logger.info(f"WebSocket Manager удален для config_id: {config_id}")
    
    def get_all(self) -> Dict[UUID, BinanceWebsocketManager]:
        return self._managers
    
    async def stop_all(self):
        for config_id, manager in list(self._managers.items()):
            await manager.stop()
            self.remove(config_id)


websocket_registry = WebSocketRegistry()
