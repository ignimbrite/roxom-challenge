import asyncio
import json
import time
from typing import Callable, Optional

import websockets

import settings
from logging_config import get_roxom_ws_logger
from .state import AccountDataState

logger = get_roxom_ws_logger()


class RoxomWebSocketClient:
    """Handles Roxom private WebSocket connections for order updates"""
    
    def __init__(self, api_key: str, account_state: AccountDataState, 
                 on_order_update: Optional[Callable] = None, 
                 shutdown_event: Optional[asyncio.Event] = None):
        self.api_key = api_key
        self.account_state = account_state
        self.on_order_update = on_order_update
        self.shutdown_event = shutdown_event
        
        # WebSocket configuration
        self.ws_url = settings.ROXOM_WS_URL
        self.reconnect_interval = settings.WS_RECONNECT_INTERVAL
        
        # Connection tracking
        self.connection_id = None
        self.is_authenticated = False
        self.websocket = None    
    
    async def start(self):
        """Start the WebSocket connection with reconnection logic"""
        
        while not (self.shutdown_event and self.shutdown_event.is_set()):
            try:
                await self._connect_and_listen()
            except Exception as e:
                if self.shutdown_event and self.shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping Roxom WebSocket client")
                    break
                logger.error(f"Roxom WebSocket connection error: {e}. Reconnecting in {self.reconnect_interval} seconds")
                await asyncio.sleep(self.reconnect_interval)
    
    async def _connect_and_listen(self):
        """Connect to Roxom WebSocket with authentication and listen for updates"""
        # Generate timestamp for authentication
        timestamp = str(int(time.time() * 1000))  # Milliseconds
        
        # Prepare authentication headers
        headers = {
            'X-API-KEY': self.api_key,
            'X-API-TIMESTAMP': timestamp
        }
        
        logger.info(f"Connecting to Roxom WebSocket: {self.ws_url}")
        logger.debug(f"Authentication timestamp: {timestamp}")
        
        try:
            # Connect with authentication headers
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=10
            ) as ws:
                self.websocket = ws
                logger.info("Connected to Roxom WebSocket")
                self.is_authenticated = True
                
                while not (self.shutdown_event and self.shutdown_event.is_set()):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        await self._handle_message(msg)
                        
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        logger.warning("Roxom WebSocket connection closed")
                        self.is_authenticated = False
                        self.websocket = None
                        raise
                    except Exception as e:
                        logger.error(f"Error processing Roxom WebSocket message: {e}")
                        await asyncio.sleep(1)
                        
        except websockets.InvalidHandshake as e:
            logger.error(f"WebSocket handshake failed (likely authentication issue): {e}")
            self.is_authenticated = False
            self.websocket = None
            raise
        except websockets.ConnectionClosedError as e:
            logger.error(f"WebSocket connection closed unexpectedly: {e}")
            self.is_authenticated = False
            self.websocket = None
            raise
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_authenticated = False
            self.websocket = None
            raise
    
    async def _handle_message(self, raw_message: str):
        """Process incoming WebSocket message"""
        try:
            message = json.loads(raw_message)
            
            if 'event' in message:
                await self._handle_event_message(message)
            elif 'type' in message:
                await self._handle_data_message(message)
            else:
                logger.warning(f"Unknown message format: {message}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e} | Raw: {raw_message}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_event_message(self, message: dict):
        """Handle event messages (connection, subscription, errors)"""
        event = message.get('event')
        code = message.get('code')
        msg_text = message.get('msg', '')
        conn_id = message.get('connId')
        
        if event == 'subscribe':
            if code == '0':
                logger.info(f"Subscription successful: {message.get('arg', {})} | ConnId: {conn_id}")
                self.connection_id = conn_id
            else:
                logger.error(f"Subscription failed: {msg_text} | Code: {code}")
                
        elif event == 'error':
            if code == '600010':
                logger.error("Authentication failed - check API key and timestamp")
                self.is_authenticated = False
            else:
                logger.error(f"WebSocket error: {msg_text} | Code: {code}")
        else:
            logger.info(f"Event: {event} | Code: {code} | Message: {msg_text}")
    
    async def _handle_data_message(self, message: dict):
        """Handle data messages (orders and balance)"""
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'order':
            await self._handle_order_update(data)
        elif msg_type == 'balance':
            # Balance updates received but not currently used
            logger.debug(f"Received balance update: {data}")
        else:
            logger.warning(f"Unknown data message type: {msg_type}")
    
    async def _handle_order_update(self, order_data: dict):
        """Handle order status updates"""
        try:
            self.account_state.update_order(order_data)
            
            if self.on_order_update:
                await self.on_order_update(order_data)
                
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    def close(self):
        """Close WebSocket connection"""
        logger.info("Closing Roxom WebSocket connection")
        self.is_authenticated = False
        if self.websocket and not self.websocket.closed:
            asyncio.create_task(self.websocket.close())
        self.websocket = None