"""
Dashboard HTTP server for Roxom Market Maker
Provides web interface for monitoring trading activity
"""

import asyncio
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import settings
from logging_config import get_logger

logger = get_logger("dashboard")


class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS support and REST API endpoints"""
    
    def __init__(self, *args, static_dir: str = None, market_maker=None, **kwargs):
        self.static_dir = static_dir or str(Path(__file__).parent / "static")
        self.market_maker = market_maker
        super().__init__(*args, directory=self.static_dir, **kwargs)
    
    def end_headers(self):
        """Add CORS headers for local development"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle preflight OPTIONS requests"""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests with API endpoints and static file serving"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path.startswith('/api/'):
            return self._handle_api_request(path)
        
        if path == '/' or path == '':
            self.path = '/index.html'
        

        
        return super().do_GET()
    
    def _handle_api_request(self, path: str):
        """Handle REST API requests"""
        try:
            if not self.market_maker:
                self._send_json_response({"error": "MarketMaker not available"}, 503)
                return
            
            if path == '/api/status':
                self._handle_status_api()
            elif path == '/api/quotes':
                self._handle_quotes_api()
            elif path == '/api/orders':
                self._handle_orders_api()
            elif path == '/api/position':
                self._handle_position_api()
            else:
                self._send_json_response({"error": "API endpoint not found"}, 404)
                
        except Exception as e:
            logger.error(f"API request error: {e}")
            self._send_json_response({"error": "Internal server error"}, 500)
    
    def _handle_status_api(self):
        """API endpoint for overall bot status"""
        try:
            uptime = time.time() - self.market_maker.start_time
            
            fair_price = None
            if self.market_maker.pricing_calculator:
                fair_price = self.market_maker.pricing_calculator.get_fair_price()
            
            status_data = {
                "status": "running",
                "uptime": uptime,
                "fair_price": fair_price,
                "current_orders": self.market_maker.current_orders.copy(),
                "last_updated": time.time()
            }
            
            self._send_json_response(status_data)
            
        except Exception as e:
            logger.error(f"Status API error: {e}")
            self._send_json_response({"error": "Failed to get status"}, 500)
    
    def _handle_quotes_api(self):
        """API endpoint for current quote data"""
        try:
            fair_price = self.market_maker.pricing_calculator.get_fair_price()
            if not fair_price:
                self._send_json_response({"error": "No fair price available"}, 503)
                return
            
            bid_price, ask_price = self.market_maker.pricing_calculator.calculate_bid_ask_prices(fair_price)
            
            quote_data = {
                "timestamp": time.time(),
                "fair_price": fair_price,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "spread": ask_price - bid_price,
                "spread_bps": ((ask_price - bid_price) / fair_price) * 10000,
                "uptime": time.time() - self.market_maker.start_time,
                "current_orders": self.market_maker.current_orders.copy()
            }
            
            self._send_json_response(quote_data)
            
        except Exception as e:
            logger.error(f"Quotes API error: {e}")
            self._send_json_response({"error": "Failed to get quotes"}, 500)
    
    def _handle_orders_api(self):
        """API endpoint for current order state"""
        try:
            order_data = {
                "timestamp": time.time(),
                "active_orders": list(self.market_maker.account_state.get_active_orders().values()),
                "recent_fills": list(self.market_maker.account_state.get_filled_orders().values())[-10:],
                "order_summary": self.market_maker.account_state.get_order_summary(),
                "current_order_ids": self.market_maker.current_orders.copy(),
                "uptime": time.time() - self.market_maker.start_time
            }
            
            self._send_json_response(order_data)
            
        except Exception as e:
            logger.error(f"Orders API error: {e}")
            self._send_json_response({"error": "Failed to get orders"}, 500)
    
    def _handle_position_api(self):
        """API endpoint for current position data"""
        try:
            position_data = self.market_maker.current_position.copy()
            position_data["last_updated"] = time.time()
            
            self._send_json_response(position_data)
            
        except Exception as e:
            logger.error(f"Position API error: {e}")
            self._send_json_response({"error": "Failed to get position"}, 500)
    
    def _send_json_response(self, data: dict, status_code: int = 200):
        """Send JSON response with proper headers"""
        response_body = json.dumps(data, indent=2)
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress HTTP request logs for cleaner output"""
        # Only log errors, not every request
        if "GET" not in format or "200" not in format:
            logger.debug(format % args)


class DashboardServer:
    """Dashboard HTTP server with lifecycle management"""
    
    def __init__(self, host: str = "localhost", port: int = 8000, market_maker=None):
        self.host = host
        self.port = port
        self.market_maker = market_maker
        self.httpd: Optional[socketserver.TCPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.static_dir = str(Path(__file__).parent / "static")
        
    def _create_handler(self):
        """Create request handler with static directory and market maker configuration"""
        static_dir = self.static_dir
        market_maker = self.market_maker
        
        class ConfiguredHandler(DashboardRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, static_dir=static_dir, market_maker=market_maker, **kwargs)
        return ConfiguredHandler
    
    def start(self) -> bool:
        """Start the dashboard server in a background thread"""
        if self.is_running:
            logger.warning("Dashboard server is already running")
            return True
            
        try:
            self.httpd = socketserver.TCPServer((self.host, self.port), self._create_handler())
            
            self.server_thread = threading.Thread(
                target=self.httpd.serve_forever,
                name="DashboardServer",
                daemon=True
            )
            self.server_thread.start()
            self.is_running = True
            
            logger.info(f"Dashboard server started at http://{self.host}:{self.port}")
            
            if settings.DASHBOARD_AUTO_OPEN:
                try:
                    webbrowser.open(f"http://{self.host}:{self.port}")
                except Exception as e:
                    logger.debug(f"Could not auto-open browser: {e}")
            
            return True
            
        except OSError as e:
            if e.errno == 48:
                logger.error(f"Port {self.port} is already in use. Dashboard server not started.")
                return False
            else:
                logger.error(f"Failed to start dashboard server: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error starting dashboard server: {e}")
            return False
    
    def stop(self):
        """Stop the dashboard server"""
        if not self.is_running:
            return
            
        if self.httpd:
            logger.info("Stopping dashboard server...")
            self.httpd.shutdown()
            self.httpd.server_close()
            
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            
        self.is_running = False
        logger.info("Dashboard server stopped")
    

    
    def get_status(self) -> dict:
        """Get server status information"""
        return {
            "running": self.is_running,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}" if self.is_running else None,
            "static_dir": self.static_dir,
            "has_market_maker": self.market_maker is not None
        }


async def start_dashboard_server(shutdown_event: Optional[asyncio.Event] = None, market_maker=None) -> None:
    """
    Start dashboard server as an async task
    
    Args:
        shutdown_event: Optional event to monitor for shutdown signal
        market_maker: MarketMaker instance for direct data access
    """
    server = DashboardServer(
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        market_maker=market_maker
    )
    
    if not server.start():
        logger.error("Failed to start dashboard server")
        return
    
    if shutdown_event:
        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            server.stop()
    else:
        try:
            while server.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            server.stop()


def run_standalone_dashboard():
    """Run dashboard server standalone (for testing or separate process)"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Roxom Market Maker Dashboard")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()
    
    server = DashboardServer(args.host, args.port)
    
    print(f"Starting Roxom Dashboard Server on {args.host}:{args.port}")
    print(f"Dashboard: http://{args.host}:{args.port}")
    print(f"Serving from: {os.getcwd()}")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        if server.start():
            while server.is_running:
                import time
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down dashboard server...")
    finally:
        server.stop()


if __name__ == "__main__":
    run_standalone_dashboard()