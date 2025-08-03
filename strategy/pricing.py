from typing import Optional

import settings
from market_data.state import MarketDataState


class FairPriceCalculator:
    """Calculates fair prices for GOLD/BTC"""
    def __init__(self, state: MarketDataState):
        self.state = state
    
    def get_fair_price(self) -> Optional[float]:
        """Calculate fair price using PAXG and BTC midprices"""
        symbols = [symbol.upper() for symbol in settings.PRICE_SYMBOLS]
        if not self.state.has_data(symbols):
            return None
        
        paxg_data = self.state.get_price('PAXGUSDT')
        btc_data = self.state.get_price('BTCUSDT')
        
        paxg_mid = (paxg_data['bid'] + paxg_data['ask']) / 2
        btc_mid = (btc_data['bid'] + btc_data['ask']) / 2
        
        # GOLD/BTC = PAXG/USDT ÷ BTC/USDT
        fair_price = paxg_mid / btc_mid
        return fair_price
    
    def calculate_bid_ask_prices(self, fair_price: float) -> tuple[float, float]:
        """Calculate bid/ask prices from fair price with spread and tick size rounding"""
        spread = fair_price * (settings.SPREAD_BPS / 10000)
        bid_price = fair_price - spread / 2
        ask_price = fair_price + spread / 2
        
        # Round to tick size
        bid_price = round(bid_price / settings.TICK_SIZE) * settings.TICK_SIZE
        ask_price = round(ask_price / settings.TICK_SIZE) * settings.TICK_SIZE
        
        return bid_price, ask_price
    
    def is_ready(self) -> bool:
        """Check if we have valid price data for quoting"""
        return self.get_fair_price() is not None