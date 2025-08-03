#!/usr/bin/env python3
"""
Roxom Market Maker - Application entry point
"""

import asyncio
import signal

import settings
from logging_config import get_main_logger, setup_logging
from strategy.market_maker import MarketMaker

setup_logging()
logger = get_main_logger()

# Global market maker instance for signal handler access
market_maker = None


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, shutting down...")
    
    if market_maker:
        market_maker.trigger_shutdown()


async def main():
    """Application entry point - start the market maker and dashboard"""
    global market_maker
    
    market_maker = MarketMaker()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    tasks = [market_maker.run()]
    
    if settings.DASHBOARD_ENABLED:
        try:
            from dashboard import start_dashboard_server
            dashboard_task = start_dashboard_server(market_maker.shutdown_event, market_maker)
            tasks.append(dashboard_task)
        except Exception as e:
            logger.warning(f"Failed to start dashboard: {e}")
            logger.info("Continuing without dashboard...")
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())