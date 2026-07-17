"""決算イベントデータ収集サービス: J-Quants → SQLite (PEAD特徴量用)"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from lib.jquants_data import build_earnings_events
from models.db_models import EarningsEvent, Instrument


def refresh_earnings(db: Session, asset_class: str = "equity_jp") -> int:
    """登録済み銘柄について J-Quants から決算発表日・EPSサプライズを取得・保存する。
    JQUANTS_API_KEY が未設定/ダミーの場合は 0 件のまま静かにスキップされる。"""
    symbols = [r.symbol for r in db.query(Instrument).filter_by(asset_class=asset_class).all()]
    if not symbols:
        print("銘柄が登録されていません。先にデータ更新を実行してください。")
        return 0

    df = build_earnings_events(symbols)
    if df.empty:
        print("決算イベント更新: 0 件 (J-Quants未設定または取得失敗)")
        return 0

    df["announcement_date"] = pd.to_datetime(df["announcement_date"], errors="coerce")
    df = df.dropna(subset=["announcement_date"])

    inserted = 0
    for _, row in df.iterrows():
        existing = (
            db.query(EarningsEvent)
            .filter_by(symbol=row["symbol"], announcement_date=row["announcement_date"])
            .first()
        )
        if existing:
            existing.fiscal_period = row.get("fiscal_period")
            existing.actual_eps = row.get("actual_eps")
            existing.forecast_eps = row.get("forecast_eps")
            existing.surprise_pct = row.get("surprise_pct")
        else:
            db.add(EarningsEvent(
                symbol=row["symbol"],
                announcement_date=row["announcement_date"],
                fiscal_period=row.get("fiscal_period"),
                actual_eps=row.get("actual_eps"),
                forecast_eps=row.get("forecast_eps"),
                surprise_pct=row.get("surprise_pct"),
                source="jquants",
            ))
            inserted += 1
    db.commit()
    print(f"決算イベント更新: {inserted} 件")
    return inserted
