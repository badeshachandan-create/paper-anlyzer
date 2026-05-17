"""Event-driven backtesting engine for Stock Paper Analyzer.

Supported signal types: momentum, mean_reversion, trend_following,
  value, low_volatility, carry, quality, size
Supported position sizing: equal_weight, signal_weight, risk_parity,
  momentum (top-tercile), min_variance
Rebalancing: daily, weekly, monthly, quarterly, annual
"""

import numpy as np
import pandas as pd
from data_fetcher import DataFetcher


class BacktestEngine:
    TRADING_DAYS = 252
    RF_ANNUAL = 0.05

    def __init__(self):
        self.fetcher = DataFetcher()

    def run(
        self,
        strategy: dict,
        start_date: str,
        end_date: str,
        initial_capital: float = 100_000,
        transaction_cost_bps: float = 10,
    ) -> dict:
        universe = strategy.get("universe", ["SPY"])
        signals_spec = strategy.get("signals", [])
        rebalance_freq = strategy.get("rebalance_frequency", "monthly")
        position_sizing = strategy.get("position_sizing", "signal_weight")
        benchmark = strategy.get("benchmark", "SPY")
        name = strategy.get("name", "Custom Strategy")

        # ── 1. Fetch price data ────────────────────────────────────────────
        all_tickers = list(dict.fromkeys(universe + [benchmark]))
        raw_prices, failed = {}, []
        for ticker in all_tickers:
            result = self.fetcher.get_price_history(ticker, start_date, end_date)
            if "error" not in result:
                close = result.get("ohlcv", {}).get("close") or result.get("data", {})
                if close:
                    raw_prices[ticker] = close
                else:
                    failed.append(ticker)
            else:
                failed.append(ticker)

        if not raw_prices:
            return {"error": "No price data available for any ticker", "failed": failed}

        # ── 2. Build aligned DataFrame ─────────────────────────────────────
        prices = pd.DataFrame(raw_prices)
        prices.index = pd.to_datetime(prices.index)
        prices = prices.sort_index().apply(pd.to_numeric, errors="coerce").ffill().dropna(how="all")

        strat_tickers = [t for t in universe if t in prices.columns]
        if not strat_tickers:
            return {"error": "No universe tickers survived data fetch", "failed": failed}

        returns = prices.pct_change().fillna(0)
        strat_ret = returns[strat_tickers]
        bench_ret = returns[benchmark] if benchmark in returns.columns else pd.Series(0.0, index=returns.index)

        # ── 3. Compute signal matrix ───────────────────────────────────────
        signal_matrix = self._compute_signals(prices[strat_tickers], strat_ret, signals_spec)

        # ── 4. Simulate ────────────────────────────────────────────────────
        rebalance_set = self._rebalance_dates(returns.index, rebalance_freq)
        txn_cost = transaction_cost_bps / 10_000

        values = [initial_capital]
        port_rets = []
        weights_log = {}
        turnover_log = []
        w = pd.Series(0.0, index=strat_tickers)

        for date in returns.index:
            rebalancing = date in rebalance_set or w.sum() == 0
            if rebalancing:
                target = self._target_weights(
                    date, signal_matrix, strat_tickers, position_sizing,
                    prices.loc[:date, strat_tickers]
                )
                turnover = float((target - w).abs().sum() / 2)
                turnover_log.append(turnover)
                w = target
                weights_log[str(date.date())] = w.to_dict()
            else:
                turnover_log.append(0.0)

            gross = float((strat_ret.loc[date] * w).sum())
            cost = (turnover_log[-1] * txn_cost) if rebalancing else 0.0
            net = gross - cost

            port_rets.append(net)
            values.append(values[-1] * (1 + net))

            # Drift weights
            drifted = w * (1 + strat_ret.loc[date])
            total = drifted.sum()
            if total > 0:
                w = drifted / total

        # ── 5. Analytics ───────────────────────────────────────────────────
        port_series = pd.Series(port_rets, index=returns.index)
        bench_aligned = bench_ret.reindex(returns.index).fillna(0)
        metrics = self._analytics(port_series, bench_aligned, initial_capital, values)

        monthly = port_series.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        bench_monthly = bench_aligned.resample("ME").apply(lambda x: (1 + x).prod() - 1)

        active_turns = [t for t in turnover_log if t > 0]
        return {
            "strategy_name": name,
            "backtest_period": {"start": start_date, "end": end_date},
            "universe": universe,
            "failed_tickers": failed,
            "metrics": metrics,
            "monthly_returns": {str(k.date()): round(float(v), 6) for k, v in monthly.items()},
            "benchmark_monthly_returns": {str(k.date()): round(float(v), 6) for k, v in bench_monthly.items()},
            "portfolio_values": {str(returns.index[i].date()): round(v, 2) for i, v in enumerate(values[1:])},
            "final_value": round(values[-1], 2),
            "initial_capital": initial_capital,
            "current_weights": w.to_dict(),
            "avg_turnover_per_rebalance": round(float(np.mean(active_turns)) if active_turns else 0, 4),
            "transaction_cost_bps": transaction_cost_bps,
        }

    # ── Signal computation ─────────────────────────────────────────────────

    def _compute_signals(self, prices: pd.DataFrame, returns: pd.DataFrame, specs: list) -> pd.DataFrame:
        if not specs:
            return pd.DataFrame(1.0, index=prices.index, columns=prices.columns)

        combined = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

        for spec in specs:
            stype = spec.get("type", "momentum")
            lb = int(spec.get("lookback_days", 252))
            w = float(spec.get("weight", 1.0))

            if stype == "momentum":
                sig = prices.pct_change(lb)

            elif stype == "mean_reversion":
                mu = prices.rolling(lb).mean()
                sd = prices.rolling(lb).std().replace(0, np.nan)
                sig = -((prices - mu) / sd)

            elif stype == "trend_following":
                ma = prices.rolling(lb).mean()
                sig = (prices > ma).astype(float) * 2 - 1

            elif stype == "value":
                peak = prices.rolling(min(252, lb)).max()
                sig = peak / prices.replace(0, np.nan)

            elif stype == "low_volatility":
                vol = returns.rolling(lb).std().replace(0, np.nan)
                sig = 1 / vol

            elif stype == "carry":
                sig = pd.DataFrame(1.0, index=prices.index, columns=prices.columns)

            elif stype == "quality":
                vol = returns.rolling(lb).std().replace(0, np.nan)
                trend = (prices.pct_change(lb) > 0).astype(float)
                sig = trend / vol

            elif stype == "size":
                sig = 1 / prices.replace(0, np.nan)

            else:
                sig = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

            combined += sig.fillna(0) * w

        return combined

    # ── Target weights ─────────────────────────────────────────────────────

    def _target_weights(
        self, date, signal_matrix: pd.DataFrame,
        tickers: list, method: str, hist_prices: pd.DataFrame
    ) -> pd.Series:
        n = len(tickers)
        fallback = pd.Series(1 / n, index=tickers)

        if date not in signal_matrix.index:
            return fallback

        scores = signal_matrix.loc[date, tickers].fillna(0)

        if method == "equal_weight":
            return fallback

        if method == "signal_weight":
            pos = scores.clip(lower=0)
            total = pos.sum()
            return pos / total if total > 0 else fallback

        if method == "risk_parity":
            if len(hist_prices) >= 21:
                vol = hist_prices.pct_change().tail(21).std().replace(0, np.nan)
                inv_vol = (1 / vol).fillna(0)
                total = inv_vol.sum()
                return inv_vol / total if total > 0 else fallback
            return fallback

        if method == "momentum":
            n_select = max(1, n // 3)
            top = scores.nlargest(n_select).index
            w = pd.Series(0.0, index=tickers)
            w[top] = 1.0 / n_select
            return w

        if method == "min_variance":
            if len(hist_prices) >= 30:
                ret_mat = hist_prices.pct_change().tail(60).dropna()
                var = np.diag(ret_mat.cov().values)
                inv_var = np.where(var > 0, 1 / var, 0.0)
                total = inv_var.sum()
                return pd.Series(inv_var / total if total > 0 else np.full(n, 1 / n), index=tickers)
            return fallback

        return fallback

    # ── Rebalance schedule ─────────────────────────────────────────────────

    def _rebalance_dates(self, index: pd.DatetimeIndex, freq: str) -> set:
        if freq == "daily":
            return set(index)
        if freq == "weekly":
            return set(index[index.dayofweek == 4])
        if freq == "monthly":
            return set(index[index.is_month_end])
        if freq == "quarterly":
            return set(index[index.month.isin([3, 6, 9, 12]) & index.is_month_end])
        if freq == "annual":
            return set(index[index.is_year_end])
        return set(index[index.is_month_end])

    # ── Performance analytics ──────────────────────────────────────────────

    def _analytics(
        self, port: pd.Series, bench: pd.Series, initial: float, values: list
    ) -> dict:
        TD = self.TRADING_DAYS
        rf_daily = self.RF_ANNUAL / TD

        total_ret = (values[-1] / initial) - 1
        n_years = len(port) / TD
        cagr = (1 + total_ret) ** (1 / n_years) - 1 if n_years > 0 else 0.0
        ann_vol = float(port.std() * np.sqrt(TD))

        sharpe = float(
            (port.mean() - rf_daily) / port.std() * np.sqrt(TD)
        ) if port.std() > 0 else 0.0

        down_std = port[port < rf_daily].std()
        sortino = float(
            (port.mean() - rf_daily) / down_std * np.sqrt(TD)
        ) if down_std > 0 else 0.0

        val_series = pd.Series(values)
        peak = val_series.expanding().max()
        drawdowns = (val_series - peak) / peak
        max_dd = float(drawdowns.min())
        calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

        # Significant drawdown periods
        dd_periods = []
        in_dd = False
        dd_start_idx = None
        for i, (date, dd_val) in enumerate(zip(port.index, drawdowns.values[1:])):
            if dd_val < -0.05 and not in_dd:
                in_dd = True
                dd_start_idx = i
            elif dd_val >= -0.01 and in_dd:
                in_dd = False
                depth = float(drawdowns.values[dd_start_idx + 1: i + 2].min())
                dd_periods.append({
                    "start": str(port.index[dd_start_idx].date()),
                    "end": str(date.date()),
                    "max_depth": f"{depth:.2%}",
                })

        bench_total = float((1 + bench).prod() - 1)
        bench_cagr = float((1 + bench_total) ** (1 / n_years) - 1) if n_years > 0 else 0.0

        if bench.std() > 0:
            cov_mat = np.cov(port.values, bench.values)
            beta = float(cov_mat[0, 1] / cov_mat[1, 1])
            alpha_ann = float((port.mean() - beta * bench.mean()) * TD)
            active = port - bench
            ir = float(active.mean() / active.std() * np.sqrt(TD)) if active.std() > 0 else 0.0
            win_rate = float((port > bench).mean())
        else:
            beta = alpha_ann = ir = win_rate = 0.0

        var_95 = float(np.percentile(port, 5))
        cvar_95 = float(port[port <= var_95].mean())

        monthly = port.resample("ME").apply(lambda x: (1 + x).prod() - 1)

        return {
            "total_return": f"{total_ret:.2%}",
            "cagr": f"{cagr:.2%}",
            "annualized_volatility": f"{ann_vol:.2%}",
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "max_drawdown": f"{max_dd:.2%}",
            "var_95_daily": f"{var_95:.2%}",
            "cvar_95_daily": f"{cvar_95:.2%}",
            "vs_benchmark": {
                "benchmark_total_return": f"{bench_total:.2%}",
                "benchmark_cagr": f"{bench_cagr:.2%}",
                "alpha_annualized": f"{alpha_ann:.2%}",
                "beta": round(beta, 3),
                "information_ratio": round(ir, 3),
                "win_rate_vs_benchmark": f"{win_rate:.2%}",
            },
            "monthly_stats": {
                "best_month": f"{float(monthly.max()):.2%}" if len(monthly) else "N/A",
                "worst_month": f"{float(monthly.min()):.2%}" if len(monthly) else "N/A",
                "avg_monthly_return": f"{float(monthly.mean()):.2%}" if len(monthly) else "N/A",
                "pct_positive_months": f"{float((monthly > 0).mean()):.2%}" if len(monthly) else "N/A",
            },
            "significant_drawdown_periods": dd_periods[:5],
        }
