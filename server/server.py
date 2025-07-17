from mcp.server.fastmcp import FastMCP
from openalgo import api
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Find and load the common .env file from the parent directory
parent_dir = Path(__file__).resolve().parent.parent
env_path = parent_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    load_dotenv()  # Fall back to local .env file if common one doesn't exist
    logger.info("Loaded environment from local .env file")

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

# Initialize OpenAlgo API client
logger.info(f"Initializing OpenAlgo client with host: {API_HOST}")
try:
    client = api(api_key=API_KEY, host=API_HOST)
    logger.info(f"Successfully initialized OpenAlgo client")
except Exception as e:
    logger.error(f"Error initializing OpenAlgo client: {str(e)}")
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

# Add this to your server/server.py file before the tool definitions

import json
from typing import Dict, List, Any

class ResponseFormatter:
    """Helper class to format API responses for better readability"""
    
    @staticmethod
    def format_funds(response: dict) -> str:
        """Format funds response into readable markdown table"""
        try:
            if isinstance(response, str):
                response = json.loads(response)
            
            if response.get('status') != 'success':
                return f"❌ **Error:** {response.get('message', 'Unable to fetch funds data')}"
            
            data = response.get('data', {})
            
            # Format the table
            formatted = """## 💰 Account Funds Summary

| **Category** | **Amount (₹)** |
|--------------|----------------|"""
            
            # Add each fund category
            categories = [
                ('Available Cash', data.get('availablecash', '0.00')),
                ('Collateral', data.get('collateral', '0.00')),
                ('M2M Realized', data.get('m2mrealized', '0.00')),
                ('M2M Unrealized', data.get('m2munrealized', '0.00')),
                ('Utilized Debits', data.get('utilizeddebits', '0.00'))
            ]
            
            for category, amount in categories:
                formatted += f"\n| {category} | {amount} |"
            
            # Add summary
            available = float(data.get('availablecash', 0))
            utilized = float(data.get('utilizeddebits', 0))
            m2m_realized = float(data.get('m2mrealized', 0))
            
            formatted += f"""

### 📊 Key Insights:
- ✅ **Available for trading:** ₹{available:,.2f}
- 📈 **Total utilized:** ₹{utilized:,.2f}
- 📊 **Realized P&L:** ₹{m2m_realized:,.2f}"""
            
            if m2m_realized > 0:
                formatted += " 🟢"
            elif m2m_realized < 0:
                formatted += " 🔴"
                
            return formatted
            
        except Exception as e:
            return f"❌ **Error formatting funds data:** {str(e)}"
    
    @staticmethod
    def format_holdings(response: dict) -> str:
        """Format holdings response into readable markdown table"""
        try:
            if isinstance(response, str):
                response = json.loads(response)
            
            if response.get('status') != 'success':
                return f"❌ **Error:** {response.get('message', 'Unable to fetch holdings data')}"
            
            data = response.get('data', [])
            
            if not data:
                return """## 📈 Portfolio Holdings

**No holdings found in your portfolio.**

Consider adding some positions to start building your portfolio! 🚀"""
            
            # Format the table
            formatted = """## 📈 Portfolio Holdings

| **Symbol** | **Exchange** | **Qty** | **Product** | **P&L (₹)** | **P&L %** |
|------------|--------------|---------|-------------|-------------|-----------|"""
            
            total_investment = 0
            total_current_value = 0
            
            for holding in data:
                symbol = holding.get('symbol', 'N/A')
                exchange = holding.get('exchange', 'N/A')
                qty = holding.get('quantity', 0)
                product = holding.get('product', 'N/A')
                pnl = float(holding.get('pnl', 0))
                pnl_percent = float(holding.get('pnlpercent', 0))
                
                # Add color coding for P&L
                pnl_color = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                
                formatted += f"\n| {symbol} | {exchange} | {qty} | {product} | {pnl:+.2f} {pnl_color} | {pnl_percent:+.2f}% |"
                
                # Calculate totals (if available)
                if 'investment' in holding:
                    total_investment += float(holding.get('investment', 0))
                if 'currentvalue' in holding:
                    total_current_value += float(holding.get('currentvalue', 0))
            
            # Add summary if we have the data
            if total_investment > 0:
                total_pnl = total_current_value - total_investment
                total_pnl_percent = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
                
                pnl_emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
                
                formatted += f"""

### 📊 Portfolio Summary:
- **Total Holdings:** {len(data)}
- **Total Investment:** ₹{total_investment:,.2f}
- **Current Value:** ₹{total_current_value:,.2f}
- **Total P&L:** ₹{total_pnl:+,.2f} ({total_pnl_percent:+.2f}%) {pnl_emoji}"""
            
            return formatted
            
        except Exception as e:
            return f"❌ **Error formatting holdings data:** {str(e)}"
    
    @staticmethod
    def format_quote(response: dict, symbol: str) -> str:
        """Format quote response into readable format"""
        try:
            if isinstance(response, str):
                response = json.loads(response)
            
            if response.get('status') != 'success':
                return f"❌ **Error:** {response.get('message', f'Unable to fetch quote for {symbol}')}"
            
            data = response.get('data', {})
            
            formatted = f"""## 📊 {symbol.upper()} Market Quote

### Current Price Information:"""
            
            # Main price info
            ltp = data.get('ltp', 'N/A')
            prev_close = data.get('close', 'N/A')
            
            if ltp != 'N/A' and prev_close != 'N/A':
                try:
                    change = float(ltp) - float(prev_close)
                    change_percent = (change / float(prev_close)) * 100
                    change_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    
                    formatted += f"""
- **Last Traded Price (LTP):** ₹{ltp}
- **Previous Close:** ₹{prev_close}
- **Change:** ₹{change:+.2f} ({change_percent:+.2f}%) {change_emoji}"""
                except:
                    formatted += f"""
- **Last Traded Price (LTP):** ₹{ltp}
- **Previous Close:** ₹{prev_close}"""
            else:
                formatted += f"""
- **Last Traded Price (LTP):** ₹{ltp}
- **Previous Close:** ₹{prev_close}"""
            
            # Additional data if available
            if data.get('open') != 'N/A':
                formatted += f"\n- **Open:** ₹{data.get('open')}"
            if data.get('high') != 'N/A':
                formatted += f"\n- **High:** ₹{data.get('high')}"
            if data.get('low') != 'N/A':
                formatted += f"\n- **Low:** ₹{data.get('low')}"
            
            # Market status
            formatted += """

### Market Status:
- ⏰ **Real-time data** (during market hours)
- 📊 Use this data for informed trading decisions"""
            
            return formatted
            
        except Exception as e:
            return f"❌ **Error formatting quote data:** {str(e)}"
    
    @staticmethod
    def format_orders(response: dict) -> str:
        """Format orders response into readable markdown table"""
        try:
            if isinstance(response, str):
                response = json.loads(response)
            
            if response.get('status') != 'success':
                return f"❌ **Error:** {response.get('message', 'Unable to fetch orders data')}"
            
            data = response.get('data', [])
            
            if not data:
                return """## 📋 Order Book

**No orders found.**

Place your first order to start trading! 🚀"""
            
            # Format the table
            formatted = """## 📋 Order Book

| **Order ID** | **Symbol** | **Action** | **Qty** | **Price** | **Status** | **Time** |
|--------------|------------|------------|---------|-----------|------------|----------|"""
            
            status_counts = {'complete': 0, 'pending': 0, 'rejected': 0, 'cancelled': 0}
            
            for order in data:
                order_id = str(order.get('orderid', 'N/A'))[:8] + '...' if len(str(order.get('orderid', ''))) > 8 else str(order.get('orderid', 'N/A'))
                symbol = order.get('symbol', 'N/A')
                action = order.get('action', 'N/A')
                qty = order.get('quantity', 'N/A')
                price = order.get('price', 'N/A')
                status = order.get('status', 'N/A').lower()
                order_time = order.get('time', 'N/A')
                
                # Count statuses
                if status in status_counts:
                    status_counts[status] += 1
                
                # Format status with emoji
                status_emoji = {
                    'complete': '✅',
                    'pending': '⏳',
                    'rejected': '❌',
                    'cancelled': '🚫'
                }.get(status, '❓')
                
                formatted += f"\n| {order_id} | {symbol} | {action} | {qty} | ₹{price} | {status_emoji} {status.title()} | {order_time} |"
            
            # Add summary
            total_orders = len(data)
            formatted += f"""

### 📊 Order Summary:
- **Total Orders:** {total_orders}"""
            
            for status, count in status_counts.items():
                if count > 0:
                    status_emoji = {
                        'complete': '✅',
                        'pending': '⏳',
                        'rejected': '❌',
                        'cancelled': '🚫'
                    }.get(status, '❓')
                    formatted += f"\n- **{status.title()}:** {count} {status_emoji}"
            
            return formatted
            
        except Exception as e:
            return f"❌ **Error formatting orders data:** {str(e)}"

