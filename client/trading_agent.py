import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path
from agno.models.openai import OpenAIChat
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from mcp import ClientSession
from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme
from typing import Optional
from contextlib import AsyncExitStack
from mcp.client.sse import sse_client
from dotenv import load_dotenv

# Silence all logging
class SilentFilter(logging.Filter):
    def filter(self, record):
        return False

# Configure root logger to be silent
root_logger = logging.getLogger()
root_logger.addFilter(SilentFilter())
root_logger.setLevel(logging.CRITICAL)

# Silence specific loggers
for logger_name in ['agno', 'httpx', 'urllib3', 'asyncio']:
    logger = logging.getLogger(logger_name)
    logger.addFilter(SilentFilter())
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False

# Redirect stdout/stderr for the agno library
class DevNull:
    def write(self, msg): pass
    def flush(self): pass

sys.stderr = DevNull()

# Define custom theme
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "danger": "bold red",
    "success": "bold green",
    "query": "bold blue",
    "response": "bold green",
    "assistant": "bold magenta",
    "user": "bold magenta"
})

# Initialize rich console with custom theme
console = Console(theme=custom_theme)

# Find and load the common .env file from the parent directory
parent_dir = Path(__file__).resolve().parent.parent
env_path = parent_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from {env_path}")
else:
    # Fall back to local .env file if common one doesn't exist
    load_dotenv()
    print("Loaded environment from local .env file")

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an MCP server running with SSE transport"""
        print(f"Attempting to connect to MCP server at {server_url}")
        try:
            # Store the context managers so they stay alive
            self._streams_context = sse_client(url=server_url)
            streams = await self._streams_context.__aenter__()
            print("Successfully created SSE client streams")
            
            self._session_context = ClientSession(*streams)
            self.session: ClientSession = await self._session_context.__aenter__()
            print("Successfully created client session")
            
            # Initialize with detailed error handling
            try:
                await self.session.initialize()
                print("Successfully initialized MCP session")
            except Exception as e:
                print(f"Error during session initialization: {str(e)}")
                if hasattr(e, '__dict__'):
                    print(f"Error details: {e.__dict__}")
                raise
                
            # Try to verify connection by listing tools
            try:
                response = await self.session.list_tools()
                print(f"Successfully connected and retrieved tools from server")
            except Exception as e:
                print(f"Error listing tools: {str(e)}")
                if hasattr(e, '__dict__'):
                    print(f"Error details: {e.__dict__}")
                raise
                
        except Exception as e:
            print(f"Error connecting to MCP server: {str(e)}")
            if hasattr(e, '__dict__'):
                print(f"Error details: {e.__dict__}")
            raise

    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def disconnect(self):
        """Disconnect from the MCP server"""
        await self.cleanup()

# Helper class for OpenAlgo symbol format assistance
class SymbolHelper:
    @staticmethod
    def format_equity(symbol, exchange="NSE"):
        """Format equity symbol"""
        return symbol.upper()
    
    @staticmethod
    def format_future(base_symbol, expiry_year, expiry_month, expiry_date=None):
        """Format futures symbol
        Example: BANKNIFTY24APR24FUT
        """
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
            7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
        }
        
        # Handle month as string or int
        if isinstance(expiry_month, int):
            month_str = month_map[expiry_month]
        else:
            month_str = expiry_month.upper()
            
        # Format the date part
        if expiry_date:
            date_part = f"{expiry_date}"
        else:
            date_part = ""
            
        # Format the year (assuming 2-digit year format)
        if isinstance(expiry_year, int) and expiry_year > 2000:
            year = str(expiry_year)[2:]
        else:
            year = str(expiry_year)
            
        return f"{base_symbol.upper()}{year}{month_str}{date_part}FUT"
    
    @staticmethod
    def format_option(base_symbol, expiry_date, expiry_month, expiry_year, strike_price, option_type):
        """Format options symbol
        Example: NIFTY28MAR2420800CE
        """
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
            7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
        }
        
        # Handle month as string or int
        if isinstance(expiry_month, int):
            month_str = month_map[expiry_month]
        else:
            month_str = expiry_month.upper()
            
        # Format the year (assuming 2-digit year format)
        if isinstance(expiry_year, int) and expiry_year > 2000:
            year = str(expiry_year)[2:]
        else:
            year = str(expiry_year)
            
        # Format option type (call or put)
        opt_type = "CE" if option_type.upper() in ["C", "CALL", "CE"] else "PE"
        
        # Format strike price (remove decimal if it's a whole number)
        if isinstance(strike_price, (int, float)):
            if strike_price == int(strike_price):
                strike_str = str(int(strike_price))
            else:
                strike_str = str(strike_price)
        else:
            strike_str = strike_price
            
        return f"{base_symbol.upper()}{expiry_date}{month_str}{year}{strike_str}{opt_type}"
    
    @staticmethod
    def get_common_indices(exchange="NSE_INDEX"):
        """Get common index symbols"""
        if exchange.upper() == "NSE_INDEX":
            return ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYNXT50", "MIDCPNIFTY", "INDIAVIX"]
        elif exchange.upper() == "BSE_INDEX":
            return ["SENSEX", "BANKEX", "SENSEX50"]
        return []

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='OpenAlgo Trading Assistant')
    parser.add_argument('--host', help='MCP server host (default: uses MCP_HOST from .env)')
    parser.add_argument('--port', type=int, help='MCP server port (default: uses MCP_PORT from .env)')
    parser.add_argument('--model', help='LLM model to use (default: uses OPENAI_MODEL from .env)')
    args = parser.parse_args()

    # Get MCP host and port from args or environment variables
    mcp_host = args.host or os.environ.get("MCP_HOST", "localhost")
    mcp_port = args.port or int(os.environ.get("MCP_PORT", "8001"))
    mcp_url = f"http://{mcp_host}:{mcp_port}/sse"
    
    # Get model from args or environment
    model_name = args.model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    console.print(f"[info]Connecting to OpenAlgo MCP server at {mcp_url}...[/info]")
    
    mcp_client = MCPClient()
    # Add more detailed error handling during connection
    try:
        console.print(f"[info]Attempting connection to {mcp_url}...[/info]")
        await mcp_client.connect_to_sse_server(mcp_url)
        console.print(f"[success]Successfully connected to MCP server[/success]")
    except Exception as e:
        console.print(f"[danger]Error connecting to MCP server: {str(e)}[/danger]")
        console.print(f"[info]Make sure the server is running with 'python server/server.py'[/info]")
        return

    # List available tools with error handling
    try:
        console.print(f"[info]Retrieving available tools from server...[/info]")
        response = await mcp_client.session.list_tools()
        # ListToolsResult doesn't have a __len__ method, so we can't directly call len() on it
        console.print(f"[success]Successfully retrieved tools from server[/success]")
    except Exception as e:
        console.print(f"[danger]Error retrieving tools: {str(e)}[/danger]")
        return

    try:
        mcp_tools = MCPTools(session=mcp_client.session)
        await mcp_tools.initialize()
        console.print(f"[success]Successfully initialized MCP tools[/success]")
    except Exception as e:
        console.print(f"[danger]Error initializing MCP tools: {str(e)}[/danger]")
        return

    # Create the Agno agent with OpenAI model
    agent = Agent(
        instructions="""
