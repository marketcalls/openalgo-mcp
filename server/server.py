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
def place_order(symbol: str, quantity: int, action: str, exchange: str = "NSE", price_type: str = "MARKET", product: str = "MIS", strategy: str = "Python", price: float = 0.0, trigger_price: float = 0.0, disclosed_quantity: int = 0) -> str:
    """
    Place a new order in OpenAlgo.
    
    Args:
        symbol: Trading symbol (e.g., SBIN, RELIANCE)
        quantity: Order quantity
        action: BUY or SELL
        exchange: Exchange (NSE, BSE, etc.)
        price_type: MARKET, LIMIT, SL, SL-M
        product: MIS, CNC, NRML
        strategy: Strategy name (default: Python)
        price: Order price (required for LIMIT, SL orders)
        trigger_price: Trigger price (required for SL, SL-M orders)
        disclosed_quantity: Disclosed quantity
    """
    try:
        logging.info(f"Placing order: {action} {quantity} {symbol} on {exchange} as {price_type} for {product}")
        response = client.placeorder(
            strategy=strategy, 
            symbol=symbol.upper(), 
            action=action.upper(), 
            exchange=exchange.upper(), 
            price_type=price_type.upper(), 
            product=product.upper(), 
            quantity=quantity,
            price=price,
            trigger_price=trigger_price,
            disclosed_quantity=disclosed_quantity
        )
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
def modify_order(order_id: str, symbol: str, quantity: int, price: float, action: str = None, exchange: str = None, price_type: str = None, product: str = None, trigger_price: float = None, strategy: str = "Python") -> str:
    """
    Modify an existing order.
    
    Args:
        order_id: Order ID to modify
        symbol: Trading symbol
        quantity: New quantity
        price: New price
        action: New order action (BUY/SELL)
        exchange: Exchange (NSE, BSE, etc.)
        price_type: MARKET, LIMIT, SL, SL-M
        product: MIS, CNC, NRML
        trigger_price: New trigger price for SL, SL-M orders
        strategy: Strategy name (default: Python)
    """
    try:
        params = {
            "order_id": order_id, 
            "strategy": strategy, 
            "symbol": symbol, 
            "quantity": quantity,
            "price": price
        }
        
        # Add optional parameters if provided
        if action:
            params["action"] = action.upper()
        if exchange:
            params["exchange"] = exchange.upper()
        if price_type:
            params["price_type"] = price_type.upper()
        if product:
            params["product"] = product.upper()
        if trigger_price is not None:
            params["trigger_price"] = trigger_price
            
        logging.info(f"Modifying order {order_id}: {params}")
        result = client.modifyorder(**params)
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
def place_basket_order(orders: list) -> str:
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
        response = client.basketorder(orders=orders)
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
def place_smart_order(symbol: str, action: str, quantity: int, position_size: int, exchange: str = "NSE", price_type: str = "MARKET", product: str = "MIS", strategy: str = "Python") -> str:
    """
    Place a smart order that considers the current position size.
    
    Args:
        symbol: Trading symbol
        action: BUY or SELL
        quantity: Order quantity
        position_size: Current position size
        exchange: Exchange (NSE, BSE, etc.)
        price_type: MARKET, LIMIT, SL, SL-M
        product: MIS, CNC, NRML
        strategy: Strategy name (default: Python)
    """
    try:
        logging.info(f"Placing smart order: {action} {quantity} {symbol} with position size {position_size}")
        response = client.placesmartorder(
            strategy=strategy,
            symbol=symbol.upper(),
            action=action.upper(),
            exchange=exchange.upper(),
            price_type=price_type.upper(),
            product=product.upper(),
            quantity=quantity,
            position_size=position_size
        )
        return str(response)
    except Exception as e:
        logging.error(f"Error placing smart order: {str(e)}")
        return f"Error placing smart order: {str(e)}"

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
