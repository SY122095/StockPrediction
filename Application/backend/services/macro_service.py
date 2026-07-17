"""マクロ・VIXデータ収集サービス: FRED + yfinance → SQLite"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from lib.fred_data import download_macro_fred
from lib.sentiment_data import compute_vix_sentiment
from lib.stock_data import download_macro
from models.db_models import MacroSeries, SentimentIndex


def _upsert_macro_series(db: Session, series_id: str, df: pd.DataFrame, source: str) -> int:
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row["value"]):
            continue
        existing = db.query(MacroSeries).filter_by(series_id=series_id, date_utc=row["date"]).first()
        if existing:
            existing.value = row["value"]
            existing.source = source
        else:
            db.add(MacroSeries(series_id=series_id, date_utc=row["date"], value=row["value"], source=source))
            inserted += 1
    return inserted


def _upsert_sentiment(db: Session, index_name: str, asset_class: str, df: pd.DataFrame, value_col: str, source: str) -> int:
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row[value_col]):
            continue
        existing = db.query(SentimentIndex).filter_by(index_name=index_name, date_utc=row["date"]).first()
        if existing:
            existing.value = row[value_col]
            existing.asset_class = asset_class
            existing.source = source
        else:
            db.add(SentimentIndex(
                date_utc=row["date"], index_name=index_name, asset_class=asset_class,
                value=row[value_col], source=source,
            ))
            inserted += 1
    return inserted


def refresh_macro(db: Session, start: str = "2022-01-01") -> dict[str, int]:
    """FRED マクロ系列 + yfinance マクロ(VIX含む) を取得し MacroSeries / SentimentIndex へ保存する。
    FRED_API_KEY が未設定/ダミーの場合は fred 側が 0 件のまま静かにスキップされる。"""
    result = {"fred": 0, "yfinance_macro": 0, "vix": 0}

    df_fred = download_macro_fred(start=start)
    for col in [c for c in df_fred.columns if c != "date"]:
        result["fred"] += _upsert_macro_series(
            db, col, df_fred[["date", col]].rename(columns={col: "value"}), source="fred"
        )
    db.commit()

    df_yf_macro = download_macro(start=start)
    if not df_yf_macro.empty:
        for col in [c for c in df_yf_macro.columns if c != "date"]:
            result["yfinance_macro"] += _upsert_macro_series(
                db, col, df_yf_macro[["date", col]].rename(columns={col: "value"}), source="yfinance"
            )
        if "vix" in df_yf_macro.columns:
            df_vix = compute_vix_sentiment(df_yf_macro)
            if not df_vix.empty:
                result["vix"] = _upsert_sentiment(db, "vix", "equity_jp", df_vix, value_col="vix", source="yfinance")
    db.commit()

    print(f"マクロデータ更新: FRED {result['fred']} 件 / yfinance {result['yfinance_macro']} 件 / VIX {result['vix']} 件")
    return result