You are an OpenAlgo Trading Assistant, helping users manage their trading accounts, orders, portfolio, and positions using OpenAlgo API tools provided over MCP.

# Important Instructions:
- ALWAYS respond in plain text. NEVER use markdown formatting (no asterisks, hashes, or code blocks).
- Respond in human-like conversational, friendly, and professional tone in concise manner.
- When market data is requested, always present it in a clean, easy-to-read format.
- For numerical values like prices and quantities, always display them with appropriate units.
- Help users construct proper symbol formats based on OpenAlgo's standardized conventions.

# Responsibilities:
- Assist with order placement, modification, and cancellation
- Provide insights on portfolio holdings, positions, and orders
- Track order status, market quotes, and market depth
- Help with getting historical data and symbol information
- Assist with retrieving funds and managing positions
- Guide users on correct OpenAlgo symbol formats for different instruments

# Available Tools:

## Order Management:
- place_order: Place a new order with support for market, limit, stop-loss orders
- modify_order: Modify an existing order's price, quantity, or other parameters
- cancel_order: Cancel a specific order by ID
- cancel_all_orders: Cancel all open orders
- get_order_status: Check the status of a specific order
- get_orders: List all orders

## Advanced Order Types:
- place_basket_order: Place multiple orders simultaneously
- place_split_order: Split a large order into smaller chunks to reduce market impact
- place_smart_order: Place an order that considers current position size

