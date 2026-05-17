---
description: |
  Format raw backtest results into a polished, readable performance report.
  Can be called standalone with prior backtest results, or invoked at the end of /analyze.
  Usage: /generate-report <backtest results JSON or reference to prior backtest>
allowed-tools:
  - mcp__filesystem__write_file
  - mcp__filesystem__read_file
---

# Generate Backtest Report

Format raw backtest results into a comprehensive, human-readable report.

## Input
`$ARGUMENTS` — backtest results JSON, a file path to results, or a reference to the most recent backtest in this conversation.

## Report Format

### SECTION 1 — Executive Summary

```
╔══════════════════════════════════════════════════════════════╗
║  STOCK PAPER ANALYZER — BACKTEST REPORT                     ║
║  Strategy: [name]                                            ║
║  Period:   [start] → [end]    Benchmark: [ticker]            ║
╚══════════════════════════════════════════════════════════════╝

VERDICT: ✅ Confirmed  /  ⚠️ Partial  /  ❌ Not Supported

[1-2 sentences: did the backtest validate the paper's claims?]
```

### SECTION 2 — Paper → Signal Mapping

Table showing which signals came from which papers, with the paper's claim vs what was implemented.

### SECTION 3 — Performance Dashboard

```
┌──────────────────────────────────┬──────────────┬───────────────┐
│ Metric                           │   Strategy   │  Benchmark    │
├──────────────────────────────────┼──────────────┼───────────────┤
│ Total Return                     │              │               │
│ CAGR                             │              │               │
│ Annualized Volatility            │              │               │
│ Sharpe Ratio                     │              │               │
│ Sortino Ratio                    │              │               │
│ Calmar Ratio                     │              │               │
│ Max Drawdown                     │              │               │
│ 95% Daily VaR                    │              │      —        │
│ Alpha (annualized)               │              │      —        │
│ Beta                             │              │      —        │
│ Information Ratio                │              │      —        │
│ Win Rate vs Benchmark            │              │      —        │
├──────────────────────────────────┼──────────────┼───────────────┤
│ Best Month                       │              │               │
│ Worst Month                      │              │               │
│ % Positive Months                │              │               │
│ Avg Monthly Return               │              │               │
└──────────────────────────────────┴──────────────┴───────────────┘
```

### SECTION 4 — Paper's Claimed vs Actual Performance

Table comparing what the paper claimed vs what the backtest produced. Note differences in sample period, universe, and methodology that explain gaps.

### SECTION 5 — Drawdown Analysis

List the 3-5 worst drawdown periods with:
- Start/end dates
- Maximum depth
- Context (e.g., "2008-2009 Financial Crisis", "2020 COVID crash")

### SECTION 6 — Regime Analysis

Break down returns qualitatively (use the monthly returns data) across:
- **Bull market periods** (extended S&P 500 rallies)
- **Bear market periods** (2008-2009, 2020, 2022)
- **High inflation regime** (2021-2023)
- **Low rate environment** (2010-2021)
- **Rising rate environment** (2022+)

### SECTION 7 — Caveats & Limitations

Always address:
- **ETF proxy risk**: if ETF proxies were used instead of individual stocks, how does this affect interpretation
- **Survivorship bias**: ETFs and indices are rebalanced; paper may have used point-in-time data
- **Look-ahead bias**: confirm signals only used past data
- **Transaction costs**: actual costs may vary; 10 bps assumption
- **Liquidity**: strategies with frequent rebalancing may face higher real-world costs
- **Sample period**: if backtest covers a different period than the paper, note which results are in-sample vs out-of-sample

### SECTION 8 — Actionable Verdict

- Clear recommendation: does the evidence support implementing this strategy?
- Top 2-3 modifications that could improve risk-adjusted returns based on the results
- Suggested next steps (alternative papers to combine, parameters to test)

---

If the user provides an output file path, save the complete report as markdown via `mcp__filesystem__write_file`.
