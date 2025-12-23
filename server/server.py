from mcp.server.fastmcp import FastMCP
from openalgo import api
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Find and load the common .env file from the parent directory
parent_dir = Path(__file__).resolve().parent.parent
env_path = parent_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logging.info(f"Loaded environment from {env_path}")
else:
    load_dotenv()  # Fall back to local .env file if common one doesn't exist
    logging.info("Loaded environment from local .env file")

# Parse command line arguments
parser = argparse.ArgumentParser(description='OpenAlgo MCP Server')
parser.add_argument('--api-key', help='OpenAlgo API Key')
parser.add_argument('--host', default='http://127.0.0.1:5000', help='OpenAlgo API host (default: http://127.0.0.1:5000)')
parser.add_argument('--port', type=int, default=8001, help='Server port (default: 8001)')
parser.add_argument('--mode', choices=['stdio', 'sse'], default='sse', help='Server mode (default: sse)')
args = parser.parse_args()

# Get configuration from environment variables or command line arguments
API_KEY = os.getenv('OPENALGO_API_KEY') or args.api_key
API_HOST = os.getenv('OPENALGO_API_HOST', args.host)
PORT = int(os.getenv('SERVER_PORT', str(args.port)))
MODE = os.getenv('SERVER_MODE', args.mode)
DEBUG = os.getenv('SERVER_DEBUG', '').lower() in ('true', 'yes', '1')

if not API_KEY:
    raise ValueError("OPENALGO_API_KEY must be set either in .env file or via command line arguments")

# Set up detailed logging for OpenAlgo API requests
class APIDebugHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.INFO:
            print(f"[{record.levelname}] {record.getMessage()}")

logger = logging.getLogger()
logger.addHandler(APIDebugHandler())

# Initialize OpenAlgo API client
logging.info(f"Initializing OpenAlgo client with host: {API_HOST} and API key: {API_KEY[:5]}...{API_KEY[-5:]}")
try:
    client = api(api_key=API_KEY, host=API_HOST)
    logging.info(f"Successfully initialized OpenAlgo client")
except Exception as e:
    logging.error(f"Error initializing OpenAlgo client: {str(e)}")
    logger = logging.getLogger(logger_name)
    logger.propagate = True
    raise

# Create an MCP server called "openalgo"
mcp = FastMCP("OpenAlgo MCP", instructions="""
OpenAlgo MCP Server provides AI assistants with access to trading capabilities through OpenAlgo API.

This server exposes various trading functions like:
- Placing, modifying, and canceling orders
- Retrieving market data and quotes
- Managing positions and portfolios
- Accessing historical data
""")

@mcp.tool()
def place_order(symbol: str, quantity: int, action: str, exchange: str = "NSE", price_type: str = "MARKET", product: str = "MIS", strategy: str = "Python", price: float = None, trigger_price: float = None, disclosed_quantity: int = None) -> str:
    """
    Place a new order in OpenAlgo.

    Args:
        symbol: Trading symbol (e.g., SBIN, RELIANCE)
        quantity: Order quantity
        action: BUY or SELL
        exchange: Exchange (NSE, BSE, NFO, etc.)
        price_type: MARKET, LIMIT, SL, SL-M (default: MARKET)
        product: MIS, CNC, NRML (default: MIS)
        strategy: Strategy name (default: Python)
        price: Order price (required for LIMIT, SL orders)
        trigger_price: Trigger price (required for SL, SL-M orders)
        disclosed_quantity: Disclosed quantity
    """
    try:
        logging.info(f"Placing order: {action} {quantity} {symbol} on {exchange} as {price_type} for {product}")
        params = {
            "strategy": strategy,
            "symbol": symbol.upper(),
            "action": action.upper(),
            "exchange": exchange.upper(),
            "price_type": price_type.upper(),
            "product": product.upper(),
            "quantity": quantity
        }
        if price is not None:
            params["price"] = price
        if trigger_price is not None:
            params["trigger_price"] = trigger_price
        if disclosed_quantity is not None:
            params["disclosed_quantity"] = disclosed_quantity

        response = client.placeorder(**params)
        return f"Order placed: {response}"
    except Exception as e:
        logging.error(f"Error placing order: {str(e)}")
        return f"Error placing order: {str(e)}"