## Market Data:
- get_quote: Get current market quotes (bid, ask, last price) for a symbol
- get_depth: Get detailed market depth (order book) for a symbol
- get_history: Get historical price data for a symbol with various timeframes
- get_intervals: Get available time intervals for historical data

## Position & Portfolio Management:
- get_open_position: Get details of an open position for a specific symbol
- close_all_positions: Close all open positions across all symbols
- get_position_book: Get all current positions
- get_holdings: Get portfolio holdings information
- get_trade_book: Get record of all executed trades

## Account & Configuration:
- get_funds: Get available funds and margin information
- get_all_tickers: Get list of all available trading symbols
- get_symbol_metadata: Get detailed information about a trading symbol

# OpenAlgo Symbol Format Guidelines:

## Exchange Codes:
- NSE: National Stock Exchange equities
- BSE: Bombay Stock Exchange equities
- NFO: NSE Futures and Options
- BFO: BSE Futures and Options
- BCD: BSE Currency Derivatives
- CDS: NSE Currency Derivatives
- MCX: Multi Commodity Exchange
- NSE_INDEX: NSE indices
- BSE_INDEX: BSE indices

## Equity Symbol Format:
Simply use the base symbol, e.g., "INFY", "SBIN", "TATAMOTORS"

## Future Symbol Format:
[Base Symbol][Expiration Date]FUT
Examples:
- BANKNIFTY24APR24FUT (Bank Nifty futures expiring in April 2024)
- USDINR10MAY24FUT (USDINR currency futures expiring in May 2024)

## Options Symbol Format:
[Base Symbol][Expiration Date][Strike Price][Option Type]
Examples:
- NIFTY28MAR2420800CE (Nifty call option with 20,800 strike expiring March 28, 2024)
- VEDL25APR24292.5CE (Vedanta call option with 292.50 strike expiring April 25, 2024)

## Common Index Symbols:
- NSE_INDEX: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, INDIAVIX
- BSE_INDEX: SENSEX, BANKEX, SENSEX50

# Parameter Guidelines:
- symbol: Trading symbol following OpenAlgo format
- exchange: Exchange code (NSE, BSE, NFO, etc.)
- price_type: "MARKET", "LIMIT", "SL" (stop-loss), "SL-M" (stop-loss market)
- product: "MIS" (intraday), "CNC" (delivery), "NRML" (normal)
- action: "BUY" or "SELL"
- quantity: Number of shares/contracts to trade
- strategy: Usually "Python" (default)

# Limitations:
You are not a financial advisor and should not provide investment advice. Your role is to ensure secure, efficient, and compliant account management.
""",
        model=OpenAIChat(
            id=model_name
        ),
        add_history_to_messages=True,
        num_history_responses=10,
        tools=[mcp_tools],
        show_tool_calls=False,
        markdown=True,
        read_tool_call_history=True,
        read_chat_history=True,
        tool_call_limit=10,
        telemetry=False,
        add_datetime_to_instructions=True
    )

    # Welcome message
    console.print()
    console.print("[info]Welcome to OpenAlgo Trading Assistant! I'm here to help you manage your trading account, orders, portfolio, and positions. How can I help you today?[/info]", style="response")

    try:
        while True:
            # Add spacing before the prompt
            console.print()
            # Get user input with rich prompt
            user_query = Prompt.ask("[query]Enter your query:[/query] [dim](or 'quit' to exit)[/dim]")

            # Check if user wants to quit
            if user_query.lower() == 'quit':
                break

            # Add spacing before the prompt
            console.print()
            # Display user query
            console.print(f"[user]You:[/user] {user_query}")
            # Add spacing before the assistant's response
            console.print()
            console.print(f"[assistant]Assistant:[/assistant] ", end="")

            # Run the agent and stream the response
            result = await agent.arun(user_query, stream=True)
            async for response in result:
                if response.content:
                    console.print(response.content, style="response", end="")

            console.print()  # Add newline after the full response
            console.print()  # Add extra spacing after the response

    except Exception as e:
        console.print(f"[danger]An error occurred: {str(e)}[/danger]")
    finally:
        # Disconnect from the MCP server
        await mcp_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
