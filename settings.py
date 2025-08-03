"""
Roxom Market Maker Configuration
"""

# ===== EXCHANGE CONFIGURATION =====
API_KEY = "your_roxom_api_key"
BASE_URL = "https://api.roxom.io"

# ===== TRADING CONFIGURATION =====
SYMBOL = "GOLD-BTC"
INST_TYPE = "perpetual"

# ===== MARKET MAKING PARAMETERS =====
SPREAD_BPS = 20                 # Spread in basis points
ORDER_SIZE = "1.00"             # Size per order
QUOTE_INTERVAL = 5              # Seconds between requotes

# ===== ORDER PARAMETERS =====
ORDER_TYPE = "limit"
TIME_IN_FORCE = "gtc"

# ===== PRICE FEED CONFIGURATION =====
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
PRICE_SYMBOLS = ["paxgusdt", "btcusdt"]

# ===== ROXOM WEBSOCKET CONFIGURATION =====
ROXOM_WS_URL = "wss://ws.roxom.io/ws"
WS_RECONNECT_INTERVAL = 5      # Seconds between reconnection attempts

# ===== RISK LIMITS =====
TICK_SIZE = 0.00000100         # Tick size for GOLD-BTC

# ===== DASHBOARD CONFIGURATION =====
DASHBOARD_ENABLED = True
DASHBOARD_HOST = "localhost"
DASHBOARD_PORT = 8000
DASHBOARD_AUTO_OPEN = True

# ===== LOGGING CONFIGURATION =====
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = None  # Set to filename for file logging, None for console only