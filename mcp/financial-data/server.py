"""Financial Data MCP Server for Stock Paper Analyzer.

Exposes six tools to Claude:
  get_price_history      — OHLCV data: Yahoo Finance → Stooq → Alpha Vantage
  get_macro_data         — Macro indicators: FRED → World Bank → OECD
  get_stock_fundamentals — Fundamentals: Yahoo Finance → FMP → SEC EDGAR
  search_tickers         — Ticker search: Yahoo Finance → Alpha Vantage
  get_asset_class_data   — Asset class data via liquid ETF proxies
  run_backtest           — Full strategy backtest engine
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("financial-data")

_fetcher = None
_backtester = None


def _get_fetcher():
    global _fetcher
    if _fetcher is None:
        from data_fetcher import DataFetcher
        _fetcher = DataFetcher()
    return _fetcher


def _get_backtester():
    global _backtester
    if _backtester is None:
        from backtest_engine import BacktestEngine
        _backtester = BacktestEngine()
    return _backtester


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@mcp.tool()
def get_price_history(
    ticker: str,
    start_date: str,
    end_date: str = "",
    interval: str = "daily",
) -> str:
    """Get historical OHLCV price data for a stock, ETF, or index.

    Automatically falls back across Yahoo Finance → Stooq → Alpha Vantage.

    Args:
        ticker:     Symbol, e.g. AAPL, SPY, QQQ, BTC-USD
        start_date: YYYY-MM-DD
        end_date:   YYYY-MM-DD (default: today)
        interval:   'daily' | 'weekly' | 'monthly'
    """
    result = _get_fetcher().get_price_history(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date or _today(),
        interval=interval,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def get_macro_data(
    indicator: str,
    start_date: str,
    end_date: str = "",
) -> str:
    """Get macroeconomic indicator time series.

    Automatically falls back across FRED → World Bank → OECD.

    Common indicator names: gdp, gdp_growth, cpi, inflation, core_cpi, pce, core_pce,
    fed_funds, ffr, unemployment, jobless_claims, 10y_yield, 2y_yield, 3m_yield,
    yield_curve, vix, m2, industrial_production, housing_starts, retail_sales,
    consumer_sentiment, sp500, dollar_index, crude_oil, gold, 10y_breakeven.
    Also accepts FRED series IDs directly (e.g. CPIAUCSL, DFF, GS10).

    Args:
        indicator:  Indicator name or FRED series ID
        start_date: YYYY-MM-DD
        end_date:   YYYY-MM-DD (default: today)
    """
    result = _get_fetcher().get_macro_data(
        indicator=indicator,
        start_date=start_date,
        end_date=end_date or _today(),
    )
    return json.dumps(result, default=str)


@mcp.tool()
def get_stock_fundamentals(
    ticker: str,
    metric: str = "all",
) -> str:
    """Get fundamental data for a stock.

    Automatically falls back across Yahoo Finance → Financial Modeling Prep → SEC EDGAR.

    Args:
        ticker: Stock symbol, e.g. AAPL
        metric: Specific metric name or 'all'.
                Options: pe_ratio, forward_pe, eps, eps_growth, price_to_book,
                price_to_sales, ev_ebitda, dividend_yield, payout_ratio, market_cap,
                revenue, revenue_growth, gross_margins, operating_margins, profit_margins,
                ebitda, free_cashflow, net_income, return_on_equity, return_on_assets,
                debt_to_equity, current_ratio, beta, sector, industry
    """
    result = _get_fetcher().get_fundamentals(ticker=ticker, metric=metric)
    return json.dumps(result, default=str)


@mcp.tool()
def search_tickers(query: str) -> str:
    """Search for stock tickers by company name or keyword.

    Args:
        query: Company name or search term, e.g. 'Apple', 'technology ETF', 'emerging markets bond'
    """
    result = _get_fetcher().search_tickers(query)
    return json.dumps(result, default=str)


@mcp.tool()
def get_asset_class_data(
    asset_class: str,
    start_date: str,
    end_date: str = "",
) -> str:
    """Get price data for a broad asset class via the most liquid ETF proxy.

    Supported asset classes: bonds, long_bonds, short_bonds, tips, commodities, gold, oil,
    reits, currencies, crypto, international_developed, international, emerging_markets,
    small_cap, large_cap, mid_cap, value, growth, dividend, technology, healthcare,
    financials, energy, utilities.

    Args:
        asset_class: Asset class name (see list above)
        start_date:  YYYY-MM-DD
        end_date:    YYYY-MM-DD (default: today)
    """
    result = _get_fetcher().get_asset_class_data(
        asset_class=asset_class,
        start_date=start_date,
        end_date=end_date or _today(),
    )
    return json.dumps(result, default=str)


@mcp.tool()
def run_backtest(
    strategy_name: str,
    universe: list,
    signals: list,
    start_date: str,
    end_date: str = "",
    rebalance_frequency: str = "monthly",
    position_sizing: str = "signal_weight",
    benchmark: str = "SPY",
    initial_capital: float = 100000.0,
    transaction_cost_bps: float = 10.0,
) -> str:
    """Run a full strategy backtest against real historical data.

    Args:
        strategy_name:       Descriptive name for this strategy
        universe:            List of tickers, e.g. ["SPY", "QQQ", "IWM", "TLT", "GLD"]
        signals:             List of signal dicts. Each dict must have:
                               - type (str): 'momentum' | 'mean_reversion' | 'trend_following'
                                             | 'value' | 'low_volatility' | 'carry'
                                             | 'quality' | 'size'
                               - lookback_days (int): e.g. 252 for 1 year, 63 for 1 quarter
                               - weight (float): relative weight of this signal
                               - description (str): plain-English description
                             Example: [{"type": "momentum", "lookback_days": 252, "weight": 1.0,
                                        "description": "12-month return skipping last month"}]
        start_date:          YYYY-MM-DD — use 2005-01-01 or earlier to cover the 2008 crisis
        end_date:            YYYY-MM-DD (default: today)
        rebalance_frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'annual'
        position_sizing:     'equal_weight' | 'signal_weight' | 'risk_parity'
                             | 'momentum' | 'min_variance'
        benchmark:           Comparison ticker, default 'SPY'
        initial_capital:     Starting USD, default 100000
        transaction_cost_bps: Cost per trade in basis points, default 10

    Returns JSON with: metrics (CAGR, Sharpe, Sortino, Calmar, max drawdown, alpha, beta,
    information ratio, VaR), monthly returns, portfolio value series, drawdown periods.
    """
    strategy = {
        "name": strategy_name,
        "universe": universe,
        "signals": signals,
        "rebalance_frequency": rebalance_frequency,
        "position_sizing": position_sizing,
        "benchmark": benchmark,
    }
    result = _get_backtester().run(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date or _today(),
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )
    return json.dumps(result, default=str)


if __name__ == "__main__":
    mcp.run()
