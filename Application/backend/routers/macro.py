from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from models.db_models import MacroSeries
from models.schemas import MacroSeriesOut

router = APIRouter(prefix="/api/v1/macro", tags=["macro"])


@router.get("/series", response_model=list[MacroSeriesOut])
def get_series(
    series_id: str = Query(..., description="例: DGS10, us_cpi, usdjpy"),
    days: int = Query(365, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(MacroSeries)
        .filter(MacroSeries.series_id == series_id, MacroSeries.date_utc >= cutoff)
        .order_by(MacroSeries.date_utc)
        .all()
    )
    return rows


@router.get("/latest")
def get_latest(db: Session = Depends(get_db)):
    """登録済みの全マクロ系列について最新値のスナップショットを返す (ダッシュボード用)。"""
    series_ids = [r[0] for r in db.query(MacroSeries.series_id).distinct().all()]
    result = {}
    for sid in series_ids:
        latest = (
            db.query(MacroSeries)
            .filter(MacroSeries.series_id == sid)
            .order_by(desc(MacroSeries.date_utc))
            .first()
        )
        if latest:
            result[sid] = {"date_utc": latest.date_utc, "value": latest.value, "source": latest.source}
    return result