# Update the tool functions to use the formatter

@mcp.tool()
def get_funds() -> str:
    """Get available funds and margin information."""
    try:
        logger.info("Getting funds information")
        result = client.funds()
        logger.info("Successfully retrieved funds information")
        
        # Use the formatter for better output
        return ResponseFormatter.format_funds(result)
    except Exception as e:
        logger.error(f"Error getting funds: {str(e)}")
        return f"❌ **Error getting funds:** {str(e)}"

@mcp.tool()
def get_holdings() -> str:
    """Get portfolio holdings."""
    try:
        logger.info("Getting holdings")
        result = client.holdings()
        
        # Use the formatter for better output
        return ResponseFormatter.format_holdings(result)
    except Exception as e:
        logger.error(f"Error fetching holdings: {str(e)}")
        return f"❌ **Error fetching holdings:** {str(e)}"

@mcp.tool()
def get_quote(symbol: str, exchange: str = "NSE") -> str:
    """
    Get market quotes for a symbol.
    
    Args:
        symbol: Trading symbol (e.g., SBIN, RELIANCE)
        exchange: Exchange (NSE, BSE, etc.)
    """
    try:
        logger.info(f"Getting quotes for {symbol.upper()} on {exchange.upper()}")
        quote = client.quotes(symbol=symbol.upper(), exchange=exchange.upper())
        logger.info(f"Successfully retrieved quotes for {symbol}")
        
        # Use the formatter for better output
        return ResponseFormatter.format_quote(quote, symbol)
    except Exception as e:
        logger.error(f"Error getting quotes for {symbol}: {str(e)}")
        return f"❌ **Error getting quotes for {symbol}:** {str(e)}"