@mcp.tool()
def get_quote(symbol: str, exchange: str = "NSE") -> str:
    """
    Get market quotes for a symbol.
    
    Args:
        symbol: Trading symbol (e.g., SBIN, RELIANCE)
        exchange: Exchange (NSE, BSE, etc.)
    """
    try:
        # Log the request parameters
        logging.info(f"QUOTES REQUEST - Symbol: {symbol.upper()}, Exchange: {exchange.upper()}, API Key: {API_KEY[:5]}...{API_KEY[-5:]}")
        
        # Make the API call with debug=True to log the raw HTTP request
        quote = client.quotes(symbol=symbol.upper(), exchange=exchange.upper())
        
        # Log the success response
        logging.info(f"QUOTES RESPONSE - Success: {quote}")
        return str(quote)
    except Exception as e:
        # Log the detailed error
        logging.error(f"QUOTES ERROR - {str(e)}")
        import traceback
        logging.error(f"QUOTES TRACEBACK: {traceback.format_exc()}")
        return f"Error getting quotes: {str(e)}"

@mcp.tool()
def get_depth(symbol: str, exchange: str = "NSE") -> str:
    try:
        return str(client.depth(symbol=symbol.upper(), exchange=exchange.upper()))
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_history(symbol: str, exchange: str, interval: str, start_date: str, end_date: str) -> str:
    try:
        return str(client.history(symbol=symbol.upper(), exchange=exchange.upper(), interval=interval, start_date=start_date, end_date=end_date))
    except Exception as e:
        return f"Error fetching history: {str(e)}"

@mcp.tool()
def get_intervals() -> str:
    """Get available intervals for historical data."""
    try:
        logging.info("Getting available intervals")
        result = client.intervals()
        return str(result)
    except Exception as e:
        logging.error(f"Error getting intervals: {str(e)}")
        import traceback
        logging.error(f"INTERVALS TRACEBACK: {traceback.format_exc()}")
        return f"Error getting intervals: {str(e)}"

@mcp.tool()
def get_symbol_metadata(symbol: str, exchange: str) -> str:
    """Get metadata for a specific symbol."""
    try:
        logging.info(f"Getting metadata for {symbol.upper()} on {exchange.upper()}")
        result = client.symbol(symbol=symbol.upper(), exchange=exchange.upper())
        return str(result)
    except Exception as e:
        logging.error(f"Error getting symbol metadata: {str(e)}")
        import traceback
        logging.error(f"SYMBOL METADATA TRACEBACK: {traceback.format_exc()}")
        return f"Error getting symbol metadata: {str(e)}"

@mcp.tool()
def get_all_tickers(exchange: str = None) -> str:
    """
    Get all available tickers/symbols.
    
    Args:
        exchange: Optional exchange filter (NSE, BSE, etc.)
    """
    try:
        params = {}
        if exchange:
            params["exchange"] = exchange.upper()
            
        result = client.ticker(**params)
        return str(result)
    except Exception as e:
        logging.error(f"Error fetching tickers: {str(e)}")
        return f"Error fetching tickers: {str(e)}"

@mcp.tool()
def get_funds() -> str:
    """
    Get available funds and margin information.
    """
    try:
        # Log the request
        logging.info(f"FUNDS REQUEST - API Key: {API_KEY[:5]}...{API_KEY[-5:]}")
        
        # Make the API call
        result = client.funds()
        
        # Log the success response
        logging.info(f"FUNDS RESPONSE - Success: {result}")
        return str(result)
    except Exception as e:
        # Log the detailed error
        logging.error(f"FUNDS ERROR - {str(e)}")
        import traceback
        logging.error(f"FUNDS TRACEBACK: {traceback.format_exc()}")
        return f"Error getting funds: {str(e)}"

