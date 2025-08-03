"""
Market making strategy implementation
"""

import asyncio
import time
from datetime import datetime
from typing import Optional

import settings
from logging_config import get_main_logger
from market_data.binance_ws import BinanceWebSocketClient
from market_data.state import MarketDataState
from roxom.roxom_client import RoxomClient
from roxom.state import AccountDataState
from .orders import OrderManager
from .pricing import FairPriceCalculator

logger = get_main_logger()


class MarketMaker:
    """Encapsulates all market making state and logic"""
    
    def __init__(self):
        self.market_state = MarketDataState()
        self.pricing_calculator = FairPriceCalculator(self.market_state)
        self.roxom_client = RoxomClient(settings.API_KEY, settings.BASE_URL)
        
        self.account_state = AccountDataState()
        self.order_manager = OrderManager(self.roxom_client, self.account_state)
        
        self.current_orders = {
            'bid_id': None,
            'ask_id': None
        }
        
        self.shutdown_event = asyncio.Event()
        self.emergency_shutdown = asyncio.Event()
        
        self.start_time = time.time()
        
        self.current_position = {
            "symbol": settings.SYMBOL,
            "position": 0.0,
            "total_fills": 0,
            "last_updated": None
        }

    async def quote_market(self):
        """Place bid and ask orders around fair price"""
        try:
            fair_price = self.pricing_calculator.get_fair_price()
            if not fair_price:
                logger.info("No fair price available, skipping quote")
                return
            
            bid_price, ask_price = self.pricing_calculator.calculate_bid_ask_prices(fair_price)
            
            # Cancel existing orders by ID
            orders_to_cancel = []
            for order_type, order_id in self.current_orders.items():
                if order_id:
                    # Check if order is still active before trying to cancel
                    if not self.account_state.is_order_active(order_id):
                        logger.debug(f"Skipping cancellation of {order_type}: {order_id} (already {self.account_state.get_order_status(order_id)})")
                        continue
                    orders_to_cancel.append((order_type, order_id))
            
            if orders_to_cancel:
                # Log all cancellations
                order_info = ", ".join([f"{order_id}" for _, order_id in orders_to_cancel])
                logger.info(f"Canceling orders [{order_info}]")
                
                # Cancel all orders concurrently
                cancellation_tasks = [
                    asyncio.to_thread(self.roxom_client.cancel_order, order_id)
                    for _, order_id in orders_to_cancel
                ]
                
                cancellation_results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)
                
                # Process results and update local state
                cancelled_count = 0
                for (order_type, order_id), result in zip(orders_to_cancel, cancellation_results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to cancel {order_id}: {result}")
                    else:
                        # Update local state to reflect cancellation
                        order = self.account_state.get_order(order_id)
                        if order:
                            order['status'] = 'cancelled'
                        cancelled_count += 1
            else:
                logger.debug("No existing orders to cancel")
            
            # Place bid and ask orders concurrently
            bid_task = asyncio.to_thread(
                self.roxom_client.place_order,
                symbol=settings.SYMBOL,
                side="buy",
                qty=settings.ORDER_SIZE,
                price=f"{bid_price:.8f}",
                order_type=settings.ORDER_TYPE,
                time_in_force=settings.TIME_IN_FORCE,
                inst_type=settings.INST_TYPE
            )
            
            ask_task = asyncio.to_thread(
                self.roxom_client.place_order,
                symbol=settings.SYMBOL,
                side="sell",
                qty=settings.ORDER_SIZE,
                price=f"{ask_price:.8f}",
                order_type=settings.ORDER_TYPE,
                time_in_force=settings.TIME_IN_FORCE,
                inst_type=settings.INST_TYPE
            )
            
            bid_result, ask_result = await asyncio.gather(bid_task, ask_task)
            
            bid_id = bid_result['data']['orderId']
            self.current_orders['bid_id'] = bid_id
            logger.info(f"BID placed {settings.ORDER_SIZE} @ {bid_price:.8f} [{bid_id}]")
            
            self.account_state.update_order({
                'orderId': bid_id,
                'accountId': bid_result['data'].get('accountId'),
                'symbol': settings.SYMBOL,
                'status': 'pendingsubmit',
                'remainingQty': settings.ORDER_SIZE,
                'executedQty': '0.00',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            ask_id = ask_result['data']['orderId']
            self.current_orders['ask_id'] = ask_id
            logger.info(f"ASK placed {settings.ORDER_SIZE} @ {ask_price:.8f} [{ask_id}]")
            
            self.account_state.update_order({
                'orderId': ask_id,
                'accountId': ask_result['data'].get('accountId'),
                'symbol': settings.SYMBOL,
                'status': 'pendingsubmit',
                'remainingQty': settings.ORDER_SIZE,
                'executedQty': '0.00',
                'avgPx': '0.00000000',
                'timestamp': datetime.utcnow().isoformat()
            })
            

            
        except Exception as e:
            logger.error(f"Error quoting market: {e}")

    async def position_polling_loop(self):
        """Poll positions"""
        
        while not self.shutdown_event.is_set():
            try:
                await self._update_position()                
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=1.0)
                    break
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in position polling: {e}")
                await asyncio.sleep(10)

    async def _update_position(self):
        """Fetch current position from REST API"""
        try:
            response = self.roxom_client.get_positions(settings.SYMBOL, settings.INST_TYPE)
            positions = response.get('data', {}).get('positions', [])
            
            total_position = 0.0
            filled_orders = len(self.account_state.get_filled_orders())
            
            for position in positions:
                side = position.get('side')
                size = float(position.get('size', 0))
                
                # Convert to signed position: long = +, short = -
                if side == 'long':
                    total_position += size
                elif side == 'short':
                    total_position -= size
            
            self.current_position.update({
                "position": total_position,
                "total_fills": filled_orders,
                "last_updated": datetime.utcnow().isoformat()
            })
                
        except Exception as e:
            logger.warning(f"Failed to update position: {e}")

    async def trading_loop(self):
        """Main trading loop"""
        while not self.shutdown_event.is_set():
            await self.quote_market()
            
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=settings.QUOTE_INTERVAL)
                break
            except asyncio.TimeoutError:
                continue

    async def immediate_cleanup(self):
        """Immediate order cancelation on CTRL+C"""
        logger.info("Canceling all active orders")
        
        try:
            response = self.roxom_client.cancel_all_orders()
            
            if response.get('success'):
                logger.info("Successfully sent cancel all orders request")
            
            cancelled_count = len([order_id for order_id in self.current_orders.values() if order_id])
            self.current_orders = {'bid_id': None, 'ask_id': None}
            
            for order_id, order_data in self.account_state.orders.items():
                if self.account_state.is_order_active(order_id):
                    order_data['status'] = 'cancelled'
            
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            logger.warning("Unable to cancel orders - continuing with shutdown")
            
            # Clear local tracking regardless
            self.current_orders = {'bid_id': None, 'ask_id': None}

    async def emergency_monitor(self):
        """Monitor for emergency shutdown and cancel orders immediately"""
        await self.emergency_shutdown.wait()
        await self.immediate_cleanup()

    async def on_price_update(self, symbol: str, bid: float, ask: float):
        fair_price = self.pricing_calculator.get_fair_price()

    async def initialize(self):
        """Initialize the market maker components"""
        try:
            await self.order_manager.initialize()
        except Exception as e:
            logger.warning(f"Order manager initialization failed, continuing without REST data: {e}")

    async def run(self):
        """Run the market making strategy"""
        logger.info("Starting Roxom Market Maker")
        logger.info("Press CTRL+C to cancel all orders and shutdown")
        
        await self.initialize()
        
        # Create WebSocket client for price feeds
        ws_client = BinanceWebSocketClient(
            self.market_state, 
            self.on_price_update, 
            self.shutdown_event
        )
        
        try:
            # Start all components concurrently
            await asyncio.gather(
                ws_client.start(),
                self.order_manager.start_websocket(self.shutdown_event),
                self.trading_loop(),
                self.position_polling_loop(),
                self.emergency_monitor(),
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.close()

    def close(self):
        """Clean up resources"""
        self.roxom_client.close()

    def trigger_shutdown(self):
        """Trigger shutdown for signal handling"""
        self.emergency_shutdown.set()
        self.shutdown_event.set()