@mcp.tool()
def get_orders() -> str:
    """Get all orders for the current strategy."""
    try:
        logger.info("Getting orders")
        result = client.orderbook()
        
        # Use the formatter for better output
        return ResponseFormatter.format_orders(result)
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
        return f"❌ **Error getting orders:** {str(e)}"

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
        logger.info(f"Placing order: {action} {quantity} {symbol} on {exchange} as {price_type} for {product}")
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
        logger.error(f"Error placing order: {str(e)}")
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
        logger.info(f"Getting quotes for {symbol.upper()} on {exchange.upper()}")
        quote = client.quotes(symbol=symbol.upper(), exchange=exchange.upper())
        logger.info(f"Successfully retrieved quotes for {symbol}")
        return str(quote)
    except Exception as e:
        logger.error(f"Error getting quotes for {symbol}: {str(e)}")
        return f"Error getting quotes: {str(e)}"

@mcp.tool()
def get_depth(symbol: str, exchange: str = "NSE") -> str:
    """Get market depth for a symbol."""
    try:
        logger.info(f"Getting market depth for {symbol.upper()} on {exchange.upper()}")
        result = client.depth(symbol=symbol.upper(), exchange=exchange.upper())
        return str(result)
    except Exception as e:
        logger.error(f"Error getting market depth: {str(e)}")
        return f"Error getting market depth: {str(e)}"

@mcp.tool()
def get_history(symbol: str, exchange: str, interval: str, start_date: str, end_date: str) -> str:
    """Get historical data for a symbol."""
    try:
        logger.info(f"Getting history for {symbol.upper()} from {start_date} to {end_date}")
        result = client.history(
            symbol=symbol.upper(), 
            exchange=exchange.upper(), 
            interval=interval, 
            start_date=start_date, 
            end_date=end_date
        )
        return str(result)
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return f"Error fetching history: {str(e)}"

