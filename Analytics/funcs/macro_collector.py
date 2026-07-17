"""FRED (セントルイス連銀) マクロ経済データ取得 (Analytics notebook 用)

環境変数 FRED_API_KEY (または Analytics/.env) からキーを読む。未設定/ダミー値の場合や
通信エラー時は例外を投げず、空の DataFrame を返す。
"""
from __future__ import annotations

import os
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

warnings.filterwarnings("ignore")

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
_DUMMY_VALUES = {"", "dummy_replace_me", "your_api_key_here"}

DEFAULT_SERIES: dict[str, str] = {
    "FEDFUNDS":  "fed_funds_rate",
    "DGS10":     "us10y_yield",
    "DGS2":      "us2y_yield",
    "T10Y2Y":    "us_yield_spread",
    "CPIAUCSL":  "us_cpi",
    "UNRATE":    "us_unemployment",
    "DEXJPUS":   "usdjpy_fred",
}


def _api_key() -> str | None:
    key = os.environ.get("FRED_API_KEY", "")
    return key if key not in _DUMMY_VALUES else None


def fetch_fred_series(series_id: str, start: str = "2015-01-01", end: str | None = None) -> pd.Series:
    api_key = _api_key()
    if not api_key:
        print(f"  WARN [FRED:{series_id}] FRED_API_KEY が未設定/ダミーのためスキップします")
        return pd.Series(name=series_id, dtype=float)

    if end is None:
        end = date.today().isoformat()

    try:
        r = requests.get(
            FRED_BASE_URL,
            params={
                "series_id": series_id, "api_key": api_key, "file_type": "json",
                "observation_start": start, "observation_end": end,
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
    if series_map is None:
        series_map = DEFAULT_SERIES
    if not _api_key():
        print("  WARN [FRED] FRED_API_KEY が未設定/ダミーのため download_macro_fred はスキップします")
        return pd.DataFrame(columns=["date"])

    records = []
    for series_id, name in series_map.items():
        s = fetch_fred_series(series_id, start=start, end=end)
        if not s.empty:
            records.append(s.rename(name))

    if not records:
        return pd.DataFrame(columns=["date"])

    df = pd.concat(records, axis=1).reset_index().rename(columns={"index": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").set_index("date").ffill().reset_index()
