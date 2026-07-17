from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.database import get_db
from lib.stock_data import SYMBOL_NAMES
from models.db_models import Prediction
from models.schemas import RankingOut, PredictionOut

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.get("/ranking", response_model=RankingOut)
def get_ranking(
    asset_class: str = Query("equity_jp"),
    target: str = Query("fwd_ret_5d"),
    top_n: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    latest_date_row = (
        db.query(Prediction.date_utc)
        .filter(Prediction.target == target)
        .order_by(desc(Prediction.date_utc))
        .first()
    )
    if not latest_date_row:
        return RankingOut(as_of_date=None, asset_class=asset_class, target=target, rankings=[])

    rows = (
        db.query(Prediction)
        .filter(Prediction.date_utc == latest_date_row[0], Prediction.target == target)
        .order_by(Prediction.rank)
        .limit(top_n)
        .all()
    )
    rankings = [
        PredictionOut(
            rank=r.rank,
            symbol=r.symbol,
            name=SYMBOL_NAMES.get(r.symbol),
            predicted_return=r.predicted_return,
            predicted_return_pct=round(r.predicted_return * 100, 2),
            model_version=r.model_version,
        )
        for r in rows
    ]
    return RankingOut(
        as_of_date=latest_date_row[0],
        asset_class=asset_class,
        target=target,
        rankings=rankings,
    )


@router.get("/{symbol}")
def get_prediction_history(
    symbol: str,
    target: str = Query("fwd_ret_5d"),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Prediction)
        .filter(Prediction.symbol == symbol, Prediction.target == target)
        .order_by(desc(Prediction.date_utc))
        .limit(limit)
        .all()
    )
    return [
        {"date": r.date_utc, "predicted_return": r.predicted_return, "rank": r.rank}
        for r in rows
    ]
