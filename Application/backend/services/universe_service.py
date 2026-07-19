"""銘柄ユニバース管理サービス: J-Quants上場銘柄マスタ → Instrument テーブル"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from lib.jquants_data import fetch_listed_instruments
from models.db_models import Instrument

_BULK_CHUNK_SIZE = 500


def refresh_universe(db: Session) -> dict:
    """東証上場銘柄マスタ(J-Quants)を取得し、Instrument テーブルへ反映する。
    取得できた銘柄一覧に含まれない既存の equity_jp レコードは is_active=0 とする
    (削除はしない。OHLCV/Prediction等の既存参照を壊さないため)。"""
    df = fetch_listed_instruments()
    if df.empty:
        print("  WARN [universe] 銘柄マスタが空のため refresh_universe をスキップします")
        return {"upserted": 0, "deactivated": 0}

    df = df.copy()
    df["asset_class"] = "equity_jp"
    df["exchange"] = "TSE"
    df["is_active"] = 1

    records = df[[
        "symbol", "name", "asset_class", "exchange",
        "market_segment", "sector33_code", "sector33_name", "is_active",
    ]].to_dict("records")

    table = Instrument.__table__
    for i in range(0, len(records), _BULK_CHUNK_SIZE):
        chunk = records[i:i + _BULK_CHUNK_SIZE]
        stmt = sqlite_insert(table).values(chunk)
        update_cols = {
            c: stmt.excluded[c]
            for c in ["name", "asset_class", "exchange", "market_segment", "sector33_code", "sector33_name", "is_active"]
        }
        stmt = stmt.on_conflict_do_update(index_elements=["symbol"], set_=update_cols)
        db.execute(stmt)
    db.commit()

    live_symbols = set(df["symbol"])
    stale = (
        db.query(Instrument)
        .filter(Instrument.asset_class == "equity_jp", Instrument.is_active == 1)
        .filter(~Instrument.symbol.in_(live_symbols))
        .all()
    )
    for inst in stale:
        inst.is_active = 0
    db.commit()

    print(f"[ユニバース] {len(records)} 銘柄 upsert / {len(stale)} 銘柄を非アクティブ化")
    return {"upserted": len(records), "deactivated": len(stale)}
