# OpenAlgo MCP - AI Trading Assistant

An AI-powered trading assistant platform for OpenAlgo, leveraging Machine Conversation Protocol (MCP) and Large Language Models to provide intelligent trading capabilities through a modern web interface.

## Overview

OpenAlgo MCP integrates the powerful OpenAlgo trading platform with advanced AI capabilities through:
1. An MCP server that exposes OpenAlgo API functions as tools for AI interaction
2. A web-based client application providing a conversational interface for trading
3. Modern UI with real-time updates via WebSockets

This bridge between OpenAlgo's trading capabilities and AI allows for a natural language interface to complex trading operations, making algorithmic trading more accessible to users of all technical backgrounds.

## Key Features

### Comprehensive Trading Capabilities

- **Order Management**: Place, modify, and cancel orders with support for various order types (market, limit, stop-loss)
- **Advanced Order Types**: Basket orders, split orders, and smart orders with position sizing
- **Market Data Access**: Real-time quotes, market depth, and historical data
- **Portfolio Management**: Track holdings, positions, order books, and trade history
- **Account Information**: Monitor funds, margins, and trading limits

### Intelligent Symbol Format Handling

- Smart parsing and formatting of instrument symbols across exchanges
- Support for equity, futures, and options symbology
- Built-in knowledge of common indices and exchange-specific formats

### AI-Powered Trading Assistant

- Natural language interface for all trading operations
- Contextual understanding of trading terminology and concepts
- Guided assistance for complex trading operations
- Real-time data presentation in human-readable formats

### Modern Web Interface

- Responsive design with light/dark mode support
- Real-time WebSocket communication
- Markdown rendering for better readability
- Quick action buttons for common operations
- Connection status monitoring

## Project Structure

```
openalgo-mcp/
├── .env                 # Environment configuration
├── .env.example         # Example configuration template
├── requirements.txt     # Project dependencies
├── LICENSE              # MIT License
├── server/              # MCP Server implementation
│   └── server.py        # FastMCP server exposing OpenAlgo API
└── client/              # Web Client implementation
    ├── app.py           # FastAPI web application
    ├── templates/       # HTML templates
    │   └── index.html   # Main UI template
    └── static/          # Static assets
        ├── script.js    # Client-side JavaScript
        └── style.css    # CSS styles
```

## Installation Guide

### Prerequisites

- Python 3.9+ installed
- OpenAlgo platform installed and configured
- OpenAI API key (for the client component)

### Step 1: Clone the Repository

```bash
git clone https://github.com/marketcalls/openalgo-mcp.git
cd openalgo-mcp
```

### Step 2: Set Up Environment

```bash
# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your API keys and settings
# Use your preferred text editor
```

Required environment variables:
- `OPENALGO_API_KEY`: Your OpenAlgo API key
- `OPENALGO_API_HOST`: OpenAlgo API host (default: http://127.0.0.1:5000)
- `OPENAI_API_KEY`: OpenAI API key for the AI assistant
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4o)

## Usage

### Starting the MCP Server

```bash
cd server
python server.py
```

