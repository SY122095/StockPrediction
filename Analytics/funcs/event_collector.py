"""J-Quants API V2 決算発表日・財務サマリー取得 (Analytics notebook 用, PEAD特徴量)

環境変数 JQUANTS_API_KEY (または Analytics/.env) からキーを読む。

実キーで実地検証済み (2026-07):
- 財務サマリー: GET /v2/fins/summary?code=XXXX (200 OK、実データ確認済み)
- **/v2/fins/announcement は存在しない** (404相当"endpoint does not exist"を実地確認)。
  決算発表日は fins/summary の DiscDate (開示日) で代替する。過去の開示のみ取得可能で、
  将来の決算発表予定日は本エンドポイントからは分からない。
- `code` パラメータは4〜5桁のJ-Quants形式が必須 ("7203.T" を直接渡すと
  `'code' must be 4 or 5 characters.` で400になる、実地確認済み)。symbol引数は
  プロジェクト標準の "7203.T" 形式で受け取り、内部で変換する。
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


def _symbol_to_code(symbol: str) -> str:
    """プロジェクト標準シンボル ("7203.T") → J-Quants 5桁コード ("72030")"""
    return f"{symbol.replace('.T', '')}0"


def _code_to_symbol(code: str) -> str:
    """J-Quants 5桁コード ("72030") → プロジェクト標準シンボル ("7203.T")"""
    return f"{str(code)[:4]}.T"


def fetch_financial_summary(symbol: str) -> pd.DataFrame:
    """財務サマリー (売上・営業利益・純利益・EPS 実績/予想) を取得する。

    戻り値の列: symbol, disc_date, period_type, fy_end, sales, op, np, eps,
                forecast_eps_this (当期予想EPS), forecast_eps_next (来期予想EPS)
    """
    cols = ["symbol", "disc_date", "period_type", "fy_end", "sales", "op", "np",
            "eps", "forecast_eps_this", "forecast_eps_next"]
    api_key = _api_key()
    if not api_key:
        print(f"  WARN [J-Quants:{symbol}] JQUANTS_API_KEY が未設定/ダミーのためスキップします")
        return pd.DataFrame(columns=cols)
    try:
        code = _symbol_to_code(symbol)
        r = requests.get(
            f"{_BASE_URL}/fins/summary", params={"code": code},
            headers={"x-api-key": api_key}, timeout=15,
        )
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows).rename(columns={
            "Code": "symbol", "DiscDate": "disc_date", "CurPerType": "period_type",
            "CurFYEn": "fy_end", "Sales": "sales", "OP": "op", "NP": "np", "EPS": "eps",
            "FEPS": "forecast_eps_this", "NxFEPS": "forecast_eps_next",
        })
        df["symbol"] = df["symbol"].map(_code_to_symbol)
        df["disc_date"] = pd.to_datetime(df["disc_date"])
        for c in ["sales", "op", "np", "eps", "forecast_eps_this", "forecast_eps_next"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
        keep = [c for c in cols if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants:{symbol}] fetch_financial_summary 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def fetch_earnings_calendar(symbol: str | None = None) -> pd.DataFrame:
    """決算発表(開示)日一覧を取得する (fins/summaryのDiscDateを代用、過去分のみ)。

    戻り値の列: symbol, announcement_date, fiscal_period
    """
    cols = ["symbol", "announcement_date", "fiscal_period"]
    if symbol is None:
        return pd.DataFrame(columns=cols)
    fin = fetch_financial_summary(symbol)
    if fin.empty:
        return pd.DataFrame(columns=cols)
    out = fin.rename(columns={"disc_date": "announcement_date"}).copy()
    out["fiscal_period"] = out["period_type"].astype(str) + out["fy_end"].astype(str).str.slice(0, 7)
    return out[cols]


def build_earnings_events(symbols: list[str]) -> pd.DataFrame:
    """複数銘柄の財務サマリー(実績/予想EPS)からPEAD用イベントテーブルを構築する。

    戻り値の列: symbol, announcement_date, fiscal_period, actual_eps, forecast_eps, surprise_pct

    surprise_pct は「当該開示の実績EPS」と「直前の開示時点で示されていた予想EPS」の乖離率
    (直前開示の当期予想が空なら来期予想で代替する近似)。開示種別(Q1〜Q4/FY)の厳密な
    対応関係を追跡したものではない点に注意。
    """
    cols = ["symbol", "announcement_date", "fiscal_period", "actual_eps", "forecast_eps", "surprise_pct"]
    if not _api_key():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため build_earnings_events をスキップします")
        return pd.DataFrame(columns=cols)

    records = []
    for symbol in symbols:
        fin = fetch_financial_summary(symbol)
        if fin.empty:
            continue
        fin = fin.sort_values("disc_date").reset_index(drop=True)
        prev_forecast = fin["forecast_eps_this"].shift(1)
        prev_forecast = prev_forecast.fillna(fin["forecast_eps_next"].shift(1))

        merged = pd.DataFrame({
            "symbol": fin["symbol"],
            "announcement_date": fin["disc_date"],
            "fiscal_period": fin["period_type"].astype(str) + fin["fy_end"].astype(str).str.slice(0, 7),
            "actual_eps": fin["eps"],
            "forecast_eps": prev_forecast,
        })
        merged["surprise_pct"] = (
            (merged["actual_eps"] - merged["forecast_eps"]) / merged["forecast_eps"].abs() * 100
        )
        merged.loc[merged["forecast_eps"].isna() | (merged["forecast_eps"] == 0), "surprise_pct"] = None
        records.append(merged)

    if not records:
        return pd.DataFrame(columns=cols)
    df = pd.concat(records, ignore_index=True)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]