@mcp.tool()
def get_intervals() -> str:
    """Get available intervals for historical data."""
    try:
        logger.info("Getting available intervals")
        result = client.intervals()
        return str(result)
    except Exception as e:
        logger.error(f"Error getting intervals: {str(e)}")
        return f"Error getting intervals: {str(e)}"

@mcp.tool()
def get_symbol_metadata(symbol: str, exchange: str) -> str:
    """Get metadata for a specific symbol."""
    try:
        logger.info(f"Getting metadata for {symbol.upper()} on {exchange.upper()}")
        result = client.symbol(symbol=symbol.upper(), exchange=exchange.upper())
        return str(result)
    except Exception as e:
        logger.error(f"Error getting symbol metadata: {str(e)}")
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
        logger.error(f"Error fetching tickers: {str(e)}")
        return f"Error fetching tickers: {str(e)}"

@mcp.tool()
def get_funds() -> str:
    """Get available funds and margin information."""
    try:
        logger.info("Getting funds information")
        result = client.funds()
        logger.info("Successfully retrieved funds information")
        return str(result)
    except Exception as e:
        logger.error(f"Error getting funds: {str(e)}")
        return f"Error getting funds: {str(e)}"

@mcp.tool()
def get_orders() -> str:
    """Get all orders for the current strategy."""
    try:
        logger.info("Getting orders")
        result = client.orderbook()
        return str(result)
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
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
            "symbol": symbol.upper(), 
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
            
        logger.info(f"Modifying order {order_id}")
        result = client.modifyorder(**params)
        return str(result)
    except Exception as e:
        logger.error(f"Error modifying order: {str(e)}")
        return f"Error modifying order: {str(e)}"

@mcp.tool()
def cancel_order(order_id: str) -> str:
    """Cancel a specific order by ID."""
    try:
        logger.info(f"Cancelling order {order_id}")
        result = client.cancelorder(order_id=order_id, strategy="Python")
        return str(result)
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        return f"Error cancelling order: {str(e)}"

@mcp.tool()
def cancel_all_orders() -> str:
    """Cancel all open orders for the current strategy."""
    try:
        logger.info("Cancelling all orders")
        result = client.cancelallorder(strategy="Python")
        return str(result)
    except Exception as e:
        logger.error(f"Error cancelling all orders: {str(e)}")
        return f"Error cancelling all orders: {str(e)}"

