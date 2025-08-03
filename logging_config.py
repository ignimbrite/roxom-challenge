"""
Centralized logging configuration for Roxom Market Maker
"""

import logging

import settings


def setup_logging():
    """Configure logging for the entire application"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=settings.LOG_FORMAT,
        filename=settings.LOG_FILE
    )

def get_logger(module_name: str = None) -> logging.Logger:
    """
    Get a logger with consistent naming convention.
    
    Args:
        module_name: Optional module name to append to base logger name
        
    Returns:
        Configured logger instance
    """
    base_name = "market_maker"
    
    if module_name:
        logger_name = f"{base_name}.{module_name}"
    else:
        logger_name = base_name
        
    return logging.getLogger(logger_name)

def get_main_logger():
    """Get the main market maker logger"""
    return get_logger()


def get_order_manager_logger():
    """Get the order manager logger"""
    return get_logger("order_manager")


def get_account_state_logger():
    """Get the account state logger"""
    return get_logger("account_state")


def get_binance_ws_logger():
    """Get the Binance WebSocket logger"""
    return get_logger("binance_ws")


def get_roxom_ws_logger():
    """Get the Roxom WebSocket logger"""
    return get_logger("roxom_ws")
