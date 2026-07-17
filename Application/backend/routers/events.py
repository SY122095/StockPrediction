from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc
from sqlalchemy.orm import Session

from core.database import get_db
from lib.stock_data import SYMBOL_NAMES
from models.db_models import EarningsEvent, Instrument
from models.schemas import EarningsEventOut

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("/earnings", response_model=list[EarningsEventOut])
def get_earnings(
    symbol: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.symbol == symbol)
        .order_by(EarningsEvent.announcement_date.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.get("/earnings/upcoming")
def get_upcoming_earnings(
    asset_class: str = Query("equity_jp"),
    within_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """今後 N 日以内に決算発表を控えている銘柄一覧 (推奨エンジンの除外フィルタ用途)。"""
    symbols = [r.symbol for r in db.query(Instrument).filter_by(asset_class=asset_class).all()]
    if not symbols:
        return []

    now = datetime.utcnow()
    rows = (
        db.query(EarningsEvent)
        .filter(
            EarningsEvent.symbol.in_(symbols),
            EarningsEvent.announcement_date >= now,
        )
        .order_by(asc(EarningsEvent.announcement_date))
        .all()
    )
    return [
        {
            "symbol": r.symbol,
            "name": SYMBOL_NAMES.get(r.symbol),
            "announcement_date": r.announcement_date,
            "days_until": (r.announcement_date - now).days,
        }
        for r in rows
        if (r.announcement_date - now).days <= within_days
    ]
