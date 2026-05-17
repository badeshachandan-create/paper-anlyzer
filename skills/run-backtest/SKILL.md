---
description: |
  Execute a backtest for a strategy specification. Accepts either a JSON strategy spec or
  a plain description and runs it against real historical data via the financial-data MCP server.
  Usage: /run-backtest <strategy JSON or description>
allowed-tools:
  - mcp__financial-data__get_price_history
  - mcp__financial-data__search_tickers
  - mcp__financial-data__get_asset_class_data
  - mcp__financial-data__run_backtest
  - mcp__filesystem__write_file
---

# Run Backtest

Execute a strategy backtest and return full performance metrics.

## Input
`$ARGUMENTS` — either a strategy JSON spec or a plain-language strategy description.

## Steps

1. **Parse input** — if JSON, extract fields directly. If plain description, infer:
   - Universe: use the most appropriate liquid ETF proxies
   - Signals: map description to signal types
   - Rebalancing: default monthly if not specified
   - Position sizing: default `signal_weight`

2. **Verify tickers** — use `mcp__financial-data__search_tickers` for any uncertain ticker. Spot-check data availability with `mcp__financial-data__get_price_history` on a 1-month range.

3. **Run the backtest** via `mcp__financial-data__run_backtest` with:
   - start_date: 10+ years back, targeting 2005-01-01 if possible
   - end_date: today
   - initial_capital: 100000
   - transaction_cost_bps: 10

   If specific tickers fail, replace with these proxies:
   | Asset | Primary | Fallback 1 | Fallback 2 |
   |---|---|---|---|
   | US large cap | SPY | IVV | VOO |
   | US small cap | IWM | VB | SCHA |
   | Bonds | AGG | BND | TLT |
   | Int'l developed | EFA | VEA | SPDW |
   | Emerging markets | EEM | VWO | IEMG |
   | Gold | GLD | IAU | GLDM |
   | Commodities | DJP | PDBC | GSG |
   | REITs | VNQ | IYR | SCHH |

4. **Return results** — present the metrics in a clean table. If the user provided an output path, save the full JSON via `mcp__filesystem__write_file`.

## Default Parameters (when not specified)
- Start: 2005-01-01
- End: today
- Capital: $100,000
- Transaction costs: 10 bps
- Benchmark: SPY
- Rebalancing: monthly
