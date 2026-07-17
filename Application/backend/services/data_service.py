"""データ収集サービス: yfinance → SQLite"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from lib.stock_data import (
    SYMBOL_NAMES,
    NIKKEI_MAJOR,
    CRYPTO_MAJOR,
    download_equity,
    download_crypto,
)
from models.db_models import Instrument, OHLCV


def _instrument_asset_class(symbol: str) -> tuple[str, str]:
    if symbol in NIKKEI_MAJOR:
        return "equity_jp", "TSE"
    if symbol in CRYPTO_MAJOR:
        return "crypto", "Binance"
    return "unknown", "unknown"


def upsert_instruments(db: Session, symbols: list[str]) -> None:
    for sym in symbols:
        if not db.query(Instrument).filter_by(symbol=sym).first():
            ac, exch = _instrument_asset_class(sym)
            db.add(Instrument(
                symbol=sym,
                name=SYMBOL_NAMES.get(sym, sym),
                asset_class=ac,
                exchange=exch,
            ))
    db.commit()


def upsert_ohlcv(db: Session, df: pd.DataFrame) -> int:
    inserted = 0
    for _, row in df.iterrows():
        exists = (
            db.query(OHLCV)
            .filter_by(symbol=row["symbol"], date_utc=row["date"])
            .first()
        )
        if not exists:
            db.add(OHLCV(
                symbol=row["symbol"],
                date_utc=row["date"],
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=row.get("volume"),
            ))
            inserted += 1
    db.commit()
    return inserted


def refresh_equity(db: Session, start: str = "2022-01-01") -> int:
    df = download_equity(start=start)
    if df.empty:
        return 0
    upsert_instruments(db, df["symbol"].unique().tolist())
    n = upsert_ohlcv(db, df)
    print(f"株式: {n} 件挿入")
    return n


def refresh_crypto(db: Session, start: str = "2022-01-01") -> int:
    df = download_crypto(start=start)
    if df.empty:
        return 0
    upsert_instruments(db, df["symbol"].unique().tolist())
    n = upsert_ohlcv(db, df)
    print(f"暗号資産: {n} 件挿入")
    return n


def refresh_all(db: Session, start: str = "2022-01-01") -> dict:
    """OHLCV(equity/crypto)に加え、マクロ・センチメント・決算イベント・需給データも更新する。
    各ソースは独立して失敗を捕捉するため、1つのAPIキー未設定/取得失敗が全体を止めない。"""
    print("=== データ更新開始 ===")
    result: dict = {
        "equity_jp": refresh_equity(db, start),
        "crypto":    refresh_crypto(db, start),
    }

    from services.event_service import refresh_earnings
    from services.macro_service import refresh_macro
    from services.sentiment_service import refresh_sentiment
    from services.supply_demand_service import refresh_supply_demand

    for key, fn, kwargs in (
        ("macro", refresh_macro, {"start": start}),
        ("sentiment", refresh_sentiment, {}),
        ("earnings", refresh_earnings, {}),
        ("supply_demand", refresh_supply_demand, {}),
    ):
        try:
            result[key] = fn(db, **kwargs)
        except Exception as e:
            print(f"  WARN [{key}] 更新失敗: {e}")
            result[key] = {"error": str(e)}

    print("=== データ更新完了 ===")
    return result