@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Get status of a specific order by ID."""
    try:
        logger.info(f"Getting status for order {order_id}")
        result = client.orderstatus(order_id=order_id, strategy="Python")
        return str(result)
    except Exception as e:
        logger.error(f"Error getting order status: {str(e)}")
        return f"Error getting order status: {str(e)}"

@mcp.tool()
def get_open_position(symbol: str, exchange: str, product: str) -> str:
    """Get details of an open position for a specific symbol."""
    try:
        logger.info(f"Getting open position for {symbol}")
        result = client.openposition(strategy="Python", symbol=symbol, exchange=exchange, product=product)
        return str(result)
    except Exception as e:
        logger.error(f"Error getting open position: {str(e)}")
        return f"Error getting open position: {str(e)}"

@mcp.tool()
def close_all_positions() -> str:
    """Close all open positions for the current strategy."""
    try:
        logger.info("Closing all positions")
        result = client.closeposition(strategy="Python")
        return str(result)
    except Exception as e:
        logger.error(f"Error closing all positions: {str(e)}")
        return f"Error closing all positions: {str(e)}"

@mcp.tool()
def get_position_book() -> str:
    """Get details of all current positions."""
    try:
        logger.info("Getting position book")
        result = client.positionbook()
        return str(result)
    except Exception as e:
        logger.error(f"Error getting position book: {str(e)}")
        return f"Error getting position book: {str(e)}"

@mcp.tool()
def get_order_book() -> str:
    """Get details of all orders."""
    try:
        logger.info("Getting order book")
        result = client.orderbook()
        return str(result)
    except Exception as e:
        logger.error(f"Error getting order book: {str(e)}")
        return f"Error getting order book: {str(e)}"

@mcp.tool()
def get_trade_book() -> str:
    """Get details of all executed trades."""
    try:
        logger.info("Getting trade book")
        result = client.tradebook()
        return str(result)
    except Exception as e:
        logger.error(f"Error getting trade book: {str(e)}")
        return f"Error getting trade book: {str(e)}"

@mcp.tool()
def get_holdings() -> str:
    """Get portfolio holdings."""
    try:
        logger.info("Getting holdings")
        result = client.holdings()
        return str(result)
    except Exception as e:
        logger.error(f"Error fetching holdings: {str(e)}")
        return f"Error fetching holdings: {str(e)}"

@mcp.tool()
def place_basket_order(orders: list) -> str:
    """
    Place multiple orders at once using basket order functionality.
    
    Args:
        orders: List of order dictionaries with required fields
    """
    try:
        logger.info(f"Placing basket order with {len(orders)} orders")
        response = client.basketorder(orders=orders)
        return str(response)
    except Exception as e:
        logger.error(f"Error placing basket order: {str(e)}")
        return f"Error placing basket order: {str(e)}"

@mcp.tool()
def place_split_order(symbol: str, exchange: str, action: str, quantity: int, splitsize: int, price_type: str = "MARKET", product: str = "MIS", price: float = 0, trigger_price: float = 0, strategy: str = "Python") -> str:
    """
    Split a large order into multiple smaller orders to reduce market impact.
    """
    try:
        logger.info(f"Placing split order: {action} {quantity} {symbol} (split size: {splitsize})")
        params = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "splitsize": splitsize,
            "price_type": price_type.upper(),
            "product": product.upper(),
            "strategy": strategy
        }
        
        # Add optional parameters if relevant
        if price and price_type.upper() in ["LIMIT", "SL"]:
            params["price"] = price
        if trigger_price and price_type.upper() in ["SL", "SL-M"]:
            params["trigger_price"] = trigger_price
            
        response = client.splitorder(**params)
        return str(response)
    except Exception as e:
        logger.error(f"Error placing split order: {str(e)}")
        return f"Error placing split order: {str(e)}"

@mcp.tool()
def place_smart_order(symbol: str, action: str, quantity: int, position_size: int, exchange: str = "NSE", price_type: str = "MARKET", product: str = "MIS", strategy: str = "Python") -> str:
    """
    Place a smart order that considers the current position size.
    """
    try:
        logger.info(f"Placing smart order: {action} {quantity} {symbol}")
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
        logger.error(f"Error placing smart order: {str(e)}")
        return f"Error placing smart order: {str(e)}"

# Create a Starlette app for the SSE transport
if MODE == 'sse':
    from mcp.server.sse import SseServerTransport
    
    # Create an SSE transport on the /messages/ endpoint
    sse = SseServerTransport("/messages/")
    
    # Define an async SSE handler that will process incoming connections
    async def handle_sse(request):
        logger.info(f"New SSE connection from {request.client}")
        try:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp._mcp_server.run(
                    streams[0],
                    streams[1],
                    mcp._mcp_server.create_initialization_options(),
                )
        except Exception as e:
            logger.error(f"Error in SSE handler: {str(e)}")
            raise
    
    # Add health check endpoint
    async def health_check(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "message": "OpenAlgo MCP Server is running"})
    
    # Set up Starlette app with both SSE connection and message posting endpoints
    app = Starlette(
        debug=DEBUG,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health_check),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        on_startup=[
            lambda: logger.info("OpenAlgo MCP Server started")
        ],
        on_shutdown=[
            lambda: logger.info("OpenAlgo MCP Server shutting down")
        ]
    )

# Run the server
if __name__ == "__main__":
    logger.info("Starting OpenAlgo MCP Server...")
    
    if MODE == 'stdio':
        # Run in stdio mode for terminal/command line usage
        mcp.run(transport="stdio")
    else:
        # Run in SSE mode with Uvicorn for web interface
        logger.info(f"Starting SSE server on port {PORT}")
        uvicorn.run(
            "server:app",
            host="0.0.0.0",
            port=PORT,
            log_level="info",
            reload=DEBUG
        )