from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InstrumentOut(BaseModel):
    symbol: str
    name: Optional[str]
    asset_class: str
    exchange: Optional[str]

    class Config:
        from_attributes = True


class OHLCVOut(BaseModel):
    symbol: str
    date_utc: datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]

    class Config:
        from_attributes = True


class StockSummaryOut(BaseModel):
    symbol: str
    name: Optional[str]
    latest_date: Optional[datetime]
    latest_close: Optional[float]
    ret_1d: Optional[float]
    ret_5d: Optional[float]


class PredictionOut(BaseModel):
    rank: int
    symbol: str
    name: Optional[str]
    predicted_return: float
    predicted_return_pct: float
    model_version: Optional[str]

    class Config:
        from_attributes = True


class RankingOut(BaseModel):
    as_of_date: Optional[datetime]
    asset_class: str
    target: str
    rankings: list[PredictionOut]


class TrainResultOut(BaseModel):
    status: str
    asset_class: str
    target: str
    mean_rank_ic: float
    n_features: int
    n_samples: int
    model_version: str


class MacroSeriesOut(BaseModel):
    series_id: str
    date_utc: datetime
    value: Optional[float]
    source: Optional[str]

    class Config:
        from_attributes = True


class SentimentIndexOut(BaseModel):
    date_utc: datetime
    index_name: str
    asset_class: Optional[str]
    value: Optional[float]
    source: Optional[str]

    class Config:
        from_attributes = True


class EarningsEventOut(BaseModel):
    symbol: str
    announcement_date: datetime
    fiscal_period: Optional[str]
    actual_eps: Optional[float]
    forecast_eps: Optional[float]
    surprise_pct: Optional[float]

    class Config:
        from_attributes = True


class SupplyDemandOut(BaseModel):
    date_utc: datetime
    market: str
    metric_name: str
    value: Optional[float]
    source: Optional[str]

    class Config:
        from_attributes = True


class AdminStatusOut(BaseModel):
    fred_configured: bool
    jquants_configured: bool


class ScreeningScoreOut(BaseModel):
    rank: Optional[int]
    symbol: str
    name: Optional[str]
    market_segment: Optional[str]
    value: Optional[float]

    class Config:
        from_attributes = True


class ScreeningRankingOut(BaseModel):
    as_of_date: Optional[datetime]
    score_type: str
    rankings: list[ScreeningScoreOut]
