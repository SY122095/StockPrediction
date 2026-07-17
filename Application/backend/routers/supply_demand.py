from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from models.db_models import SupplyDemand
from models.schemas import SupplyDemandOut

router = APIRouter(prefix="/api/v1/supply-demand", tags=["supply-demand"])

_METRICS = ["foreign_net_ratio", "margin_ratio", "short_selling_ratio"]


@router.get("/latest")
def get_latest(market: str = Query("TSE_ALL"), db: Session = Depends(get_db)):
    result = {}
    for metric in _METRICS:
        latest = (
            db.query(SupplyDemand)
            .filter(SupplyDemand.market == market, SupplyDemand.metric_name == metric)
            .order_by(desc(SupplyDemand.date_utc))
            .first()
        )
        if latest:
            result[metric] = {"date_utc": latest.date_utc, "value": latest.value, "source": latest.source}
    return result


@router.get("/history", response_model=list[SupplyDemandOut])
def get_history(
    metric_name: str = Query(..., description="foreign_net_ratio | margin_ratio | short_selling_ratio"),
    market: str = Query("TSE_ALL"),
    days: int = Query(180, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(SupplyDemand)
        .filter(
            SupplyDemand.metric_name == metric_name,
            SupplyDemand.market == market,
            SupplyDemand.date_utc >= cutoff,
        )
        .order_by(SupplyDemand.date_utc)
        .all()
    )
    return rows