@mcp.tool()
def get_orders() -> str:
    """Get all orders for the current strategy."""
    try:
        logging.info("Getting orders for strategy Python")
        result = client.orderbook()
        return str(result)
    except Exception as e:
        logging.error(f"Error getting orders: {str(e)}")
        import traceback
        logging.error(f"ORDERS TRACEBACK: {traceback.format_exc()}")
        return f"Error getting orders: {str(e)}"

@mcp.tool()
def modify_order(order_id: str, symbol: str, action: str, exchange: str, product: str, quantity: int, price: float, price_type: str = "LIMIT", strategy: str = "Python", disclosed_quantity: int = 0, trigger_price: float = 0) -> str:
    """
    Modify an existing order.

    Args:
        order_id: Order ID to modify
        symbol: Trading symbol
        action: Order action (BUY/SELL)
        exchange: Exchange (NSE, BSE, etc.)
        product: Product type (MIS, CNC, NRML)
        quantity: New quantity
        price: New price
        price_type: LIMIT, SL, SL-M (default: LIMIT)
        strategy: Strategy name (default: Python)
        disclosed_quantity: Disclosed quantity (default: 0)
        trigger_price: Trigger price for SL orders (default: 0)
    """
    try:
        logging.info(f"Modifying order {order_id}: {symbol} {action} qty={quantity} price={price}")
        result = client.modifyorder(
            order_id=order_id,
            strategy=strategy,
            symbol=symbol.upper(),
            action=action.upper(),
            exchange=exchange.upper(),
            price_type=price_type.upper(),
            product=product.upper(),
            quantity=quantity,
            price=price,
            disclosed_quantity=disclosed_quantity,
            trigger_price=trigger_price
        )
        return str(result)
    except Exception as e:
        logging.error(f"Error modifying order: {str(e)}")
        return f"Error modifying order: {str(e)}"

@mcp.tool()
def cancel_order(order_id: str) -> str:
    """Cancel a specific order by ID."""
    try:
        logging.info(f"Cancelling order {order_id}")
        result = client.cancelorder(order_id=order_id, strategy="Python")
        return str(result)
    except Exception as e:
        logging.error(f"Error cancelling order: {str(e)}")
        import traceback
        logging.error(f"CANCEL ORDER TRACEBACK: {traceback.format_exc()}")
        return f"Error cancelling order: {str(e)}"

@mcp.tool()
def cancel_all_orders() -> str:
    """Cancel all open orders for the current strategy."""
    try:
        logging.info("Cancelling all orders for strategy Python")
        result = client.cancelallorder(strategy="Python")
        return str(result)
    except Exception as e:
        logging.error(f"Error cancelling all orders: {str(e)}")
        import traceback
        logging.error(f"CANCEL ALL ORDERS TRACEBACK: {traceback.format_exc()}")
        return f"Error cancelling all orders: {str(e)}"

