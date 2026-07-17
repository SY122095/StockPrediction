"""J-Quants API V2 決算発表日・財務サマリー取得 (Analytics notebook 用, PEAD特徴量)

環境変数 JQUANTS_API_KEY (または Analytics/.env) からキーを読む。無料プランでの
実際のV2エンドポイントパスは未検証のため、失敗時は例外を投げず空 DataFrame を返す。
実キー取得後は https://jpx-jquants.com/ja/spec/quickstart で要確認。
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

warnings.filterwarnings("ignore")

_BASE_URL = "https://api.jquants.com/v2"
_DUMMY_VALUES = {"", "dummy_replace_me", "your_api_key_here"}


def _api_key() -> str | None:
    key = os.environ.get("JQUANTS_API_KEY", "")
    return key if key not in _DUMMY_VALUES else None


def fetch_earnings_calendar(code: str | None = None) -> pd.DataFrame:
    api_key = _api_key()
    if not api_key:
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのためスキップします")
        return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])
    try:
        params = {"code": code} if code else {}
        r = requests.get(
            f"{_BASE_URL}/fins/announcement", params=params,
            headers={"x-api-key": api_key}, timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("announcement", data if isinstance(data, list) else [])
        if not rows:
            return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])
        df = pd.DataFrame(rows).rename(
            columns={"Code": "symbol", "Date": "announcement_date", "FiscalYear": "fiscal_period"}
        )
        keep = [c for c in ["symbol", "announcement_date", "fiscal_period"] if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_earnings_calendar 取得失敗: {e}")
        return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])


def fetch_financial_summary(code: str) -> pd.DataFrame:
    api_key = _api_key()
    if not api_key:
        print(f"  WARN [J-Quants:{code}] JQUANTS_API_KEY が未設定/ダミーのためスキップします")
        return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])
    try:
        r = requests.get(
            f"{_BASE_URL}/fins/summary", params={"code": code},
            headers={"x-api-key": api_key}, timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("summary", data if isinstance(data, list) else [])
        if not rows:
            return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])
        df = pd.DataFrame(rows).rename(columns={
            "Code": "symbol", "DiscDate": "disc_date", "Sales": "sales",
            "OP": "op", "NP": "np", "EPS": "eps", "ForecastEPS": "forecast_eps",
        })
        keep = [c for c in ["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"] if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants:{code}] fetch_financial_summary 取得失敗: {e}")
        return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])


def build_earnings_events(symbols: list[str]) -> pd.DataFrame:
    """複数銘柄の決算カレンダー + 財務サマリー(実績/予想EPS)を突合し、
    symbol, announcement_date, fiscal_period, actual_eps, forecast_eps, surprise_pct を返す。"""
    cols = ["symbol", "announcement_date", "fiscal_period", "actual_eps", "forecast_eps", "surprise_pct"]
    if not _api_key():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため build_earnings_events をスキップします")
        return pd.DataFrame(columns=cols)

    records = []
    for code in symbols:
        cal = fetch_earnings_calendar(code)
        fin = fetch_financial_summary(code)
        if cal.empty:
            continue
        merged = cal.copy()
        if not fin.empty and "eps" in fin.columns:
            latest_fin = fin.sort_values("disc_date").iloc[-1]
            merged["actual_eps"] = latest_fin.get("eps")
            merged["forecast_eps"] = latest_fin.get("forecast_eps")
        else:
            merged["actual_eps"] = None
            merged["forecast_eps"] = None

        def _surprise(row):
            actual, forecast = row.get("actual_eps"), row.get("forecast_eps")
            if actual in (None, 0) or forecast in (None, 0) or pd.isna(actual) or pd.isna(forecast):
                return None
            return (actual - forecast) / abs(forecast) * 100

        merged["surprise_pct"] = merged.apply(_surprise, axis=1)
        records.append(merged)

    if not records:
        return pd.DataFrame(columns=cols)
    df = pd.concat(records, ignore_index=True)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]
