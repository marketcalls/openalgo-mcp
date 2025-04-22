<<<<<<< HEAD
# OpenAlgo MCP - AI Trading Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An AI-powered trading assistant platform for OpenAlgo, leveraging Machine Conversation Protocol (MCP) and Large Language Models to provide intelligent trading capabilities.

## Overview

OpenAlgo MCP integrates the powerful OpenAlgo trading platform with advanced AI capabilities through:
1. An MCP server that exposes OpenAlgo API functions as tools for AI interaction
2. An intelligent client application providing a conversational interface for trading

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

## Project Structure

```
mcpserver/
├── .env                 # Common environment configuration
├── .env.example         # Example configuration template
├── requirements.txt     # Common dependencies for both client and server
├── LICENSE              # MIT License
├── server/              # MCP Server implementation
│   ├── server.py        # OpenAlgo MCP server code
│   ├── requirements.txt # Server-specific dependencies
│   └── .env             # Server-specific configuration (optional)
└── client/              # Client implementation
    ├── trading_agent.py # AI assistant client code
    ├── requirements.txt # Client-specific dependencies
    └── .env             # Client-specific configuration (optional)
```

## Installation Guide

### Prerequisites

- Python 3.9+ installed
- OpenAlgo platform installed and configured
- OpenAI API key (for the client component)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/openalgo-mcp.git
cd openalgo-mcp/mcpserver
```

### Step 2: Set Up Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your API keys and settings
# vim .env or use any text editor
```

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

### Starting the Trading Assistant Client

```bash
cd client
python trading_agent.py
```

The client supports these options:
- `--host`: MCP server host (default: from .env)
- `--port`: MCP server port (default: from .env)
- `--model`: OpenAI model to use (default: from .env)

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenAlgo](https://openalgo.in/) for the powerful trading platform
- [MCP (Machine Conversation Protocol)](https://github.com/lalalune/mcp) for the communication framework
- [AGNO](https://github.com/AstroCorp/agno) for the AI agent infrastructure
=======
# openalgo-mcp
openalgo-mcp
>>>>>>> e499efe061ea80029530aab1eeb2f78b49a03c8c
