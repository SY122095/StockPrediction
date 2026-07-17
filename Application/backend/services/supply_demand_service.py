"""JPX需給データ収集サービス: 投資部門別売買状況・信用取引残高・空売り比率 → SQLite"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from lib.supply_demand_data import (
    fetch_jpx_investor_flows,
    fetch_jpx_margin_balance,
    fetch_jpx_short_selling_ratio,
)
from models.db_models import SupplyDemand


def _upsert_metric(db: Session, df: pd.DataFrame) -> int:
    inserted = 0
    for _, row in df.iterrows():
        if pd.isna(row.get("value")):
            continue
        existing = (
            db.query(SupplyDemand)
            .filter_by(market=row["market"], metric_name=row["metric_name"], date_utc=row["date_utc"])
            .first()
        )
        if existing:
            existing.value = row["value"]
        else:
            db.add(SupplyDemand(
                date_utc=row["date_utc"], market=row["market"],
                metric_name=row["metric_name"], value=row["value"], source="jpx",
            ))
            inserted += 1
    return inserted


def refresh_supply_demand(db: Session) -> dict[str, int]:
    """JPX統計 (投資部門別/信用/空売り) を取得・保存する。ライブ取得失敗時は
    lib/supply_demand_data.py 側でローカル手動配置ファイルへフォールバックする。"""
    result: dict[str, int] = {}
    for name, fetch_fn in (
        ("foreign_net_ratio", fetch_jpx_investor_flows),
        ("margin_ratio", fetch_jpx_margin_balance),
        ("short_selling_ratio", fetch_jpx_short_selling_ratio),
    ):
        try:
            df = fetch_fn()
            result[name] = _upsert_metric(db, df)
        except Exception as e:
            print(f"  WARN [SupplyDemand:{name}] 更新失敗: {e}")
            result[name] = 0
    db.commit()
    print(f"需給データ更新: {result}")
    return result
