import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests


class RoxomClient:
    """REST client for Roxom exchange API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.roxom.io"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": api_key,
            "Accept": "*/*",
            "Content-Type": "application/json"
        })
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - properly close session"""
        self.close()
    
    def close(self):
        """Close the requests session"""
        if hasattr(self, 'session') and self.session:
            self.session.close()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to Roxom API"""
        url = urljoin(self.base_url, endpoint)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, params=params, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Roxom API request failed: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" | Response: {error_detail}"
                except:
                    error_msg += f" | Response text: {e.response.text}"
            raise Exception(error_msg)
    
    # ===== TRADING METHODS =====
    
    def place_order(self, symbol: str, side: str, qty: str, price: str, 
                   order_type: str, time_in_force: str, inst_type: str) -> Dict[str, Any]:
        """Place a new order on Roxom"""
        data = {
            "symbol": symbol,
            "instType": inst_type,
            "orderType": order_type,
            "side": side,
            "qty": qty,
            "px": price,
            "timeInForce": time_in_force
        }
        return self._make_request("POST", "/api/v1/orders", data=data)
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order by ID"""
        endpoint = f"/api/v1/orders/{order_id}/cancel"
        return self._make_request("POST", endpoint)
    
    def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all open orders"""
        return self._make_request("POST", "/api/v1/orders/cancel-all")
    
    def get_orders(self, inst_type: str) -> Dict[str, Any]:
        """Get all orders"""
        params = {"instType": inst_type}
        return self._make_request("GET", "/api/v1/orders", params=params)
    
    # ===== ACCOUNT & POSITION METHODS =====
    
    def get_positions(self, symbol: str, inst_type: str) -> Dict[str, Any]:
        """Get positions for a symbol"""
        params = {
            "instType": inst_type,
            "symbol": symbol
        }
        return self._make_request("GET", "/api/v1/positions", params=params)
    
    # ===== MARKET DATA METHODS =====
    
    def ping(self) -> Dict[str, Any]:
        """Ping the exchange"""
        return self._make_request("GET", "/ping")