import asyncio
from typing import Dict, Any, Optional

import settings
from logging_config import get_order_manager_logger
from roxom.roxom_client import RoxomClient
from roxom.roxom_ws import RoxomWebSocketClient
from roxom.state import AccountDataState

logger = get_order_manager_logger()


class OrderManager:
    """Manages order state: fetch via REST at start, update via WebSocket"""
    
    def __init__(self, client: RoxomClient, state: AccountDataState):
        self.client = client
        self.state = state
        self.ws_client = None
        self.is_initialized = False

        
        logger.debug("OrderManager initialized")
    
    async def initialize(self) -> None:
        """Fetch existing orders via REST API"""
        try:
            response = self.client.get_orders(settings.INST_TYPE)
            orders = response.get('data', {}).get('orders', [])
            
            logger.debug(f"Found {len(orders)} existing orders")
            
            for order in orders:
                # Convert REST API format to WebSocket format
                order_data = {
                    'orderId': order.get('id'),
                    'accountId': order.get('accountId'),
                    'symbol': order.get('symbol'),
                    'status': order.get('status'),
                    'remainingQty': order.get('qty'),
                    'executedQty': '0.00',
                    'avgPx': '0.00000000',
                    'timestamp': order.get('createdAt')
                }
                self.state.update_order(order_data)
            
            self.is_initialized = True
            logger.debug("Order state initialized from REST API")
            
        except Exception as e:
            logger.error(f"Failed to initialize order state: {e}")
            raise
    
    async def start_websocket(self, shutdown_event: Optional[asyncio.Event] = None) -> None:
        """Start WebSocket connection for real-time order updates"""                
        self.ws_client = RoxomWebSocketClient(
            api_key=settings.API_KEY,
            account_state=self.state,
            on_order_update=self._on_order_update,
            shutdown_event=shutdown_event
        )
        
        await self.ws_client.start()
    
    async def _on_order_update(self, order_data: dict) -> None:
        """Handle order updates from WebSocket"""
        order_id = order_data.get('orderId')
        status = order_data.get('status')
        logger.debug(f"Order update: {order_id} -> {status}")
    
    def get_active_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get active orders from state"""
        return self.state.get_active_orders()
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get specific order by ID"""
        return self.state.get_order(order_id)
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get order status by ID"""
        return self.state.get_order_status(order_id)
        
    def is_ready(self) -> bool:
        """Check if order manager is ready"""
        return self.is_initialized and self.state is not None