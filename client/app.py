import os
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from mcp import ClientSession
from mcp.client.sse import sse_client
from agno.models.openai import OpenAIChat
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from typing import Optional, Dict, List
from contextlib import AsyncExitStack
from pydantic import BaseModel
from dotenv import load_dotenv
import json
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Find and load the .env file
parent_dir = Path(__file__).resolve().parent
env_path = parent_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    load_dotenv()
    logger.info("Loaded environment from local .env file")

# Create FastAPI app
app = FastAPI(title="OpenAlgo Trading Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify the domains you want to allow
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates
templates = Jinja2Templates(directory=str(parent_dir / "templates"))
os.makedirs(parent_dir / "templates", exist_ok=True)

# Set up static files
static_dir = parent_dir / "static"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# MCP Connection settings
MCP_HOST = os.environ.get("MCP_HOST", "localhost")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

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

class MCPClient:
    def __init__(self):
        """Initialize session and client objects"""
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._streams_context = None
        self._session_context = None
        
    async def connect_to_sse_server(self, server_url: str):
        """Connect to an MCP server running with SSE transport"""
        logger.info(f"Attempting to connect to MCP server at {server_url}")
        try:
            # Store the context managers so they stay alive
            self._streams_context = sse_client(url=server_url)
            streams = await self._streams_context.__aenter__()
            logger.info("Successfully created SSE client streams")
            
            self._session_context = ClientSession(*streams)
            self.session: ClientSession = await self._session_context.__aenter__()
            logger.info("Successfully created client session")
            
            # Initialize with detailed error handling
            try:
                await self.session.initialize()
                logger.info("Successfully initialized MCP session")
            except Exception as e:
                logger.error(f"Error during session initialization: {str(e)}")
                raise
                
            # Try to verify connection by listing tools
            try:
                response = await self.session.list_tools()
                logger.info(f"Successfully connected and retrieved tools from server")
                return True
            except Exception as e:
                logger.error(f"Error listing tools: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {str(e)}")
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

# Store MCP clients for each connection
mcp_clients: Dict[str, MCPClient] = {}
agents: Dict[str, Agent] = {}

class Message(BaseModel):
    role: str
    content: str

class ChatHistory(BaseModel):
    messages: List[Message] = []

# Initialize chat histories
chat_histories: Dict[str, ChatHistory] = {}

async def get_mcp_client(client_id: str):
    """Get or create an MCP client for the connection"""
    if client_id not in mcp_clients:
        mcp_client = MCPClient()
        try:
            await mcp_client.connect_to_sse_server(MCP_URL)
            mcp_clients[client_id] = mcp_client
            
            # Initialize the agent
            mcp_tools = MCPTools(session=mcp_client.session)
            await mcp_tools.initialize()
            
            agent = Agent(
                instructions="""
You are an OpenAlgo Trading Assistant, helping users manage their trading accounts, orders, portfolio, and positions using OpenAlgo API tools provided over MCP.

# Important Instructions:
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
                    id=MODEL_NAME
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
            
            agents[client_id] = agent
            
            # Initialize chat history
            chat_histories[client_id] = ChatHistory()
            
        except Exception as e:
            logger.error(f"Error setting up MCP client: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to MCP server: {str(e)}")
    
    return mcp_clients[client_id]

@app.get("/", response_class=HTMLResponse)
async def get_homepage(request: Request):
    """Serve the main chat interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "mcp_server": MCP_URL}

@app.get("/api/status")
async def get_status():
    """Get MCP server connection status"""
    try:
        # Create a temporary client to check connection
        temp_client = MCPClient()
        connected = False
        try:
            connected = await temp_client.connect_to_sse_server(MCP_URL)
        finally:
            await temp_client.disconnect()
        
        return {
            "status": "connected" if connected else "disconnected",
            "mcp_server": MCP_URL
        }
    except Exception as e:
        logger.error(f"Error checking MCP server status: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "mcp_server": MCP_URL
        }

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for chat communication"""
    await websocket.accept()
    active_connections[client_id] = websocket
    
    try:
        # Send a welcome message
        await websocket.send_json({
            "role": "assistant",
            "content": "Welcome to OpenAlgo Trading Assistant! I'm here to help you manage your trading account, orders, portfolio, and positions. How can I help you today?"
        })
        
        # Get or create MCP client
        mcp_client = await get_mcp_client(client_id)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                user_query = message.get("content", "")
                
                if not user_query:
                    continue
                
                # Add user message to chat history
                chat_histories[client_id].messages.append(Message(role="user", content=user_query))
                
                # Send processing message
                await websocket.send_json({
                    "role": "system",
                    "content": "Processing your request..."
                })
                
                # Get agent response
                agent = agents[client_id]
                response_text = ""
                
                # Run the agent and stream the response
                result = await agent.arun(user_query, stream=True)
                async for response in result:
                    if response.content:
                        # Append to the full response
                        response_text += response.content
                        # Send partial response
                        await websocket.send_json({
                            "role": "assistant",
                            "content": response.content,
                            "partial": True
                        })
                
                # Send complete response
                await websocket.send_json({
                    "role": "assistant",
                    "content": response_text,
                    "partial": False
                })
                
                # Add assistant message to chat history
                chat_histories[client_id].messages.append(Message(role="assistant", content=response_text))
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                await websocket.send_json({
                    "role": "system",
                    "content": "Error: Invalid message format."
                })
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    "role": "system",
                    "content": f"Error: {str(e)}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        active_connections.pop(client_id, None)
        
        # Clean up resources
        if client_id in mcp_clients:
            await mcp_clients[client_id].disconnect()
            mcp_clients.pop(client_id, None)
        
        if client_id in agents:
            agents.pop(client_id, None)
        
        if client_id in chat_histories:
            chat_histories.pop(client_id, None)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    for client_id, mcp_client in mcp_clients.items():
        await mcp_client.disconnect()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
