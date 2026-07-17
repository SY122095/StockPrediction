"""センチメント指標取得: 暗号資産 Fear&Greed Index (alternative.me) / 株式 VIX 特徴量"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

FEAR_GREED_URL = "https://api.alternative.me/fng/"


def fetch_fear_greed_index(limit: int = 0) -> pd.DataFrame:
    """alternative.me の Fear & Greed Index (暗号資産) を取得する。認証不要。

    limit=0 で取得可能な全履歴を返す。
    戻り値の列: date, fear_greed_value, fear_greed_label
    """
    try:
        r = requests.get(FEAR_GREED_URL, params={"limit": limit, "format": "json"}, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame(columns=["date", "fear_greed_value", "fear_greed_label"])
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s").dt.normalize()
        df["fear_greed_value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.rename(columns={"value_classification": "fear_greed_label"})
        return df[["date", "fear_greed_value", "fear_greed_label"]].sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"  WARN [Fear&Greed] 取得失敗: {e}")
        return pd.DataFrame(columns=["date", "fear_greed_value", "fear_greed_label"])


def compute_vix_sentiment(df_macro: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """yfinance 由来のマクロ DataFrame (vix列を含む) から VIX センチメント特徴量を計算する。

    戻り値の列: date, vix, vix_chg1d, vix_zscore
    """
    if df_macro is None or df_macro.empty or "vix" not in df_macro.columns:
        return pd.DataFrame(columns=["date", "vix", "vix_chg1d", "vix_zscore"])

    df = df_macro[["date", "vix"]].dropna().sort_values("date").copy()
    df["vix_chg1d"] = df["vix"].pct_change()
    roll_mean = df["vix"].rolling(window, min_periods=window // 2).mean()
    roll_std = df["vix"].rolling(window, min_periods=window // 2).std()
    df["vix_zscore"] = (df["vix"] - roll_mean) / roll_std.replace(0, np.nan)
    return df.reset_index(drop=True)
