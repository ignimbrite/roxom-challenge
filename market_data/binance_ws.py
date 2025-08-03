import asyncio
import json
from typing import Callable

import websockets

import settings
from logging_config import get_binance_ws_logger
from .state import MarketDataState

logger = get_binance_ws_logger()


class BinanceWebSocketClient:
    """Handles Binance WebSocket connections and price updates"""

    def __init__(self, state: MarketDataState, on_update_callback: Callable = None, shutdown_event=None):
        self.state = state
        self.on_update_callback = on_update_callback
        self.shutdown_event = shutdown_event
        self.ws_url = settings.BINANCE_WS_URL
        self.symbols = settings.PRICE_SYMBOLS
    
    async def start(self):
        """Start the WebSocket connection"""
        while not (self.shutdown_event and self.shutdown_event.is_set()):
            try:
                await self._connect_and_listen()
            except Exception as e:
                if self.shutdown_event and self.shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping WebSocket client")
                    break
                logger.error(f"Connection error: {e}. Reconnecting in 5 seconds")
                await asyncio.sleep(5)
    
    async def _connect_and_listen(self):
        """Connect to Binance WebSocket and listen for price updates"""
        streams = "/".join(f"{symbol}@bookTicker" for symbol in self.symbols)
        ws_url = f"{self.ws_url}/{streams}"
        
        logger.info(f"Connecting to: {ws_url}")
        
        async with websockets.connect(ws_url) as ws:
            logger.info("Connected to Binance WebSocket")
            
            while not (self.shutdown_event and self.shutdown_event.is_set()):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    await self._handle_message(data)
                    
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    raise
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await asyncio.sleep(1)
    
    async def _handle_message(self, data: dict):
        """Process incoming WebSocket message"""
        if "data" in data:
            payload = data["data"]
        else:
            payload = data
        
        symbol = payload["s"]
        bid = float(payload["b"])
        ask = float(payload["a"])

        self.state.update_price(symbol, bid, ask)
        logger.debug(f"{symbol} | Bid: {bid} | Ask: {ask}")
        
        if self.on_update_callback:
            await self.on_update_callback(symbol, bid, ask)