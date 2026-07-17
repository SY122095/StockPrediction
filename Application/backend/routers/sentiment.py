from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from models.db_models import SentimentIndex
from models.schemas import SentimentIndexOut

router = APIRouter(prefix="/api/v1/sentiment", tags=["sentiment"])


@router.get("/latest")
def get_latest(
    asset_class: Optional[str] = Query(None, description="equity_jp | crypto"),
    db: Session = Depends(get_db),
):
    """センチメント指標の最新値。equity_jp は vix、crypto は fear_greed を返す。"""
    index_names = ["vix"] if asset_class == "equity_jp" else (
        ["fear_greed"] if asset_class == "crypto" else ["vix", "fear_greed"]
    )
    result = {}
    for name in index_names:
        latest = (
            db.query(SentimentIndex)
            .filter(SentimentIndex.index_name == name)
            .order_by(desc(SentimentIndex.date_utc))
            .first()
        )
        if latest:
            result[name] = {"date_utc": latest.date_utc, "value": latest.value, "source": latest.source}
    return result


@router.get("/history", response_model=list[SentimentIndexOut])
def get_history(
    index_name: str = Query(..., description="vix | fear_greed"),
    days: int = Query(180, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(SentimentIndex)
        .filter(SentimentIndex.index_name == index_name, SentimentIndex.date_utc >= cutoff)
        .order_by(SentimentIndex.date_utc)
        .all()
    )
    return rows
