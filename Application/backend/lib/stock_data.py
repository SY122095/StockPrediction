"""yfinance ベースのデータ取得 (Application 内部用)"""
from __future__ import annotations

import warnings
from datetime import datetime
from typing import Sequence

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# NIKKEI_MAJOR は「コア層」専用の厳選銘柄リスト (LightGBM学習/予測パイプライン向け)。
# 広いユニバース(急騰候補スクリーニング)は lib/jquants_data.py の fetch_listed_instruments()
# で東証全上場銘柄を動的取得する (services/universe_service.py 参照)。
NIKKEI_MAJOR = [
    "7203.T", "6758.T", "8306.T", "9432.T", "9984.T",
    "6861.T", "8316.T", "4063.T", "6367.T", "7974.T",
    "8035.T", "6954.T", "4519.T", "9433.T", "3382.T",
    "4502.T", "7751.T", "6098.T", "8766.T", "6501.T",
    "4568.T", "7267.T", "6702.T", "6503.T", "5108.T",
]

CRYPTO_MAJOR = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]

MACRO_TICKERS: dict[str, str] = {
    "^N225":    "nikkei225",
    "DX-Y.NYB": "usd_index",
    "CL=F":     "crude_oil",
    "GC=F":     "gold",
    "^TNX":     "us10y_yield",
    "USDJPY=X": "usdjpy",
    "^VIX":     "vix",
}

SYMBOL_NAMES: dict[str, str] = {
    "7203.T": "トヨタ自動車",    "6758.T": "ソニーグループ",
    "8306.T": "三菱UFJ FG",     "9432.T": "NTT",
    "9984.T": "ソフトバンクG",   "6861.T": "キーエンス",
    "8316.T": "三井住友FG",     "4063.T": "信越化学工業",
    "6367.T": "ダイキン工業",    "7974.T": "任天堂",
    "8035.T": "東京エレクトロン","6954.T": "ファナック",
    "4519.T": "中外製薬",       "9433.T": "KDDI",
    "3382.T": "セブン&アイ",    "4502.T": "武田薬品工業",
    "7751.T": "キヤノン",       "6098.T": "リクルートHD",
    "8766.T": "東京海上HD",     "6501.T": "日立製作所",
    "4568.T": "第一三共",       "7267.T": "本田技研工業",
    "6702.T": "富士通",         "6503.T": "三菱電機",
    "5108.T": "ブリヂストン",
    "BTC-USD": "Bitcoin",       "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",        "BNB-USD": "BNB",
    "XRP-USD": "XRP",
}


def _today() -> str:
    return datetime.today().strftime("%Y-%m-%d")


def _to_long(raw: pd.DataFrame, symbols: list[str], asset_class: str) -> pd.DataFrame:
    records = []
    for sym in symbols:
        try:
            df_s = raw.xs(sym, level=1, axis=1).copy() if len(symbols) > 1 else raw.copy()
            df_s = df_s.dropna(subset=["Close"])
            if df_s.empty:
                continue
            df_s["symbol"] = sym
            df_s.index.name = "date"
            df_s = df_s.reset_index()
            df_s.columns = [c.lower() if c != "date" else c for c in df_s.columns]
            records.append(df_s)
        except Exception as e:
            print(f"  WARN [{sym}]: {e}")
    if not records:
        return pd.DataFrame()
    df = pd.concat(records, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df["asset_class"] = asset_class
    cols = ["symbol", "asset_class", "date", "open", "high", "low", "close", "volume"]
    return df[cols].sort_values(["symbol", "date"]).reset_index(drop=True)


def download_equity(
    symbols: list[str] | None = None,
    start: str = "2021-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    if symbols is None:
        symbols = NIKKEI_MAJOR
    if end is None:
        end = _today()
    print(f"[株式] {len(symbols)} 銘柄 ({start}~{end})")
    raw = yf.download(symbols, start=start, end=end, auto_adjust=True, progress=True)
    df = _to_long(raw, symbols, "equity_jp")
    print(f"  → {len(df):,} 行")
    return df


def download_crypto(
    symbols: list[str] | None = None,
    start: str = "2021-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    if symbols is None:
        symbols = CRYPTO_MAJOR
    if end is None:
        end = _today()
    print(f"[暗号資産] {len(symbols)} シンボル ({start}~{end})")
    raw = yf.download(symbols, start=start, end=end, auto_adjust=True, progress=True)
    df = _to_long(raw, symbols, "crypto")
    print(f"  → {len(df):,} 行")
    return df


def download_macro(start: str = "2021-01-01", end: str | None = None) -> pd.DataFrame:
    if end is None:
        end = _today()
    records = []
    for ticker, name in MACRO_TICKERS.items():
        try:
            s = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)["Close"]
            s.name = name
            records.append(s)
        except Exception:
            pass
    if not records:
        return pd.DataFrame(columns=["date"])
    df = pd.concat(records, axis=1).reset_index()
    df = df.rename(columns={df.columns[0]: "date"})
    if df.empty:
        return pd.DataFrame(columns=["date"] + list(df.columns[1:]))
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").set_index("date").ffill().reset_index()
