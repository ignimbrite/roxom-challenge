from datetime import datetime
from typing import Any, Dict, List, Optional

from logging_config import get_account_state_logger

logger = get_account_state_logger()


class AccountDataState:
    """Stores real-time account data from Roxom WebSocket: orders only"""
    
    def __init__(self):
        # Order tracking - order_id -> order_data
        self.orders: Dict[str, Dict[str, Any]] = {}
        
        # Track order status changes for debugging
        self.order_history: List[Dict[str, Any]] = []
        
        logger.debug("AccountDataState initialized")
    
    def update_order(self, order_data: Dict[str, Any]) -> None:
        """Update order status from WebSocket order update"""
        order_id = order_data.get('orderId')
        if not order_id:
            logger.warning("Received order update without orderId")
            return
        
        previous_state = self.orders.get(order_id, {})
        previous_status = previous_state.get('status', 'unknown')
        
        self.orders[order_id] = {
            'orderId': order_id,
            'accountId': order_data.get('accountId'),
            'symbol': order_data.get('symbol'),
            'status': order_data.get('status'),
            'remainingQty': order_data.get('remainingQty'),
            'executedQty': order_data.get('executedQty'),
            'avgPx': order_data.get('avgPx'),
            'timestamp': order_data.get('timestamp'),
            'lastUpdated': datetime.utcnow().isoformat()
        }
        
        # Add to history for tracking
        history_entry = {
            'orderId': order_id,
            'previousStatus': previous_status,
            'newStatus': order_data.get('status'),
            'executedQty': order_data.get('executedQty'),
            'remainingQty': order_data.get('remainingQty'),
            'avgPx': order_data.get('avgPx'),
            'timestamp': order_data.get('timestamp'),
            'processedAt': datetime.utcnow().isoformat()
        }
        self.order_history.append(history_entry)
        
        # Keep history manageable (last 1000 entries)
        if len(self.order_history) > 1000:
            self.order_history = self.order_history[-1000:]
        
        # Log status changes in a uniform format
        status = order_data.get('status')
        if status == 'pendingsubmit':
            logger.debug(f"Order submitted: {order_id}")
        elif status == 'submitted':
            logger.debug(f"Order confirmed: {order_id}")
        elif status == 'filled':
            executed = order_data.get('executedQty', '0.00')
            avg_price = order_data.get('avgPx', '0.00000000')
            logger.info(f"Order filled {executed} @ {avg_price} [{order_id}]")
        elif status == 'partiallyfilled':
            executed = order_data.get('executedQty', '0.00')
            avg_price = order_data.get('avgPx', '0.00000000')
            remaining = order_data.get('remainingQty', '0.00')
            logger.info(f"Order partially filled {executed} @ {avg_price} | Remaining {remaining} [{order_id}]")
        elif status == 'cancelled':
            executed = order_data.get('executedQty', '0.00')
            if executed != '0.00' and float(executed) > 0:
                remaining = order_data.get('remainingQty', '0.00')
                avg_price = order_data.get('avgPx', '0.00000000')
                logger.info(f"Order cancelled with partial fill {executed} @ {avg_price} | Remaining {remaining} [{order_id}]")
            else:
                logger.debug(f"Order cancelled: {order_id}")
        elif status == 'rejected':
            executed = order_data.get('executedQty', '0.00')
            remaining = order_data.get('remainingQty', '0.00')
            logger.info(f"Order rejected: {order_id} | Executed {executed} | Remaining {remaining}")
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order data by ID"""
        return self.orders.get(order_id)
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get order status by ID"""
        order = self.orders.get(order_id)
        return order.get('status') if order else None
    
    def get_active_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all orders that are not in terminal states"""
        terminal_states = {'filled', 'cancelled', 'rejected', 'inactive'}
        return {
            order_id: order_data 
            for order_id, order_data in self.orders.items() 
            if order_data.get('status') not in terminal_states
        }
    
    def get_filled_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all filled orders"""
        return {
            order_id: order_data 
            for order_id, order_data in self.orders.items() 
            if order_data.get('status') == 'filled'
        }
    
    def is_order_active(self, order_id: str) -> bool:
        """Check if an order is still active (not in terminal state)"""
        order = self.orders.get(order_id)
        if not order:
            return False
        
        terminal_states = {'filled', 'cancelled', 'rejected', 'inactive'}
        return order.get('status') not in terminal_states
    
    def get_order_summary(self) -> Dict[str, int]:
        """Get summary of orders by status"""
        summary = {}
        for order_data in self.orders.values():
            status = order_data.get('status', 'unknown')
            summary[status] = summary.get(status, 0) + 1
        return summary
    