@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Get status of a specific order by ID."""
    try:
        logging.info(f"Getting status for order {order_id}")
        result = client.orderstatus(order_id=order_id, strategy="Python")
        return str(result)
    except Exception as e:
        logging.error(f"Error getting order status: {str(e)}")
        import traceback
        logging.error(f"ORDER STATUS TRACEBACK: {traceback.format_exc()}")
        return f"Error getting order status: {str(e)}"

@mcp.tool()
def get_open_position(symbol: str, exchange: str, product: str) -> str:
    """Get details of an open position for a specific symbol."""
    try:
        logging.info(f"Getting open position for {symbol} on {exchange} with product {product}")
        result = client.openposition(strategy="Python", symbol=symbol, exchange=exchange, product=product)
        return str(result)
    except Exception as e:
        logging.error(f"Error getting open position: {str(e)}")
        import traceback
        logging.error(f"OPEN POSITION TRACEBACK: {traceback.format_exc()}")
        return f"Error getting open position: {str(e)}"

@mcp.tool()
def close_all_positions() -> str:
    """Close all open positions for the current strategy."""
    try:
        logging.info("Closing all positions for strategy Python")
        result = client.closeposition(strategy="Python")
        return str(result)
    except Exception as e:
        logging.error(f"Error closing all positions: {str(e)}")
        import traceback
        logging.error(f"CLOSE POSITIONS TRACEBACK: {traceback.format_exc()}")
        return f"Error closing all positions: {str(e)}"

@mcp.tool()
def get_position_book() -> str:
    """Get details of all current positions."""
    try:
        logging.info("Getting position book")
        result = client.positionbook()
        return str(result)
    except Exception as e:
        logging.error(f"Error getting position book: {str(e)}")
        import traceback
        logging.error(f"POSITION BOOK TRACEBACK: {traceback.format_exc()}")
        return f"Error getting position book: {str(e)}"

@mcp.tool()
def get_order_book() -> str:
    """Get details of all orders."""
    try:
        logging.info("Getting order book")
        result = client.orderbook()
        return str(result)
    except Exception as e:
        logging.error(f"Error getting order book: {str(e)}")
        import traceback
        logging.error(f"ORDER BOOK TRACEBACK: {traceback.format_exc()}")
        return f"Error getting order book: {str(e)}"

@mcp.tool()
def get_trade_book() -> str:
    """Get details of all executed trades."""
    try:
        logging.info("Getting trade book")
        result = client.tradebook()
        return str(result)
    except Exception as e:
        logging.error(f"Error getting trade book: {str(e)}")
        import traceback
        logging.error(f"TRADE BOOK TRACEBACK: {traceback.format_exc()}")
        return f"Error getting trade book: {str(e)}"

@mcp.tool()
def get_holdings() -> str:
    try:
        result = client.holdings()
        return str(result)
    except Exception as e:
        logging.error(f"Error fetching holdings: {str(e)}")
        return f"Error fetching holdings: {str(e)}"

@mcp.tool()
def place_basket_order(orders: list, strategy: str = "Python") -> str:
    """
    Place multiple orders at once using basket order functionality.

    Args:
        orders: List of order dictionaries with required fields:
               - symbol: Trading symbol
               - exchange: Exchange (NSE, BSE, etc.)
               - action: BUY or SELL
               - quantity: Order quantity
               - pricetype: MARKET, LIMIT, SL, SL-M
               - product: MIS, CNC, NRML
        strategy: Strategy name (default: Python)

    Example input format:
    [
        {
            "symbol": "SBIN",
            "exchange": "NSE",
            "action": "BUY",
            "quantity": 1,
            "pricetype": "MARKET",
            "product": "MIS"
        },
        {
            "symbol": "RELIANCE",
            "exchange": "NSE",
            "action": "SELL",
            "quantity": 1,
            "pricetype": "MARKET",
            "product": "MIS"
        }
    ]
    """
    try:
        logging.info(f"Placing basket order with {len(orders)} orders")
        response = client.basketorder(strategy=strategy, orders=orders)
        return str(response)
    except Exception as e:
        logging.error(f"Error placing basket order: {str(e)}")
        return f"Error placing basket order: {str(e)}"

@mcp.tool()
def place_split_order(symbol: str, exchange: str, action: str, quantity: int, splitsize: int, price_type: str = "MARKET", product: str = "MIS", price: float = 0, trigger_price: float = 0, strategy: str = "Python") -> str:
    """
    Split a large order into multiple smaller orders to reduce market impact.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange (NSE, BSE, etc.)
        action: BUY or SELL
        quantity: Total order quantity
        splitsize: Size of each split order
        price_type: MARKET, LIMIT, SL, SL-M
        product: MIS, CNC, NRML
        price: Order price (for LIMIT orders)
        trigger_price: Trigger price (for SL orders)
        strategy: Strategy name (default: Python)
    """
    try:
        logging.info(f"Placing split order: {action} {quantity} {symbol} (split size: {splitsize})")
        params = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "splitsize": splitsize,
            "price_type": price_type.upper(),
            "product": product.upper()
        }
        
        # Add optional parameters if relevant
        if price and price_type.upper() in ["LIMIT", "SL"]:
            params["price"] = price
        if trigger_price and price_type.upper() in ["SL", "SL-M"]:
            params["trigger_price"] = trigger_price
        if strategy:
            params["strategy"] = strategy
            
        response = client.splitorder(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error placing split order: {str(e)}")
        return f"Error placing split order: {str(e)}"

@mcp.tool()
def place_smart_order(symbol: str, action: str, quantity: int, position_size: int, exchange: str = "NSE", price_type: str = "MARKET", product: str = "MIS", strategy: str = "Python", price: float = None, trigger_price: float = None, disclosed_quantity: int = None) -> str:
    """
    Place a smart order that considers the current position size.

    Args:
        symbol: Trading symbol
        action: BUY or SELL
        quantity: Order quantity
        position_size: Target position size
        exchange: Exchange (NSE, BSE, etc.)
        price_type: MARKET, LIMIT, SL, SL-M (default: MARKET)
        product: MIS, CNC, NRML (default: MIS)
        strategy: Strategy name (default: Python)
        price: Limit price (required for LIMIT orders)
        trigger_price: Trigger price (required for SL orders)
        disclosed_quantity: Disclosed quantity
    """
    try:
        logging.info(f"Placing smart order: {action} {quantity} {symbol} with position size {position_size}")
        params = {
            "strategy": strategy,
            "symbol": symbol.upper(),
            "action": action.upper(),
            "exchange": exchange.upper(),
            "price_type": price_type.upper(),
            "product": product.upper(),
            "quantity": quantity,
            "position_size": position_size
        }
        if price is not None:
            params["price"] = price
        if trigger_price is not None:
            params["trigger_price"] = trigger_price
        if disclosed_quantity is not None:
            params["disclosed_quantity"] = disclosed_quantity

        response = client.placesmartorder(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error placing smart order: {str(e)}")
        return f"Error placing smart order: {str(e)}"

# OPTIONS TRADING TOOLS

@mcp.tool()
def place_options_order(underlying: str, exchange: str, offset: str, option_type: str, action: str, quantity: int, expiry_date: str = None, strategy: str = "Python", price_type: str = "MARKET", product: str = "MIS", price: float = None, trigger_price: float = None) -> str:
    """
    Place an options order with ATM/ITM/OTM offset.

    Args:
        underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY', 'NIFTY28OCT25FUT')
        exchange: Exchange for underlying ('NSE_INDEX', 'BSE_INDEX', 'NFO')
        offset: Strike offset - 'ATM', 'ITM1'-'ITM50', 'OTM1'-'OTM50'
        option_type: 'CE' for Call or 'PE' for Put
        action: 'BUY' or 'SELL'
        quantity: Number of lots (must be multiple of lot size)
        expiry_date: Expiry date in format 'DDMMMYY' (e.g., '28OCT25'). Optional if underlying includes expiry.
        strategy: Strategy name (default: Python)
        price_type: 'MARKET', 'LIMIT', 'SL', 'SL-M' (default: MARKET)
        product: 'MIS', 'NRML' (default: MIS)
        price: Limit price (required for LIMIT orders)
        trigger_price: Trigger price (required for SL and SL-M orders)
    """
    try:
        params = {
            "strategy": strategy,
            "underlying": underlying.upper(),
            "exchange": exchange.upper(),
            "offset": offset.upper(),
            "option_type": option_type.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "price_type": price_type.upper(),
            "product": product.upper()
        }
        if expiry_date:
            params["expiry_date"] = expiry_date
        if price is not None:
            params["price"] = price
        if trigger_price is not None:
            params["trigger_price"] = trigger_price

        logging.info(f"Placing options order: {action} {quantity} {underlying} {offset} {option_type}")
        response = client.optionsorder(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error placing options order: {str(e)}")
        return f"Error placing options order: {str(e)}"

@mcp.tool()
def place_options_multi_order(strategy: str, underlying: str, exchange: str, legs: list, expiry_date: str = None) -> str:
    """
    Place a multi-leg options order (spreads, iron condor, straddles, etc.).

    Args:
        strategy: Strategy name (required)
        underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
        exchange: Exchange for underlying ('NSE_INDEX', 'BSE_INDEX', 'NFO')
        legs: List of leg dictionaries (1-20 legs). Each leg must contain:
            - offset: Strike offset ('ATM', 'ITM1'-'ITM50', 'OTM1'-'OTM50')
            - option_type: 'CE' for Call or 'PE' for Put
            - action: 'BUY' or 'SELL'
            - quantity: Number of lots
            Optional: expiry_date, pricetype, product, price, trigger_price
        expiry_date: Default expiry date in format 'DDMMMYY' for all legs

    Example legs for Iron Condor:
        [
            {"offset": "OTM10", "option_type": "CE", "action": "BUY", "quantity": 75},
            {"offset": "OTM10", "option_type": "PE", "action": "BUY", "quantity": 75},
            {"offset": "OTM5", "option_type": "CE", "action": "SELL", "quantity": 75},
            {"offset": "OTM5", "option_type": "PE", "action": "SELL", "quantity": 75}
        ]
    """
    try:
        params = {
            "strategy": strategy,
            "underlying": underlying.upper(),
            "exchange": exchange.upper(),
            "legs": legs
        }
        if expiry_date:
            params["expiry_date"] = expiry_date

        logging.info(f"Placing options multi order: {len(legs)} legs on {underlying}")
        response = client.optionsmultiorder(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error placing options multi order: {str(e)}")
        return f"Error placing options multi order: {str(e)}"

@mcp.tool()
def get_option_symbol(underlying: str, exchange: str, offset: str, option_type: str, expiry_date: str = None) -> str:
    """
    Get option symbol for specific strike and expiry.

    Args:
        underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
        exchange: Exchange for underlying ('NSE_INDEX', 'BSE_INDEX')
        offset: Strike offset - 'ATM', 'ITM1'-'ITM50', 'OTM1'-'OTM50'
        option_type: 'CE' for Call or 'PE' for Put
        expiry_date: Expiry date in format 'DDMMMYY' (e.g., '28OCT25')
    """
    try:
        params = {
            "underlying": underlying.upper(),
            "exchange": exchange.upper(),
            "offset": offset.upper(),
            "option_type": option_type.upper()
        }
        if expiry_date:
            params["expiry_date"] = expiry_date

        response = client.optionsymbol(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error getting option symbol: {str(e)}")
        return f"Error getting option symbol: {str(e)}"

@mcp.tool()
def get_option_chain(underlying: str, exchange: str, expiry_date: str = None, strike_count: int = None) -> str:
    """
    Get option chain data with real-time quotes for all strikes.

    Args:
        underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY', 'RELIANCE')
        exchange: Exchange code (NSE_INDEX, NSE, NFO, BSE_INDEX, BSE, BFO)
        expiry_date: Expiry date in DDMMMYY format (e.g., '30DEC25')
        strike_count: Number of strikes above and below ATM (1-100)
    """
    try:
        params = {
            "underlying": underlying.upper(),
            "exchange": exchange.upper()
        }
        if expiry_date:
            params["expiry_date"] = expiry_date
        if strike_count:
            params["strike_count"] = strike_count

        response = client.optionchain(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error getting option chain: {str(e)}")
        return f"Error getting option chain: {str(e)}"

@mcp.tool()
def get_option_greeks(symbol: str, exchange: str, interest_rate: float = 0.0, underlying_symbol: str = None, underlying_exchange: str = None) -> str:
    """
    Calculate option Greeks (delta, gamma, theta, vega, rho).

    Args:
        symbol: Option symbol (e.g., 'NIFTY25NOV2526000CE')
        exchange: Exchange name (typically 'NFO')
        interest_rate: Risk-free interest rate (default: 0.0)
        underlying_symbol: Underlying symbol (e.g., 'NIFTY')
        underlying_exchange: Underlying exchange ('NSE_INDEX')
    """
    try:
        params = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "interest_rate": interest_rate
        }
        if underlying_symbol:
            params["underlying_symbol"] = underlying_symbol.upper()
        if underlying_exchange:
            params["underlying_exchange"] = underlying_exchange.upper()

        response = client.optiongreeks(**params)
        return str(response)
    except Exception as e:
        logging.error(f"Error calculating option greeks: {str(e)}")
        return f"Error calculating option greeks: {str(e)}"

@mcp.tool()
def get_synthetic_future(underlying: str, exchange: str, expiry_date: str) -> str:
    """
    Calculate synthetic future price using put-call parity.

    Args:
        underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
        exchange: Exchange for underlying ('NSE_INDEX', 'BSE_INDEX')
        expiry_date: Expiry date in format 'DDMMMYY' (e.g., '25NOV25')
    """
    try:
        response = client.syntheticfuture(
            underlying=underlying.upper(),
            exchange=exchange.upper(),
            expiry_date=expiry_date
        )
        return str(response)
    except Exception as e:
        logging.error(f"Error calculating synthetic future: {str(e)}")
        return f"Error calculating synthetic future: {str(e)}"

# MARKET DATA TOOLS

@mcp.tool()
def get_multi_quotes(symbols: list) -> str:
    """
    Get real-time quotes for multiple symbols in a single request.

    Args:
        symbols: List of symbol-exchange pairs
        Example: [{"symbol": "RELIANCE", "exchange": "NSE"}, {"symbol": "INFY", "exchange": "NSE"}]
    """
    try:
        normalized = [{"symbol": s["symbol"].upper(), "exchange": s["exchange"].upper()} for s in symbols]
        response = client.multiquotes(symbols=normalized)
        return str(response)
    except Exception as e:
        logging.error(f"Error getting multi quotes: {str(e)}")
        return f"Error getting multi quotes: {str(e)}"

@mcp.tool()
def search_instruments(query: str, exchange: str = "NSE") -> str:
    """
    Search for instruments by name or symbol.

    Args:
        query: Search query
        exchange: Exchange to search in (NSE, BSE, NFO, etc.)
    """
    try:
        response = client.search(query=query, exchange=exchange.upper())
        return str(response)
    except Exception as e:
        logging.error(f"Error searching instruments: {str(e)}")
        return f"Error searching instruments: {str(e)}"

@mcp.tool()
def get_expiry_dates(symbol: str, exchange: str = "NFO", instrument_type: str = "options") -> str:
    """
    Get expiry dates for derivatives.

    Args:
        symbol: Underlying symbol
        exchange: Exchange name (typically NFO for F&O)
        instrument_type: 'options' or 'futures'
    """
    try:
        response = client.expiry(
            symbol=symbol.upper(),
            exchange=exchange.upper(),
            instrumenttype=instrument_type.lower()
        )
        return str(response)
    except Exception as e:
        logging.error(f"Error getting expiry dates: {str(e)}")
        return f"Error getting expiry dates: {str(e)}"

@mcp.tool()
def get_instruments(exchange: str) -> str:
    """
    Download all instruments for an exchange.

    Args:
        exchange: Exchange name (NSE, BSE, NFO, BFO, MCX, CDS, BCD, NCDEX)
    """
    try:
        response = client.instruments(exchange=exchange.upper())
        return str(response)
    except Exception as e:
        logging.error(f"Error getting instruments: {str(e)}")
        return f"Error getting instruments: {str(e)}"

# UTILITIES

@mcp.tool()
def get_holidays(year: int) -> str:
    """
    Get trading holidays for a specific year.

    Args:
        year: Year to get holidays for (e.g., 2025)
    """
    try:
        response = client.holidays(year=year)
        return str(response)
    except Exception as e:
        logging.error(f"Error getting holidays: {str(e)}")
        return f"Error getting holidays: {str(e)}"

@mcp.tool()
def get_timings(date: str) -> str:
    """
    Get exchange trading timings for a specific date.

    Args:
        date: Date in YYYY-MM-DD format (e.g., '2025-12-23')
    """
    try:
        response = client.timings(date=date)
        return str(response)
    except Exception as e:
        logging.error(f"Error getting timings: {str(e)}")
        return f"Error getting timings: {str(e)}"

@mcp.tool()
def send_telegram_alert(username: str, message: str) -> str:
    """
    Send a Telegram alert notification.

    Args:
        username: OpenAlgo login ID/username
        message: Alert message to send
    """
    try:
        response = client.telegram(username=username, message=message)
        return str(response)
    except Exception as e:
        logging.error(f"Error sending telegram alert: {str(e)}")
        return f"Error sending telegram alert: {str(e)}"

@mcp.tool()
def calculate_margin(positions: list) -> str:
    """
    Calculate margin requirements for positions.

    Args:
        positions: List of position dictionaries
        Example: [{"symbol": "NIFTY25NOV2525000CE", "exchange": "NFO", "action": "BUY", "product": "NRML", "pricetype": "MARKET", "quantity": "75"}]
    """
    try:
        response = client.margin(positions=positions)
        return str(response)
    except Exception as e:
        logging.error(f"Error calculating margin: {str(e)}")
        return f"Error calculating margin: {str(e)}"

@mcp.tool()
def analyzer_status() -> str:
    """Get the current analyzer status including mode and total logs."""
    try:
        response = client.analyzerstatus()
        return str(response)
    except Exception as e:
        logging.error(f"Error getting analyzer status: {str(e)}")
        return f"Error getting analyzer status: {str(e)}"

@mcp.tool()
def analyzer_toggle(mode: bool) -> str:
    """
    Toggle the analyzer mode between analyze (simulated) and live trading.

    Args:
        mode: True for analyze mode (simulated), False for live mode
    """
    try:
        response = client.analyzertoggle(mode=mode)
        return str(response)
    except Exception as e:
        logging.error(f"Error toggling analyzer: {str(e)}")
        return f"Error toggling analyzer: {str(e)}"

# Create a Starlette app for the SSE transport
if MODE == 'sse':
    from starlette.routing import Route
    from mcp.server.sse import SseServerTransport
    
    # Create an SSE transport on the /messages/ endpoint
    sse = SseServerTransport("/messages/")
    
    # Define an async SSE handler that will process incoming connections
    async def handle_sse(request):
        logging.info(f"New SSE connection from {request.client}")
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp._mcp_server.run(
                streams[0],
                streams[1],
                mcp._mcp_server.create_initialization_options(),
            )
    
    # Set up Starlette app with both SSE connection and message posting endpoints
    app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        on_startup=[
            lambda: logging.info("OpenAlgo MCP Server started")
        ],
        on_shutdown=[
            lambda: logging.info("OpenAlgo MCP Server shutting down")
        ]
    )

# Run the server
if __name__ == "__main__":
    logging.info("Starting OpenAlgo MCP Server...")
    
    if MODE == 'stdio':
        # Run in stdio mode for terminal/command line usage
        mcp.run(transport="stdio")
    else:
        # Run in SSE mode with Uvicorn for web interface
        uvicorn.run(
            "server:app",
            host="0.0.0.0",
            port=PORT,
            log_level="info",
            reload=True,
            access_log=True
        )
