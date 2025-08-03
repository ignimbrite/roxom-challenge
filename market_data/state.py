from typing import Dict, Optional

import settings


class MarketDataState:
    """Stores latest bid/ask prices for symbols"""
    
    def __init__(self):
        self.prices: Dict[str, Dict] = {}
        for symbol in settings.PRICE_SYMBOLS:
            self.prices[symbol.upper()] = {'bid': None, 'ask': None}
    
    def update_price(self, symbol: str, bid: float, ask: float) -> None:
        """Update latest bid/ask for a symbol"""
        if symbol in self.prices:
            self.prices[symbol] = {
                'bid': bid,
                'ask': ask
            }
    
    def get_price(self, symbol: str) -> Optional[Dict]:
        """Get latest price data for a symbol"""
        return self.prices.get(symbol)
    
    def has_data(self, symbols: list) -> bool:
        """Check if all symbols have price data"""
        for symbol in symbols:
            price_data = self.prices.get(symbol)
            if not price_data or price_data['bid'] is None or price_data['ask'] is None:
                return False
        return True