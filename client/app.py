import os
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from mcp import ClientSession
from mcp.client.sse import sse_client
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from typing import Optional, Dict, List
from contextlib import AsyncExitStack
from pydantic import BaseModel
from dotenv import load_dotenv
import json
from fastapi.middleware.cors import CORSMiddleware

# Configure logging with a custom filter to reduce noise
class SilentFilter(logging.Filter):
    def filter(self, record):
        # Filter out specific noisy log messages
        silenced_messages = [
            "HTTP Request:",
            "HTTP Response:",
            "Connection pool is full",
            "Starting new HTTPS connection"
        ]
        return not any(msg in record.getMessage() for msg in silenced_messages)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the filter to reduce noise
for handler in logging.getLogger().handlers:
    handler.addFilter(SilentFilter())

# Find and load the .env file
parent_dir = Path(__file__).resolve().parent
env_path = parent_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    # Try parent directory
    parent_env = parent_dir.parent / ".env"
    if parent_env.exists():
        load_dotenv(dotenv_path=parent_env)
        logger.info(f"Loaded environment from {parent_env}")
    else:
        load_dotenv()
        logger.info("Loaded environment from default location")

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

# Set up templates and static files
templates = Jinja2Templates(directory=str(parent_dir / "templates"))
static_dir = parent_dir / "static"
os.makedirs(parent_dir / "templates", exist_ok=True)
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Configuration
MCP_HOST = os.environ.get("MCP_HOST", "localhost")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"

# LLM Provider settings
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

# Store active connections and resources
active_connections: Dict[str, WebSocket] = {}
mcp_clients: Dict[str, "MCPClient"] = {}
agents: Dict[str, Agent] = {}
chat_histories: Dict[str, "ChatHistory"] = {}

class SymbolHelper:
    """Helper class for OpenAlgo symbol format assistance"""
    
    @staticmethod
    def format_equity(symbol, exchange="NSE"):
        """Format equity symbol"""
        return symbol.upper()
    
    @staticmethod
    def format_future(base_symbol, expiry_year, expiry_month, expiry_date=None):
        """Format futures symbol - Example: BANKNIFTY24APR24FUT"""
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
            7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
        }
        
        if isinstance(expiry_month, int):
            month_str = month_map[expiry_month]
        else:
            month_str = expiry_month.upper()
            
        if expiry_date:
            date_part = f"{expiry_date}"
        else:
            date_part = ""
            
        if isinstance(expiry_year, int) and expiry_year > 2000:
            year = str(expiry_year)[2:]
        else:
            year = str(expiry_year)
            
        return f"{base_symbol.upper()}{year}{month_str}{date_part}FUT"
    
    @staticmethod
    def format_option(base_symbol, expiry_date, expiry_month, expiry_year, strike_price, option_type):
        """Format options symbol - Example: NIFTY28MAR2420800CE"""
        month_map = {
            1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
            7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
        }
        
        if isinstance(expiry_month, int):
            month_str = month_map[expiry_month]
        else:
            month_str = expiry_month.upper()
            
        if isinstance(expiry_year, int) and expiry_year > 2000:
            year = str(expiry_year)[2:]
        else:
            year = str(expiry_year)
            
        opt_type = "CE" if option_type.upper() in ["C", "CALL", "CE"] else "PE"
        
        if isinstance(strike_price, (int, float)):
            if strike_price == int(strike_price):
                strike_str = str(int(strike_price))
            else:
                strike_str = str(strike_price)
        else:
            strike_str = strike_price
            
        return f"{base_symbol.upper()}{expiry_date}{month_str}{year}{strike_str}{opt_type}"

