---
description: |
  Extract a structured, machine-readable strategy specification from a single academic finance paper.
  Useful standalone when you want to inspect what a paper implies before running a full backtest.
  Usage: /extract-strategy <paper URL or paste text after the command>
allowed-tools:
  - mcp__fetch__fetch
  - mcp__filesystem__read_file
---

# Extract Strategy From Paper

Given one academic paper, extract a complete, implementable strategy specification.

## Input
`$ARGUMENTS` — a URL, file path, or pasted paper content following the skill invocation.

## Steps

1. **Retrieve the paper** — if URL call `mcp__fetch__fetch`; if path call `mcp__filesystem__read_file`; if pasted, use as-is

2. **Read deeply** — identify:
   - Title, authors, publication year, journal
   - Core hypothesis and empirical claim
   - Universe (which stocks, asset classes, geographies)
   - Signal construction (formula, parameters, lookback)
   - Portfolio formation (how signals map to positions)
   - Rebalancing frequency and transaction cost assumptions
   - Risk management rules (if any)
   - Reported performance statistics

3. **Map signal type** — categorize the primary signal as one of:
   `momentum`, `mean_reversion`, `trend_following`, `value`, `low_volatility`, `carry`, `quality`, `size`

4. **Output structured JSON** in this exact format:

```json
{
  "paper": {
    "title": "...",
    "authors": "...",
    "year": "...",
    "core_thesis": "..."
  },
  "strategy": {
    "name": "...",
    "universe": ["SPY", "..."],
    "signals": [
      {
        "type": "momentum",
        "lookback_days": 252,
        "weight": 1.0,
        "description": "12-month return skipping last month"
      }
    ],
    "rebalance_frequency": "monthly",
    "position_sizing": "signal_weight",
    "benchmark": "SPY"
  },
  "claimed_performance": {
    "cagr": "...",
    "sharpe_ratio": "...",
    "max_drawdown": "...",
    "sample_period": "YYYY to YYYY",
    "universe_size": "..."
  },
  "assumptions_made": ["..."],
  "data_requirements": ["..."]
}
```

5. After the JSON, provide a 2-3 sentence plain-English summary of what the strategy does and whether it is straightforward or complex to replicate.
