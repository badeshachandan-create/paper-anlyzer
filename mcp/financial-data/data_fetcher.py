"""Multi-source financial data fetcher with automatic fallback chains.

Stock prices:   Yahoo Finance  → Stooq            → Alpha Vantage
Macro data:     FRED           → World Bank        → OECD
Fundamentals:   Yahoo Finance  → Financial Modeling Prep → SEC EDGAR
"""

import os
import re
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional


class DataFetcher:
    def __init__(self):
        self.alpha_key = os.environ.get("ALPHA_VANTAGE_KEY", "")
        self.fmp_key = os.environ.get("FMP_API_KEY", "")
        self.fred_key = os.environ.get("FRED_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "StockPaperAnalyzer/1.0 research@example.com"}
        )

    # ──────────────────────────────────────────────────────────
    # PRICE HISTORY
    # ──────────────────────────────────────────────────────────

    def get_price_history(
        self, ticker: str, start_date: str, end_date: str, interval: str = "daily"
    ) -> dict:
        errors = []
        for label, fn in [
            ("Yahoo Finance", self._yahoo_price),
            ("Stooq", self._stooq_price),
            ("Alpha Vantage", self._alpha_vantage_price),
        ]:
            try:
                return fn(ticker, start_date, end_date, interval)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        return {"error": "All price sources failed", "ticker": ticker, "details": errors}

    def _yahoo_price(self, ticker, start, end, interval):
        import yfinance as yf

        iv = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}.get(interval, "1d")
        df = yf.download(ticker, start=start, end=end, interval=iv, progress=False, auto_adjust=True)
        if df.empty:
            raise ValueError("No data returned")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        close = df["Close"].to_dict()
        return {
            "source": "Yahoo Finance",
            "ticker": ticker,
            "interval": interval,
            "data": close,
            "ohlcv": {
                "open": df["Open"].to_dict(),
                "high": df["High"].to_dict(),
                "low": df["Low"].to_dict(),
                "close": close,
                "volume": df.get("Volume", pd.Series(dtype=float)).to_dict(),
            },
        }

    def _stooq_price(self, ticker, start, end, interval):
        import pandas_datareader as pdr

        df = pdr.get_data_stooq(ticker, start=start, end=end)
        if df.empty:
            raise ValueError("No data returned")
        df = df.sort_index()
        df.index = df.index.strftime("%Y-%m-%d")
        close = df["Close"].to_dict()
        return {
            "source": "Stooq",
            "ticker": ticker,
            "interval": interval,
            "data": close,
            "ohlcv": {
                "open": df["Open"].to_dict(),
                "high": df["High"].to_dict(),
                "low": df["Low"].to_dict(),
                "close": close,
                "volume": df.get("Volume", pd.Series(dtype=float)).to_dict(),
            },
        }

    def _alpha_vantage_price(self, ticker, start, end, interval):
        if not self.alpha_key:
            raise ValueError("ALPHA_VANTAGE_KEY not set")
        func = {
            "daily": "TIME_SERIES_DAILY_ADJUSTED",
            "weekly": "TIME_SERIES_WEEKLY_ADJUSTED",
            "monthly": "TIME_SERIES_MONTHLY_ADJUSTED",
        }.get(interval, "TIME_SERIES_DAILY_ADJUSTED")
        url = (
            f"https://www.alphavantage.co/query?function={func}&symbol={ticker}"
            f"&outputsize=full&apikey={self.alpha_key}"
        )
        data = self._session.get(url, timeout=20).json()
        ts_key = next((k for k in data if "Time Series" in k), None)
        if not ts_key:
            note = data.get("Note") or data.get("Information") or str(data)
            raise ValueError(f"Alpha Vantage: {note}")
        ts = data[ts_key]
        close_key = "5. adjusted close" if "adjusted close" in str(list(ts.values())[:1]) else "4. close"
        close = {
            k: float(v.get(close_key, v.get("4. close", 0)))
            for k, v in ts.items()
            if start <= k <= end
        }
        if not close:
            raise ValueError("No data in requested date range")
        return {
            "source": "Alpha Vantage",
            "ticker": ticker,
            "interval": interval,
            "data": close,
            "ohlcv": {"close": close},
        }

    # ──────────────────────────────────────────────────────────
    # MACRO DATA
    # ──────────────────────────────────────────────────────────

    FRED_SERIES = {
        "gdp": "GDP",
        "gdp_growth": "GDPC1",
        "cpi": "CPIAUCSL",
        "inflation": "CPIAUCSL",
        "core_cpi": "CPILFESL",
        "pce": "PCE",
        "core_pce": "PCEPILFE",
        "fed_funds": "DFF",
        "ffr": "DFF",
        "interest_rate": "DFF",
        "unemployment": "UNRATE",
        "jobless_claims": "ICSA",
        "10y_yield": "GS10",
        "2y_yield": "GS2",
        "3m_yield": "TB3MS",
        "yield_curve": "T10Y2Y",
        "yield_spread": "T10Y2Y",
        "vix": "VIXCLS",
        "m2": "M2SL",
        "m1": "M1SL",
        "industrial_production": "INDPRO",
        "capacity_utilization": "TCU",
        "housing_starts": "HOUST",
        "retail_sales": "RSAFS",
        "trade_balance": "BOPGSTB",
        "consumer_sentiment": "UMCSENT",
        "sp500": "SP500",
        "nasdaq": "NASDAQCOM",
        "dollar_index": "DTWEXBGS",
        "crude_oil": "DCOILWTICO",
        "gold_fix": "GOLDAMGBD228NLBM",
        "10y_breakeven": "T10YIE",
        "5y_breakeven": "T5YIE",
        "credit_spread": "BAMLH0A0HYM2",
        "ted_spread": "TEDRATE",
    }

    def get_macro_data(self, indicator: str, start_date: str, end_date: str) -> dict:
        errors = []
        for label, fn in [
            ("FRED", self._fred_data),
            ("World Bank", self._worldbank_data),
            ("OECD", self._oecd_data),
        ]:
            try:
                return fn(indicator, start_date, end_date)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        return {
            "error": "All macro sources failed",
            "indicator": indicator,
            "details": errors,
        }

    def _fred_data(self, indicator, start_date, end_date):
        import pandas_datareader.data as web

        series_id = self.FRED_SERIES.get(indicator.lower(), indicator.upper())
        df = web.get_data_fred(series_id, start=start_date, end=end_date)
        if df.empty:
            raise ValueError(f"FRED: no observations for {series_id}")
        df.index = df.index.strftime("%Y-%m-%d")
        series = df.iloc[:, 0].dropna()
        return {
            "source": "FRED",
            "indicator": indicator,
            "series_id": series_id,
            "data": series.to_dict(),
            "latest_value": float(series.iloc[-1]) if len(series) else None,
            "latest_date": str(series.index[-1]) if len(series) else None,
        }

    def _worldbank_data(self, indicator, start_date, end_date):
        WB_MAP = {
            "gdp": "NY.GDP.MKTP.CD",
            "gdp_growth": "NY.GDP.MKTP.KD.ZG",
            "inflation": "FP.CPI.TOTL.ZG",
            "unemployment": "SL.UEM.TOTL.ZS",
            "interest_rate": "FR.INR.RINR",
            "current_account": "BN.CAB.XOKA.GD.ZS",
        }
        wb_id = WB_MAP.get(indicator.lower(), indicator)
        start_year, end_year = start_date[:4], end_date[:4]
        url = (
            f"https://api.worldbank.org/v2/country/US/indicator/{wb_id}"
            f"?date={start_year}:{end_year}&format=json&per_page=50"
        )
        resp = self._session.get(url, timeout=15).json()
        if len(resp) < 2 or not resp[1]:
            raise ValueError("World Bank: no data returned")
        data = {item["date"]: item["value"] for item in resp[1] if item["value"] is not None}
        if not data:
            raise ValueError("World Bank: empty dataset")
        return {"source": "World Bank", "indicator": indicator, "wb_indicator": wb_id, "data": data}

    def _oecd_data(self, indicator, start_date, end_date):
        OECD_MAP = {
            "gdp": "GDPVALUE",
            "cpi": "CPI",
            "unemployment": "UNRT",
            "interest_rate": "IRLT",
        }
        oecd_id = OECD_MAP.get(indicator.lower())
        if not oecd_id:
            raise ValueError(f"No OECD mapping for '{indicator}'")
        url = (
            f"https://stats.oecd.org/sdmx-json/data/DP_LIVE/USA.{oecd_id}.../OECD"
            f"?contentType=csv&detail=code&separator=comma&csv-lang=en"
            f"&startPeriod={start_date[:7]}&endPeriod={end_date[:7]}"
        )
        r = self._session.get(url, timeout=20)
        if r.status_code != 200:
            raise ValueError(f"OECD HTTP {r.status_code}")
        data = {}
        for line in r.text.strip().split("\n")[1:]:
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    data[parts[-2].strip('"')] = float(parts[-1].strip('"'))
                except (ValueError, IndexError):
                    pass
        if not data:
            raise ValueError("OECD: could not parse response")
        return {"source": "OECD", "indicator": indicator, "data": data}

    # ──────────────────────────────────────────────────────────
    # FUNDAMENTALS
    # ──────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str, metric: str = "all") -> dict:
        errors = []
        for label, fn in [
            ("Yahoo Finance", self._yahoo_fundamentals),
            ("Financial Modeling Prep", self._fmp_fundamentals),
            ("SEC EDGAR", self._edgar_fundamentals),
        ]:
            try:
                return fn(ticker, metric)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        return {"error": "All fundamental sources failed", "ticker": ticker, "details": errors}

    def _yahoo_fundamentals(self, ticker, metric):
        import yfinance as yf

        info = yf.Ticker(ticker).info
        if not info or len(info) < 5:
            raise ValueError("Insufficient data returned")
        all_fields = {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "eps_growth": info.get("earningsGrowth"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "ebitda": info.get("ebitda"),
            "free_cashflow": info.get("freeCashflow"),
            "net_income": info.get("netIncomeToCommon"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "short_ratio": info.get("shortRatio"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
        }
        fundamentals = {metric: all_fields[metric]} if metric != "all" and metric in all_fields else all_fields
        return {"source": "Yahoo Finance", "ticker": ticker, "fundamentals": fundamentals}

    def _fmp_fundamentals(self, ticker, metric):
        key = self.fmp_key or "demo"
        url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={key}"
        data = self._session.get(url, timeout=10).json()
        if not data or (isinstance(data, dict) and "Error" in str(data)):
            raise ValueError(f"FMP returned error: {data}")
        p = data[0] if isinstance(data, list) else data
        fundamentals = {
            "pe_ratio": p.get("pe"),
            "eps": p.get("eps"),
            "beta": p.get("beta"),
            "market_cap": p.get("mktCap"),
            "price_to_book": p.get("priceToBookRatioTTM"),
            "sector": p.get("sector"),
            "industry": p.get("industry"),
            "dividend_yield": p.get("lastDiv"),
            "price": p.get("price"),
        }
        return {"source": "Financial Modeling Prep", "ticker": ticker, "fundamentals": fundamentals}

    def _edgar_fundamentals(self, ticker, metric):
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK={ticker}"
            f"&type=10-K&dateb=&owner=include&count=1&action=getcompany&output=atom"
        )
        r = self._session.get(url, timeout=15)
        cik_match = re.search(r"CIK=(\d+)", r.text)
        if not cik_match:
            raise ValueError("Could not resolve CIK from EDGAR")
        cik = cik_match.group(1).zfill(10)
        facts = self._session.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", timeout=20
        ).json()
        gaap = facts.get("facts", {}).get("us-gaap", {})

        def latest(concept):
            for unit_vals in gaap.get(concept, {}).get("units", {}).values():
                annual = [e for e in unit_vals if e.get("form") == "10-K"]
                if annual:
                    return annual[-1].get("val")
            return None

        fundamentals = {
            "revenue": latest("Revenues") or latest("RevenueFromContractWithCustomerExcludingAssessedTax"),
            "net_income": latest("NetIncomeLoss"),
            "eps_basic": latest("EarningsPerShareBasic"),
            "eps_diluted": latest("EarningsPerShareDiluted"),
            "total_assets": latest("Assets"),
            "total_liabilities": latest("Liabilities"),
            "stockholders_equity": latest("StockholdersEquity"),
            "operating_income": latest("OperatingIncomeLoss"),
            "cash": latest("CashAndCashEquivalentsAtCarryingValue"),
        }
        return {"source": "SEC EDGAR", "ticker": ticker, "fundamentals": fundamentals}

    # ──────────────────────────────────────────────────────────
    # SEARCH & ASSET CLASSES
    # ──────────────────────────────────────────────────────────

    def search_tickers(self, query: str) -> dict:
        try:
            import yfinance as yf
            results = yf.Search(query, max_results=10).quotes
            return {"source": "Yahoo Finance", "results": results[:10]}
        except Exception as exc_yf:
            if self.alpha_key:
                try:
                    url = (
                        f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH"
                        f"&keywords={query}&apikey={self.alpha_key}"
                    )
                    data = self._session.get(url, timeout=10).json()
                    return {"source": "Alpha Vantage", "results": data.get("bestMatches", [])}
                except Exception as exc_av:
                    return {"error": f"Yahoo: {exc_yf} | Alpha Vantage: {exc_av}"}
            return {"error": str(exc_yf)}

    ASSET_CLASS_PROXIES = {
        "bonds": ["AGG", "BND", "TLT"],
        "long_bonds": ["TLT", "EDV", "ZROZ"],
        "short_bonds": ["SHY", "BIL", "SGOV"],
        "tips": ["TIP", "SCHP", "STIP"],
        "commodities": ["DJP", "PDBC", "GSG"],
        "gold": ["GLD", "IAU", "GLDM"],
        "oil": ["USO", "BNO", "UCO"],
        "reits": ["VNQ", "IYR", "SCHH"],
        "currencies": ["UUP", "FXE", "FXY"],
        "crypto": ["BTC-USD", "ETH-USD"],
        "international_developed": ["EFA", "VEA", "SPDW"],
        "international": ["EFA", "VEU", "ACWX"],
        "emerging_markets": ["EEM", "VWO", "IEMG"],
        "small_cap": ["IWM", "VB", "SCHA"],
        "large_cap": ["SPY", "VOO", "IVV"],
        "mid_cap": ["IJH", "VO", "MDY"],
        "value": ["VTV", "IWD", "VONV"],
        "growth": ["VUG", "IWF", "VONG"],
        "dividend": ["VYM", "HDV", "SCHD"],
        "technology": ["QQQ", "VGT", "XLK"],
        "healthcare": ["XLV", "VHT", "IYH"],
        "financials": ["XLF", "VFH", "KRE"],
        "energy": ["XLE", "VDE", "OIH"],
        "utilities": ["XLU", "VPU", "IDU"],
    }

    def get_asset_class_data(self, asset_class: str, start_date: str, end_date: str) -> dict:
        key = asset_class.lower().replace(" ", "_")
        tickers = self.ASSET_CLASS_PROXIES.get(key, [asset_class])
        for ticker in tickers:
            data = self.get_price_history(ticker, start_date, end_date)
            if "error" not in data:
                return {"asset_class": asset_class, "proxy_ticker": ticker, **data}
        return {"error": f"No data for asset class '{asset_class}'", "tried": tickers}
