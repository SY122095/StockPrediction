"""データ収集サービス: yfinance / J-Quants → SQLite"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from lib.jquants_data import fetch_daily_quotes_range
from lib.stock_data import (
    SYMBOL_NAMES,
    NIKKEI_MAJOR,
    CRYPTO_MAJOR,
    download_equity,
    download_crypto,
)
from models.db_models import Instrument, OHLCV

_BULK_CHUNK_SIZE = 500


def bulk_upsert_ohlcv(db: Session, df: pd.DataFrame) -> int:
    """SQLiteのON CONFLICTを使った高速バルクupsert (広いユニバース向け、行ごとのSELECTを避ける)。"""
    if df is None or df.empty:
        return 0

    df = df.dropna(subset=["symbol", "date"]).copy()
    df = df.rename(columns={"date": "date_utc"})
    keep = ["symbol", "date_utc", "open", "high", "low", "close", "volume"]
    for c in keep:
        if c not in df.columns:
            df[c] = None
    records = df[keep].to_dict("records")

    table = OHLCV.__table__
    total = 0
    for i in range(0, len(records), _BULK_CHUNK_SIZE):
        chunk = records[i:i + _BULK_CHUNK_SIZE]
        stmt = sqlite_insert(table).values(chunk)
        update_cols = {c: stmt.excluded[c] for c in ["open", "high", "low", "close", "volume"]}
        stmt = stmt.on_conflict_do_update(index_elements=["symbol", "date_utc"], set_=update_cols)
        db.execute(stmt)
        total += len(chunk)
    db.commit()
    return total


def _instrument_asset_class(symbol: str) -> tuple[str, str]:
    if symbol in NIKKEI_MAJOR:
        return "equity_jp", "TSE"
    if symbol in CRYPTO_MAJOR:
        return "crypto", "Binance"
    return "unknown", "unknown"


def upsert_instruments(db: Session, symbols: list[str]) -> None:
    """コア層(yfinance厳選銘柄)の Instrument を登録する。is_core=1 を必ず立てる
    (広いユニバース経由で先に is_core=0 のまま作成済みの行があっても、ここで昇格させる)。"""
    for sym in symbols:
        existing = db.query(Instrument).filter_by(symbol=sym).first()
        if existing:
            existing.is_core = 1
        else:
            ac, exch = _instrument_asset_class(sym)
            db.add(Instrument(
                symbol=sym,
                name=SYMBOL_NAMES.get(sym, sym),
                asset_class=ac,
                exchange=exch,
                is_core=1,
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


def refresh_equity_broad(db: Session, start: str = "2024-05-01") -> dict:
    """広いユニバース(J-Quants全上場銘柄)のOHLCVを日付範囲一括取得しupsertする。
    コア30銘柄向けの refresh_equity (yfinance) とは完全に独立しており、既存の学習/予測
    パイプラインには影響しない。未登録シンボルは最小限の Instrument 行を自動作成する
    (詳細な市場区分等は services.universe_service.refresh_universe で別途補完される)。"""
    df = fetch_daily_quotes_range(start=start, end=pd.Timestamp.utcnow().strftime("%Y-%m-%d"))
    if df.empty:
        return {"instruments_seeded": 0, "ohlcv_upserted": 0}

    symbols = df["symbol"].unique().tolist()
    existing = {s for (s,) in db.query(Instrument.symbol).filter(Instrument.symbol.in_(symbols)).all()}
    missing = [s for s in symbols if s not in existing]
    for sym in missing:
        db.add(Instrument(symbol=sym, name=SYMBOL_NAMES.get(sym, sym), asset_class="equity_jp", exchange="TSE"))
    db.commit()

    n = bulk_upsert_ohlcv(db, df)
    print(f"[広いユニバース] 株式: {len(symbols)} 銘柄 / OHLCV {n} 件 upsert (新規Instrument {len(missing)} 件)")
    return {"instruments_seeded": len(missing), "ohlcv_upserted": n}


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
