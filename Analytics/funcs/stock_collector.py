"""
株式・暗号資産データ収集モジュール (yfinance ベース)

JP株式 : yfinance (.T suffix, 東証)
暗号資産: yfinance (BTC-USD 等)
マクロ  : yfinance (^N225, DX-Y.NYB 等)
"""
from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path
from typing import Sequence

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ---- 銘柄定義 ----

NIKKEI_MAJOR = [
    "7203.T",  # トヨタ自動車
    "6758.T",  # ソニーグループ
    "8306.T",  # 三菱UFJ FG
    "9432.T",  # NTT
    "9984.T",  # ソフトバンクG
    "6861.T",  # キーエンス
    "8316.T",  # 三井住友FG
    "4063.T",  # 信越化学工業
    "6367.T",  # ダイキン工業
    "7974.T",  # 任天堂
    "8035.T",  # 東京エレクトロン
    "6954.T",  # ファナック
    "4519.T",  # 中外製薬
    "9433.T",  # KDDI
    "3382.T",  # セブン&アイ
    "4502.T",  # 武田薬品工業
    "7751.T",  # キヤノン
    "6098.T",  # リクルートHD
    "8766.T",  # 東京海上HD
    "6501.T",  # 日立製作所
    "4568.T",  # 第一三共
    "7267.T",  # 本田技研工業
    "6702.T",  # 富士通
    "6503.T",  # 三菱電機
    "5108.T",  # ブリヂストン
    "8802.T",  # 三菱地所
    "9022.T",  # 東海旅客鉄道
    "2413.T",  # エムスリー
    "2801.T",  # キッコーマン
    "4661.T",  # OLC
]

CRYPTO_MAJOR = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "XRP-USD",
]

MACRO_TICKERS: dict[str, str] = {
    "^N225":    "nikkei225",
    "^DJI":     "dow_jones",
    "DX-Y.NYB": "usd_index",
    "CL=F":     "crude_oil",
    "GC=F":     "gold",
    "^TNX":     "us10y_yield",
    "USDJPY=X": "usdjpy",
    "^VIX":     "vix",
}

# 銘柄名マスタ
SYMBOL_NAMES: dict[str, str] = {
    "7203.T": "トヨタ自動車",
    "6758.T": "ソニーグループ",
    "8306.T": "三菱UFJ FG",
    "9432.T": "NTT",
    "9984.T": "ソフトバンクG",
    "6861.T": "キーエンス",
    "8316.T": "三井住友FG",
    "4063.T": "信越化学工業",
    "6367.T": "ダイキン工業",
    "7974.T": "任天堂",
    "8035.T": "東京エレクトロン",
    "6954.T": "ファナック",
    "4519.T": "中外製薬",
    "9433.T": "KDDI",
    "3382.T": "セブン&アイ",
    "4502.T": "武田薬品工業",
    "7751.T": "キヤノン",
    "6098.T": "リクルートHD",
    "8766.T": "東京海上HD",
    "6501.T": "日立製作所",
    "4568.T": "第一三共",
    "7267.T": "本田技研工業",
    "6702.T": "富士通",
    "6503.T": "三菱電機",
    "5108.T": "ブリヂストン",
    "8802.T": "三菱地所",
    "9022.T": "東海旅客鉄道",
    "2413.T": "エムスリー",
    "2801.T": "キッコーマン",
    "4661.T": "OLC",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "BNB-USD": "BNB",
    "XRP-USD": "XRP",
}


def _today() -> str:
    return datetime.today().strftime("%Y-%m-%d")


def _long_format(raw: pd.DataFrame, symbols: list[str], asset_class: str) -> pd.DataFrame:
    """yfinance multi-index → long format"""
    records = []
    for sym in symbols:
        try:
            if len(symbols) == 1:
                df_s = raw.copy()
            else:
                df_s = raw.xs(sym, level=1, axis=1).copy()
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
    df = df[["symbol", "asset_class", "date", "open", "high", "low", "close", "volume"]]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def download_equity(
    symbols: Sequence[str] | None = None,
    start: str = "2020-01-01",
    end: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """JP株式 OHLCV を取得"""
    if symbols is None:
        symbols = NIKKEI_MAJOR
    symbols = list(symbols)
    if end is None:
        end = _today()

    print(f"[株式] {len(symbols)} 銘柄 ダウンロード中 ({start} → {end})")
    raw = yf.download(symbols, start=start, end=end, interval=interval,
                      auto_adjust=True, progress=True)
    df = _long_format(raw, symbols, "equity_jp")
    print(f"  完了: {len(df):,} 行")
    return df


def download_crypto(
    symbols: Sequence[str] | None = None,
    start: str = "2020-01-01",
    end: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """暗号資産 OHLCV を取得"""
    if symbols is None:
        symbols = CRYPTO_MAJOR
    symbols = list(symbols)
    if end is None:
        end = _today()

    print(f"[暗号資産] {len(symbols)} シンボル ダウンロード中 ({start} → {end})")
    raw = yf.download(symbols, start=start, end=end, interval=interval,
                      auto_adjust=True, progress=True)
    df = _long_format(raw, symbols, "crypto")
    print(f"  完了: {len(df):,} 行")
    return df


def download_macro(
    tickers: dict[str, str] | None = None,
    start: str = "2020-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """マクロ指標を取得してワイド形式で返す"""
    if tickers is None:
        tickers = MACRO_TICKERS
    if end is None:
        end = _today()

    print(f"[マクロ] {len(tickers)} 指標 ダウンロード中 ({start} → {end})")
    records = []
    for ticker, name in tickers.items():
        try:
            s = yf.download(ticker, start=start, end=end, auto_adjust=True,
                            progress=False)["Close"]
            s.name = name
            records.append(s)
        except Exception as e:
            print(f"  WARN [{ticker}]: {e}")

    if not records:
        return pd.DataFrame()

    df = pd.concat(records, axis=1)
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    df = df.set_index("date").ffill().reset_index()
    print(f"  完了: {len(df):,} 行 × {df.shape[1] - 1} 指標")
    return df