class MCPClient:
    """Enhanced MCP Client with better error handling"""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None
        self._connected = False
        
    async def connect_to_sse_server(self, server_url: str) -> bool:
        """Connect to an MCP server running with SSE transport"""
        logger.info(f"Attempting to connect to MCP server at {server_url}")
        try:
            # Clean up any existing connections
            await self.cleanup()
            
            # Create new connection
            self._streams_context = sse_client(url=server_url)
            streams = await self._streams_context.__aenter__()
            logger.info("Successfully created SSE client streams")
            
            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()
            logger.info("Successfully created client session")
            
            # Initialize session
            await self.session.initialize()
            logger.info("Successfully initialized MCP session")
            
            # Verify connection by listing tools
            response = await self.session.list_tools()
            logger.info(f"Successfully connected - found {len(response.tools)} tools")
            self._connected = True
            return True
                
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {str(e)}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Properly clean up the session and streams"""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
            if self._streams_context:
                await self._streams_context.__aexit__(None, None, None)
                self._streams_context = None
            self.session = None
            self._connected = False
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def disconnect(self):
        """Disconnect from the MCP server"""
        await self.cleanup()

    @property
    def is_connected(self) -> bool:
        return self._connected and self.session is not None

class Message(BaseModel):
    role: str
    content: str

class ChatHistory(BaseModel):
    messages: List[Message] = []

async def get_mcp_client(client_id: str) -> MCPClient:
    """Get or create an MCP client for the connection"""
    if client_id not in mcp_clients:
        mcp_client = MCPClient()
        try:
            await mcp_client.connect_to_sse_server(MCP_URL)
            mcp_clients[client_id] = mcp_client
            
            # Initialize the agent
            mcp_tools = MCPTools(session=mcp_client.session)
            await mcp_tools.initialize()
            
            # Choose model based on provider
            if LLM_PROVIDER == "groq":
                model = Groq(id=GROQ_MODEL, timeout=60.0)
            else:
                model = OpenAIChat(id=OPENAI_MODEL)
            
            agent = Agent(
                instructions="""
You are an OpenAlgo Trading Assistant, helping users manage their trading accounts, orders, portfolio, and positions using OpenAlgo API tools provided over MCP.

# Responsibilities:
- Assist with order placement, modification, and cancellation
- Provide insights on portfolio holdings, positions, and orders
- Track order status, market quotes, and market depth
- Help with getting historical data and symbol information
- Assist with retrieving funds and managing positions
- Guide users on correct OpenAlgo symbol formats for different instruments

# OpenAlgo Symbol Format Guidelines:
## Exchange Codes:
- NSE: National Stock Exchange equities
- BSE: Bombay Stock Exchange equities
- NFO: NSE Futures and Options
- BFO: BSE Futures and Options

## Equity Symbol Format:
Simply use the base symbol, e.g., "INFY", "SBIN", "TATAMOTORS"

## Future Symbol Format:
[Base Symbol][Expiration Date]FUT
Examples: BANKNIFTY24APR24FUT, USDINR10MAY24FUT

## Options Symbol Format:
[Base Symbol][Expiration Date][Strike Price][Option Type]
Examples: NIFTY28MAR2420800CE, VEDL25APR24292.5CE

# Parameter Guidelines:
- symbol: Trading symbol following OpenAlgo format
- exchange: Exchange code (NSE, BSE, NFO, etc.)
- price_type: "MARKET", "LIMIT", "SL" (stop-loss), "SL-M" (stop-loss market)
- product: "MIS" (intraday), "CNC" (delivery), "NRML" (normal)
- action: "BUY" or "SELL"
- quantity: Number of shares/contracts to trade
- strategy: Usually "Python" (default)

# Updated Agent Instructions with Better Formatting
# Add this to your client/app.py when creating the agent

# Important Instructions:
- Respond in human-like conversational, friendly, and professional tone in concise manner.
- ALWAYS format responses in clean, readable markdown format
- Use tables for structured data like portfolio, funds, orders, and quotes
- Present numerical values with proper formatting and currency symbols
- Use clear headings and sections to organize information
- Make responses visually appealing and easy to scan

# Response Formatting Guidelines:

## For Funds Information:
Format funds data as a clean table with proper alignment:

```markdown
## 💰 Account Funds Summary

| **Category** | **Amount (₹)** |
|--------------|----------------|
| Available Cash | 808.18 |
| Collateral | 0.00 |
| M2M Realized | -24.60 |
| M2M Unrealized | 0.00 |
| Utilized Debits | 115.22 |

**Key Insights:**
- ✅ Available for trading: **₹808.18**
- 📊 Total utilized: **₹115.22**
- 📈 Realized P&L: **₹-24.60**
```

## For Portfolio/Holdings:
Present holdings in a structured table format:

```markdown
## 📈 Portfolio Holdings

| **Symbol** | **Exchange** | **Qty** | **Product** | **P&L (₹)** | **P&L %** |
|------------|--------------|---------|-------------|-------------|-----------|
| TATASTEEL | NSE | 1 | CNC | 14.00 | 9.79% |
| CANBANK | NSE | 5 | CNC | 39.00 | 7.61% |

### Portfolio Summary:
- **Total Holding Value:** ₹715.00
- **Total Investment:** ₹662.00
- **Total P&L:** ₹53.61 **(8.09%)**
- **Number of Holdings:** 2
```

