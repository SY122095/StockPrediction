"""J-Quants API V2 (JPX公式) 決算発表日・財務サマリー取得

PEAD (決算発表後ドリフト) 特徴量のためのイベントデータ取得。
無料プランでの実際のV2エンドポイントパス・レスポンス形式は本実装時点で未検証のため、
すべての呼び出しを try/except で保護し、失敗時は空 DataFrame を返す。
実キー取得後は https://jpx-jquants.com/ja/spec/quickstart の公式ノートブックで
エンドポイントパスを確認し、必要なら _BASE_URL 以下のパスを調整すること。
"""
from __future__ import annotations

import warnings

import pandas as pd
import requests

from core.config import settings

warnings.filterwarnings("ignore")

_BASE_URL = "https://api.jquants.com/v2"


def _headers() -> dict[str, str]:
    return {"x-api-key": settings.jquants_api_key}


def _configured() -> bool:
    return settings.is_configured("jquants_api_key")


def fetch_earnings_calendar(code: str | None = None) -> pd.DataFrame:
    """決算発表予定日一覧を取得する。

    戻り値の列: symbol, announcement_date, fiscal_period
    """
    if not _configured():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため fetch_earnings_calendar をスキップします")
        return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])

    try:
        params = {"code": code} if code else {}
        r = requests.get(f"{_BASE_URL}/fins/announcement", params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        rows = data.get("announcement", data if isinstance(data, list) else [])
        if not rows:
            return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])
        df = pd.DataFrame(rows)
        rename_map = {"Code": "symbol", "Date": "announcement_date", "FiscalYear": "fiscal_period"}
        df = df.rename(columns=rename_map)
        keep = [c for c in ["symbol", "announcement_date", "fiscal_period"] if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_earnings_calendar 取得失敗（無料プラン対象外/エンドポイント未確定の可能性）: {e}")
        return pd.DataFrame(columns=["symbol", "announcement_date", "fiscal_period"])


def fetch_financial_summary(code: str) -> pd.DataFrame:
    """財務サマリー (売上・営業利益・純利益・EPS 実績/予想) を取得する。

    戻り値の列: symbol, disc_date, sales, op, np, eps, forecast_eps
    """
    if not _configured():
        print(f"  WARN [J-Quants:{code}] JQUANTS_API_KEY が未設定/ダミーのため fetch_financial_summary をスキップします")
        return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])

    try:
        r = requests.get(f"{_BASE_URL}/fins/summary", params={"code": code}, headers=_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        rows = data.get("summary", data if isinstance(data, list) else [])
        if not rows:
            return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])
        df = pd.DataFrame(rows)
        rename_map = {
            "Code": "symbol", "DiscDate": "disc_date", "Sales": "sales",
            "OP": "op", "NP": "np", "EPS": "eps", "ForecastEPS": "forecast_eps",
        }
        df = df.rename(columns=rename_map)
        keep = [c for c in ["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"] if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants:{code}] fetch_financial_summary 取得失敗: {e}")
        return pd.DataFrame(columns=["symbol", "disc_date", "sales", "op", "np", "eps", "forecast_eps"])


def build_earnings_events(symbols: list[str]) -> pd.DataFrame:
    """複数銘柄の決算カレンダー + 財務サマリー(実績/予想EPS)を突合し、
    EarningsEvent テーブル投入用の統合 DataFrame を返す。

    戻り値の列: symbol, announcement_date, fiscal_period, actual_eps, forecast_eps, surprise_pct
    """
    cols = ["symbol", "announcement_date", "fiscal_period", "actual_eps", "forecast_eps", "surprise_pct"]
    if not _configured():
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
