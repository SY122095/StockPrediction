"""FRED (セントルイス連銀) マクロ経済データ取得

APIキー未設定/ダミー値の場合や通信エラー時は例外を投げず、空の DataFrame を返す。
呼び出し側 (services / build_features) はこれを前提に None-safe に扱う。
"""
from __future__ import annotations

import warnings
from datetime import date

import pandas as pd
import requests

from core.config import settings

warnings.filterwarnings("ignore")

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# デフォルトで取得するマクロ系列 (docs/api_setup_guide.md 6章 参照)
DEFAULT_SERIES: dict[str, str] = {
    "FEDFUNDS":  "fed_funds_rate",   # FF金利
    "DGS10":     "us10y_yield",      # 米10年債利回り
    "DGS2":      "us2y_yield",       # 米2年債利回り
    "T10Y2Y":    "us_yield_spread",  # 長短金利差 (逆イールド)
    "CPIAUCSL":  "us_cpi",           # 米CPI
    "UNRATE":    "us_unemployment",  # 米失業率
    "DEXJPUS":   "usdjpy_fred",      # ドル円 (FRED版)
}


def fetch_fred_series(series_id: str, start: str = "2015-01-01", end: str | None = None) -> pd.Series:
    """1系列を取得。取得不可の場合は空の Series を返す。"""
    if not settings.is_configured("fred_api_key"):
        print(f"  WARN [FRED:{series_id}] FRED_API_KEY が未設定/ダミーのためスキップします")
        return pd.Series(name=series_id, dtype=float)

    if end is None:
        end = date.today().isoformat()

    try:
        r = requests.get(
            FRED_BASE_URL,
            params={
                "series_id": series_id,
                "api_key": settings.fred_api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
            },
            timeout=15,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if not obs:
            return pd.Series(name=series_id, dtype=float)
        df = pd.DataFrame(obs)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        s = df.set_index("date")["value"]
        s.name = series_id
        return s
    except Exception as e:
        print(f"  WARN [FRED:{series_id}] 取得失敗: {e}")
        return pd.Series(name=series_id, dtype=float)


def download_macro_fred(
    series_map: dict[str, str] | None = None,
    start: str = "2015-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """複数系列をまとめて取得し、date列 + 各系列名(列) の wide DataFrame を返す。

    APIキー未設定時は空 DataFrame (列: date のみ) を返す。
    """
    if series_map is None:
        series_map = DEFAULT_SERIES

    if not settings.is_configured("fred_api_key"):
        print("  WARN [FRED] FRED_API_KEY が未設定/ダミーのため download_macro_fred はスキップします")
        return pd.DataFrame(columns=["date"])

    records = []
    for series_id, name in series_map.items():
        s = fetch_fred_series(series_id, start=start, end=end)
        if not s.empty:
            s = s.rename(name)
            records.append(s)

    if not records:
        return pd.DataFrame(columns=["date"])

    df = pd.concat(records, axis=1).reset_index()
    df = df.rename(columns={"index": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").set_index("date").ffill().reset_index()