The server supports the following options:
- `--api-key`: OpenAlgo API key (alternative to setting in .env)
- `--host`: OpenAlgo API host URL (default: http://127.0.0.1:5000)
- `--port`: Server port (default: 8001)
- `--mode`: Server transport mode - 'stdio' or 'sse' (default: sse)

### Starting the Web UI Client

```bash
cd client
python app.py
```

This will start the web interface on http://localhost:8000 by default.

You can then access the trading assistant through your web browser.

The client application will automatically connect to the MCP server as configured in the .env file.

## Configuration

The project uses a unified configuration approach with environment variables:

1. Common configuration is stored in the root `.env` file
2. Component-specific configuration can be set in `server/.env` or `client/.env`
3. Common settings will be loaded first, then possibly overridden by component-specific settings

### Required API Keys

1. **OpenAlgo API Key** - Set in `.env` as `OPENALGO_API_KEY`
   - Required for accessing the OpenAlgo trading platform
   - Obtain from your OpenAlgo account dashboard

2. **OpenAI API Key** - Set in `.env` as `OPENAI_API_KEY` (for the client only)
   - Required for the AI assistant capabilities
   - Obtain from [OpenAI Platform](https://platform.openai.com/)

## Technical Capabilities

The OpenAlgo MCP implementation provides comprehensive API coverage including:

1. **Order Management**:
   - `place_order`: Standard order placement
   - `modify_order`: Order modification with parameter validation
   - `cancel_order`: Order cancellation by ID

2. **Advanced Order Types**:
   - `place_basket_order`: Place multiple orders simultaneously
   - `place_split_order`: Split large orders into smaller chunks
   - `place_smart_order`: Position-aware order placement

3. **Market Data**:
   - `get_quote`: Latest market quotes
   - `get_depth`: Order book depth data
   - `get_history`: Historical price data with various timeframes

4. **Account Information**:
   - `get_funds`: Available funds and margin
   - `get_holdings`: Portfolio holdings
   - `get_position_book`, `get_order_book`, `get_trade_book`: Trading records

5. **Symbol Information**:
   - `get_symbol_metadata`: Detailed symbol information
   - `get_all_tickers`: Available trading symbols
   - `get_intervals`: Supported timeframes for historical data

The implementation uses FastMCP with SSE (Server-Sent Events) transport for real-time communication and includes proper error handling, logging, and parameter validation.

## Technical Implementation

### Server Implementation

The OpenAlgo MCP Server is built using the FastMCP library and exposes OpenAlgo trading functionality through a comprehensive set of tools. It uses Server-Sent Events (SSE) as the primary transport mechanism for real-time communication.

#### Server Architecture

- **Framework**: Uses FastMCP with Starlette for the web server
- **Transport**: Server-Sent Events (SSE) for real-time bidirectional communication
- **API Client**: Wraps the OpenAlgo API with appropriate error handling and logging
- **Configuration**: Uses environment variables with command-line override capabilities
- **Health Endpoint**: Supports /health endpoint for client health checks

#### Available API Tools

The server exposes over 15 trading-related tools, including:

- **Order Management**: place_order, modify_order, cancel_order, get_order_status
- **Advanced Orders**: place_basket_order, place_split_order, place_smart_order
- **Market Data**: get_quote, get_depth, get_history, get_intervals
- **Account Information**: get_funds, get_holdings, get_position_book, get_order_book, get_trade_book
- **Symbol Information**: get_symbol_metadata, get_all_tickers

### Web Client Implementation

The Trading Assistant web client provides a user-friendly interface to interact with the OpenAlgo platform through natural language. It uses OpenAI's language models to interpret user commands and invoke the appropriate trading functions.

#### Client Architecture

- **Framework**: FastAPI web server with WebSocket support
- **MCP Client**: Uses MCP's SSE client for communicating with the server
- **LLM Integration**: Uses the Agno agent framework with OpenAI Chat models
- **UI**: Modern web interface built with HTML, CSS, and JavaScript
- **Symbol Helper**: Built-in utilities for correct symbol formatting across exchanges
- **Error Handling**: Comprehensive exception handling with user-friendly feedback

#### Web UI Features

- **Real-time Chat**: WebSocket-based real-time communication
- **Theme Support**: Light and dark mode themes
- **Quick Actions**: Pre-defined buttons for common operations
- **Markdown Rendering**: Format AI responses with proper markdown styling
- **Connection Status**: Visual indicators for server connection state
- **Responsive Design**: Works on desktop and mobile devices
- **Auto-scrolling**: Messages automatically scroll into view
- **Message History**: Maintains conversation context for better interactions

## Troubleshooting Guide

### Common Issues

#### Connection Issues

If you're having trouble connecting to the MCP server:

1. **Verify the server is running**:
   ```bash
   cd server
   python server.py
   ```
   You should see output indicating the server is running on the configured port.

2. **Check environment variables**:
   - Ensure `MCP_HOST` and `MCP_PORT` in `.env` match the server's configuration
   - Verify that `SERVER_PORT` is the same as `MCP_PORT`

3. **Test local connectivity**:
   - Try accessing `http://localhost:8001/sse` in your browser (replace 8001 with your configured port)
   - You should see a message indicating the endpoint is for SSE connections

#### API Authentication Issues

If you see 403 Forbidden or authentication errors:

1. **Check your API key**:
   - Verify your OpenAlgo API key in the `.env` file is correct and active
   - Ensure the API key has the necessary permissions for the operations you're trying to perform

2. **Verify API host**:
   - Make sure `OPENALGO_API_HOST` points to the correct endpoint
   - For testing, the default value `http://127.0.0.1:5000` should work if you're running OpenAlgo locally

#### Client Issues

1. **Silent failures in the client**:
   - The client uses a SilentFilter for logging to provide a clean interface
   - If you suspect issues, temporarily modify the logging configuration in `trading_agent.py`
   - Check that the OpenAI API key is valid if you experience model generation failures

## Acknowledgements and Credits

This project is made possible by the following open-source projects and tools:

### Core Technologies

- **[OpenAlgo](https://github.com/marketcalls/openalgo)**: The powerful trading platform that powers all trading operations in this project

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)**: The communication protocol that enables AI agents to use tools and APIs

- **[Agno](https://github.com/agno-agi/agno)**: The agent framework used for building the trading assistant client

### Inspiration

This project was inspired by [Zerodha MCP](https://github.com/mtwn105/zerodha-mcp), which pioneered the use of Machine Conversation Protocol for trading applications. The OpenAlgo MCP project adapts and extends this concept for the OpenAlgo trading platform, with a focus on enhanced symbol handling, comprehensive trading operations, and a more user-friendly interface.

#### Symbol Formatting Issues

If your symbol-related requests are failing:

1. **Follow format guidelines**:
   - Equity symbols: Simple uppercase symbol (e.g., `INFY`, `SBIN`)
   - Futures: `[BaseSymbol][Year][Month][Date]FUT` (e.g., `BANKNIFTY24APR24FUT`)
   - Options: `[BaseSymbol][Date][Month][Year][Strike][OptionType]` (e.g., `NIFTY28MAR2420800CE`)

2. **Use the SymbolHelper class**:
   - The client includes formatting assistance methods that can help construct proper symbols

### Debugging Mode

For more detailed logging, enable debugging in the `.env` file:

```
SERVER_DEBUG=true
```

This will output additional information to help diagnose connection and API issues.

## License

This project is licensed under the Apache-2.0 license - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- This project was inspired by [Zerodha MCP]([https://github.com/zerodha/zerodha-mcp](https://github.com/mtwn105/zerodha-mcp)), which is licensed under the Apache License 2.0. While no code has been directly copied, this project builds upon the concept and architecture introduced by Zerodha MCP.
- [OpenAlgo](https://openalgo.in/) for the powerful trading platform
- [MCP (Machine Conversation Protocol)](https://github.com/lalalune/mcp) for the communication framework
- [AGNO](https://github.com/AstroCorp/agno) for the AI agent infrastructure

