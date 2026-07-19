"""J-Quants 上場銘柄マスタ・株価一括取得 (Analytics notebook 用)

Application/backend/lib/jquants_data.py の fetch_listed_instruments / fetch_daily_quotes_range
と機能的に同一 (DB非依存)。広いユニバースでの急騰候補スクリーニング検討用。

実地検証済み (2026-07, V2):
- 上場銘柄マスタ: GET /v2/equities/master (パラメータ不要)
- 株価四本値 (単一日・全銘柄一括): GET /v2/equities/bars/daily?date=YYYY-MM-DD
"""
from __future__ import annotations

import os
import time
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
_RATE_LIMIT_SLEEP_SEC = 12.5
_EQUITY_PROD_CAT = "011"
_MARKET_SEGMENT_MAP = {"プライム": "Prime", "スタンダード": "Standard", "グロース": "Growth"}


def _api_key() -> str | None:
    key = os.environ.get("JQUANTS_API_KEY", "")
    return key if key not in _DUMMY_VALUES else None


def _code_to_symbol(code: str) -> str:
    return f"{str(code)[:4]}.T"


def fetch_listed_instruments(include_tokyo_pro: bool = False) -> pd.DataFrame:
    """東証上場銘柄マスタを取得する (株式のみ)。列: symbol, name, market_segment, sector33_code, sector33_name"""
    cols = ["symbol", "name", "market_segment", "sector33_code", "sector33_name"]
    api_key = _api_key()
    if not api_key:
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのためスキップします")
        return pd.DataFrame(columns=cols)

    try:
        r = requests.get(f"{_BASE_URL}/equities/master", headers={"x-api-key": api_key}, timeout=30)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows)
        df = df[df["ProdCat"] == _EQUITY_PROD_CAT].copy()
        if not include_tokyo_pro:
            df = df[df["MktNm"] != "TOKYO PRO MARKET"]
        df["symbol"] = df["Code"].map(_code_to_symbol)
        df["market_segment"] = df["MktNm"].map(_MARKET_SEGMENT_MAP).fillna(df["MktNm"])
        df = df.rename(columns={"CoName": "name", "S33": "sector33_code", "S33Nm": "sector33_name"})
        df = df.drop_duplicates(subset="symbol", keep="last")
        return df[cols].reset_index(drop=True)
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_listed_instruments 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def fetch_daily_quotes_by_date(date: str) -> pd.DataFrame:
    """指定日の全銘柄株価四本値を1コールで取得する。列: symbol, date, open, high, low, close, volume, turnover_value"""
    cols = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_value"]
    api_key = _api_key()
    if not api_key:
        return pd.DataFrame(columns=cols)
    try:
        r = requests.get(
            f"{_BASE_URL}/equities/bars/daily", params={"date": date},
            headers={"x-api-key": api_key}, timeout=30,
        )
        if r.status_code == 400:
            return pd.DataFrame(columns=cols)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows)
        df["symbol"] = df["Code"].map(_code_to_symbol)
        df = df.rename(columns={
            "Date": "date", "O": "open", "H": "high", "L": "low", "C": "close",
            "Vo": "volume", "Va": "turnover_value",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[cols]
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_daily_quotes_by_date({date}) 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def _probe_subscription_end_date(after: str) -> str | None:
    """`after`以降のダミー日付で400を意図的に起こし、エラーメッセージから
    実際のサブスクリプション対象期間の終端日を抽出する (無駄なレート制限消費を避けるため)。"""
    import re

    api_key = _api_key()
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{_BASE_URL}/equities/bars/daily", params={"date": after}, headers={"x-api-key": api_key}, timeout=15
        )
        if r.status_code != 400:
            return None
        msg = r.json().get("message", "")
        dates_found = re.findall(r"\d{4}-\d{2}-\d{2}", msg)
        return dates_found[1] if len(dates_found) >= 2 else None
    except Exception:
        return None


def fetch_daily_quotes_range(start: str, end: str, sleep_sec: float = _RATE_LIMIT_SLEEP_SEC) -> pd.DataFrame:
    """日付範囲の全銘柄株価四本値を取得する (1営業日=1APIコール、レート制限(約5req/分)を考慮)。
    事前probeでサブスクリプション対象期間外の日付を切り詰め、無駄な待機を避ける。"""
    cols = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_value"]
    if not _api_key():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのためスキップします")
        return pd.DataFrame(columns=cols)

    dates = pd.bdate_range(start=start, end=end)
    if len(dates) == 0:
        return pd.DataFrame(columns=cols)

    subscription_end = _probe_subscription_end_date(dates[-1].strftime("%Y-%m-%d"))
    if subscription_end is not None:
        clipped = dates[dates <= pd.Timestamp(subscription_end)]
        if len(clipped) < len(dates):
            print(f"  INFO [J-Quants] サブスクリプション対象期間は〜{subscription_end}まで。"
                  f"範囲を {len(dates)}→{len(clipped)} 営業日に短縮します")
        dates = clipped
    time.sleep(sleep_sec)

    print(f"  [J-Quants] 一括株価取得: {len(dates)} 営業日分 (約 {len(dates) * sleep_sec / 60:.1f} 分)")
    frames = []
    for i, d in enumerate(dates):
        df_day = fetch_daily_quotes_by_date(d.strftime("%Y-%m-%d"))
        if not df_day.empty:
            frames.append(df_day)
        if i < len(dates) - 1:
            time.sleep(sleep_sec)

    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)
