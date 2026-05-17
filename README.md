# Stock Paper Analyzer

A Claude Code plugin that reads academic finance papers, extracts tradeable strategies, and backtests them against real historical market data.

## What It Does

1. **Reads papers** — paste text, provide URLs, or point to local files
2. **Extracts signals** — maps paper methodology to momentum, value, trend, volatility, and other factor signals
3. **Synthesizes strategies** — combines multiple papers with your custom prompt
4. **Backtests with real data** — fetches actual historical prices and runs a full simulation
5. **Reports results** — CAGR, Sharpe ratio, max drawdown, alpha/beta vs benchmark, regime analysis

## Quick Start

```bash
# 1. Install dependencies
bash setup.sh

# 2. Load the plugin
claude --plugin-dir /path/to/stock-paper-analyzer

# 3. Analyze a paper
/analyze "Test the 12-month momentum strategy from Jegadeesh & Titman against the S&P 500 sectors"
# Then paste the paper text or provide a URL
```

## Skills

| Skill | Command | Description |
|---|---|---|
| **analyze** | `/analyze "prompt"` | Full pipeline: papers → strategy → backtest → report |
| **extract-strategy** | `/extract-strategy <URL or text>` | Parse one paper into a strategy spec JSON |
| **run-backtest** | `/run-backtest <strategy JSON>` | Run a backtest for a given strategy |
| **generate-report** | `/generate-report` | Format a polished report from prior backtest results |

## Data Sources

The plugin uses a **3-source fallback chain** for every data type:

| Data Type | Source 1 | Source 2 | Source 3 |
|---|---|---|---|
| Stock/ETF prices | Yahoo Finance | Stooq | Alpha Vantage |
| Macro indicators | FRED (Fed Reserve) | World Bank | OECD |
| Stock fundamentals | Yahoo Finance | Financial Modeling Prep | SEC EDGAR |

All sources work without API keys. Optional free API keys extend rate limits and coverage.

## Supported Strategy Types

| Signal | Academic Examples |
|---|---|
| `momentum` | Jegadeesh & Titman (1993), AQR momentum papers |
| `mean_reversion` | De Bondt & Thaler (1985) |
| `trend_following` | AQR time-series momentum, trend-following literature |
| `value` | Fama-French HML, Asness value papers |
| `low_volatility` | Ang et al., Frazzini & Pedersen BAB |
| `carry` | AQR carry papers (Koijen et al.) |
| `quality` | Asness et al. QMJ factor |
| `size` | Fama-French SMB |

## Supported Position Sizing

- `equal_weight` — allocate equally across universe
- `signal_weight` — weight proportional to signal strength
- `risk_parity` — inverse volatility weighting
- `momentum` — top-tercile selection by signal rank
- `min_variance` — minimum variance optimization

## Environment Variables (all optional)

```bash
export FRED_API_KEY=...          # fred.stlouisfed.org — free, highly recommended
export ALPHA_VANTAGE_KEY=...     # alphavantage.co — free tier
export FMP_API_KEY=...           # financialmodelingprep.com — free tier
```

## Architecture

```
stock-paper-analyzer/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── .mcp.json                    # MCP server configuration
├── skills/
│   ├── analyze/SKILL.md         # Main entry point
│   ├── extract-strategy/SKILL.md
│   ├── run-backtest/SKILL.md
│   └── generate-report/SKILL.md
├── mcp/
│   └── financial-data/
│       ├── server.py            # FastMCP server (6 tools)
│       ├── data_fetcher.py      # Multi-source data layer
│       ├── backtest_engine.py   # Simulation + analytics engine
│       └── requirements.txt
└── setup.sh
```

The MCP server provides raw data tools. The skills teach Claude how to orchestrate those tools end-to-end for any academic paper.

## Extending to an App

Because all data access goes through the MCP server's clean tool interface, you can:
- Call `run_backtest` directly from any MCP-compatible client
- Wrap the Python files as a REST API with minimal changes
- Add new data sources by extending `DataFetcher` with new fallback methods
- Add new signal types to `BacktestEngine._compute_signals` with one new `elif` block
