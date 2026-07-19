from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from models.db_models import Instrument, ScreeningScore
from models.schemas import ScreeningRankingOut, ScreeningScoreOut

router = APIRouter(prefix="/api/v1/screening", tags=["screening"])


@router.get("/ranking", response_model=ScreeningRankingOut)
def get_screening_ranking(
    score_type: str = Query("composite", description="volume_spike | momentum_5d | breakout_20d | composite"),
    market_segment: Optional[str] = Query(None, description="Prime | Standard | Growth"),
    top_n: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    latest_date_row = (
        db.query(ScreeningScore.date_utc)
        .filter(ScreeningScore.score_type == score_type)
        .order_by(desc(ScreeningScore.date_utc))
        .first()
    )
    if not latest_date_row:
        return ScreeningRankingOut(as_of_date=None, score_type=score_type, rankings=[])

    q = (
        db.query(ScreeningScore, Instrument)
        .join(Instrument, ScreeningScore.symbol == Instrument.symbol)
        .filter(ScreeningScore.date_utc == latest_date_row[0], ScreeningScore.score_type == score_type)
    )
    if market_segment:
        q = q.filter(Instrument.market_segment == market_segment)

    rows = q.order_by(ScreeningScore.rank).limit(top_n).all()
    rankings = [
        ScreeningScoreOut(
            rank=score.rank, symbol=score.symbol, name=inst.name,
            market_segment=inst.market_segment, value=score.value,
        )
        for score, inst in rows
    ]
    return ScreeningRankingOut(as_of_date=latest_date_row[0], score_type=score_type, rankings=rankings)
