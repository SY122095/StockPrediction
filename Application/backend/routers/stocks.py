from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from lib.stock_data import SYMBOL_NAMES
from models.db_models import OHLCV, Instrument
from models.schemas import InstrumentOut, OHLCVOut, StockSummaryOut

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


@router.get("", response_model=list[InstrumentOut])
def list_instruments(
    asset_class: Optional[str] = Query(None, description="equity_jp | crypto"),
    db: Session = Depends(get_db),
):
    q = db.query(Instrument)
    if asset_class:
        q = q.filter(Instrument.asset_class == asset_class)
    return q.order_by(Instrument.symbol).all()


@router.get("/{symbol}/ohlcv", response_model=list[OHLCVOut])
def get_ohlcv(
    symbol: str,
    days: int = Query(90, ge=1, le=1825),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol, OHLCV.date_utc >= cutoff)
        .order_by(OHLCV.date_utc)
        .all()
    )
    if not rows:
        raise HTTPException(404, f"データが見つかりません: {symbol}")
    return rows


@router.get("/{symbol}/summary", response_model=StockSummaryOut)
def get_summary(symbol: str, db: Session = Depends(get_db)):
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol)
        .order_by(desc(OHLCV.date_utc))
        .limit(25)
        .all()
    )
    if not rows:
        raise HTTPException(404, f"データが見つかりません: {symbol}")

    latest = rows[0]
    ret_1d = (
        (rows[0].close - rows[1].close) / rows[1].close if len(rows) >= 2 and rows[1].close else None
    )
    ret_5d = (
        (rows[0].close - rows[5].close) / rows[5].close if len(rows) >= 6 and rows[5].close else None
    )
    return StockSummaryOut(
        symbol=symbol,
        name=SYMBOL_NAMES.get(symbol),
        latest_date=latest.date_utc,
        latest_close=latest.close,
        ret_1d=ret_1d,
        ret_5d=ret_5d,
    )