## For Market Quotes:
Format quotes with clear price information:

```markdown
## 📊 NIFTY Market Quote

### Current Price Information:
- **Last Traded Price (LTP):** ₹24,752.45
- **Previous Close:** ₹24,826.20
- **Change:** -₹73.75 **(-0.30%)**

### Market Status:
- 🔴 **Currently Closed** - No live updates for open, high, low, ask, bid, or volume
- ⏰ **Next Session:** Regular trading hours

*For detailed market depth and live data, please check during market hours.*
```

## For Orders:
Present order information in tables:

```markdown
## 📋 Order Book

| **Order ID** | **Symbol** | **Action** | **Qty** | **Price** | **Status** | **Time** |
|--------------|------------|------------|---------|-----------|------------|----------|
| 12345 | RELIANCE | BUY | 10 | 2,450.00 | COMPLETE | 09:30 AM |
| 12346 | TCS | SELL | 5 | 3,890.00 | PENDING | 10:15 AM |

### Order Summary:
- **Total Orders:** 2
- **Completed:** 1
- **Pending:** 1
```

## General Formatting Rules:
1. Use emoji icons (💰📈📊📋) to make sections visually appealing
2. Bold important numbers and percentages
3. Use proper currency symbols (₹ for INR)
4. Color-code positive/negative values contextually
5. Include summary sections with key insights
6. Use consistent table formatting with clear headers
7. Add explanatory text when data might be confusing

## For Empty or Error Responses:
When API returns no data or errors:

```markdown
## ⚠️ Information Not Available

The requested data is currently unavailable. This could be due to:
- Market is closed
- No positions/orders exist
- API connectivity issues

Please try again during market hours or contact support if the issue persists.

# Limitations:
You are not a financial advisor and should not provide investment advice. Your role is to ensure secure, efficient, and compliant account management.
""",
                model=model,
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
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                user_query = message.get("content", "").strip()
                
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
                full_response = ""
                has_streamed_content = False
                
                # Run the agent and stream the response
                try:
                    result = await agent.arun(user_query, stream=True)
                    
                    # Check if we get streaming responses
                    async for response in result:
                        if response.content:
                            has_streamed_content = True
                            full_response += response.content
                            # Send partial response
                            await websocket.send_json({
                                "role": "assistant",
                                "content": response.content,
                                "partial": True
                            })
                    
                    # Only send complete response if we didn't get any streaming content
                    if not has_streamed_content and full_response:
                        await websocket.send_json({
                            "role": "assistant",
                            "content": full_response,
                            "partial": False
                        })
                    elif has_streamed_content:
                        # Send a signal that streaming is complete (frontend will ignore this)
                        await websocket.send_json({
                            "role": "assistant",
                            "content": "",
                            "partial": False,
                            "streaming_complete": True
                        })
                    
                except Exception as agent_error:
                    logger.error(f"Agent error: {str(agent_error)}")
                    full_response = f"I encountered an error while processing your request: {str(agent_error)}"
                    # Send error as complete message (not streaming)
                    await websocket.send_json({
                        "role": "assistant",
                        "content": full_response,
                        "partial": False
                    })
                
                # Add assistant message to chat history (use full response)
                if full_response:
                    chat_histories[client_id].messages.append(Message(role="assistant", content=full_response))
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from client {client_id}")
                await websocket.send_json({
                    "role": "system",
                    "content": "Error: Invalid message format."
                })
            except Exception as e:
                logger.error(f"Error processing message from {client_id}: {str(e)}")
                await websocket.send_json({
                    "role": "system",
                    "content": f"Error: {str(e)}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
    finally:
        # Clean up resources
        active_connections.pop(client_id, None)
        
        if client_id in mcp_clients:
            try:
                await mcp_clients[client_id].disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting MCP client: {str(e)}")
            mcp_clients.pop(client_id, None)
        
        if client_id in agents:
            agents.pop(client_id, None)
        
        if client_id in chat_histories:
            chat_histories.pop(client_id, None)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down - cleaning up resources")
    for client_id, mcp_client in list(mcp_clients.items()):
        try:
            await mcp_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client {client_id}: {str(e)}")

if __name__ == "__main__":
    logger.info(f"Starting OpenAlgo Trading Assistant on port 8000")
    logger.info(f"MCP Server URL: {MCP_URL}")
    logger.info(f"LLM Provider: {LLM_PROVIDER}")
    
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )