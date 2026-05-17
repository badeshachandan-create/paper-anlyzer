#!/usr/bin/env bash
# Setup script for Stock Paper Analyzer plugin
set -e

echo "=== Stock Paper Analyzer — Setup ==="
echo ""

# Python deps
echo "[1/2] Installing Python dependencies..."
pip install -r mcp/financial-data/requirements.txt --quiet
echo "      Done."

# Create output directory
mkdir -p ~/stock-analyzer-results
echo "[2/2] Created output directory: ~/stock-analyzer-results"

echo ""
echo "=== Optional: free API keys for broader data coverage ==="
echo ""
echo "  FRED (Federal Reserve data — highly recommended, free):"  
echo "    Register at: https://fred.stlouisfed.org/docs/api/api_key.html"
echo "    export FRED_API_KEY=your_key_here"
echo ""
echo "  Alpha Vantage (backup stock data, free tier):"  
echo "    Register at: https://www.alphavantage.co/support/#api-key"
echo "    export ALPHA_VANTAGE_KEY=your_key_here"
echo ""
echo "  Financial Modeling Prep (backup fundamentals, free tier):"  
echo "    Register at: https://financialmodelingprep.com/developer/docs"
echo "    export FMP_API_KEY=your_key_here"
echo ""
echo "Note: The plugin works without any API keys using Yahoo Finance,"
echo "      Stooq, World Bank, OECD, and SEC EDGAR as free sources."
echo ""
echo "=== Ready. Load the plugin with: ==="
echo "  claude --plugin-dir <path-to-this-directory>"
echo ""
echo "Then run: /analyze \"your prompt\" and paste a paper or provide its URL."
