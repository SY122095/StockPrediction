from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.sql import func

from core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id         = Column(Integer, primary_key=True)
    symbol     = Column(String(20), unique=True, nullable=False)
    name       = Column(String(100))
    asset_class = Column(String(20))   # equity_jp | crypto
    exchange   = Column(String(20))


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id       = Column(Integer, primary_key=True)
    symbol   = Column(String(20), nullable=False)
    date_utc = Column(DateTime, nullable=False)
    open     = Column(Float)
    high     = Column(Float)
    low      = Column(Float)
    close    = Column(Float)
    volume   = Column(Float)

    __table_args__ = (
        UniqueConstraint("symbol", "date_utc", name="uq_ohlcv_symbol_date"),
        Index("ix_ohlcv_symbol_date", "symbol", "date_utc"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id               = Column(Integer, primary_key=True)
    symbol           = Column(String(20), nullable=False)
    date_utc         = Column(DateTime, nullable=False)
    target           = Column(String(20))       # fwd_ret_5d など
    predicted_return = Column(Float)
    rank             = Column(Integer)
    model_version    = Column(String(50))
    created_at       = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "date_utc", "target", name="uq_pred_symbol_date_target"),
        Index("ix_predictions_date", "date_utc"),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id           = Column(Integer, primary_key=True)
    version_id   = Column(String(50), unique=True)
    asset_class  = Column(String(20))
    target       = Column(String(20))
    trained_at   = Column(DateTime, server_default=func.now())
    mean_rank_ic = Column(Float)
    n_features   = Column(Integer)
    n_samples    = Column(Integer)
    is_active    = Column(Integer, default=1)


class MacroSeries(Base):
    """FRED / yfinance 由来のマクロ経済系列 (金利・CPI・USDJPY等)"""
    __tablename__ = "macro_series"

    id        = Column(Integer, primary_key=True)
    series_id = Column(String(50), nullable=False)   # 例: DGS10, us_cpi, vix
    date_utc  = Column(DateTime, nullable=False)
    value     = Column(Float)
    source    = Column(String(20))                    # fred | yfinance

    __table_args__ = (
        UniqueConstraint("series_id", "date_utc", name="uq_macro_series_date"),
        Index("ix_macro_series_id_date", "series_id", "date_utc"),
    )


class SentimentIndex(Base):
    """VIX・Fear&Greed等のセンチメント指標"""
    __tablename__ = "sentiment_index"

    id          = Column(Integer, primary_key=True)
    date_utc    = Column(DateTime, nullable=False)
    index_name  = Column(String(30), nullable=False)  # vix | fear_greed
    asset_class = Column(String(20))                  # equity_jp | crypto
    value       = Column(Float)
    source      = Column(String(30))

    __table_args__ = (
        UniqueConstraint("index_name", "date_utc", name="uq_sentiment_name_date"),
        Index("ix_sentiment_name_date", "index_name", "date_utc"),
    )


class EarningsEvent(Base):
    """決算発表イベント (PEAD特徴量用)"""
    __tablename__ = "earnings_events"

    id                = Column(Integer, primary_key=True)
    symbol            = Column(String(20), nullable=False)
    announcement_date = Column(DateTime, nullable=False)
    fiscal_period     = Column(String(20))
    actual_eps        = Column(Float)
    forecast_eps      = Column(Float)
    surprise_pct      = Column(Float)
    source            = Column(String(20), default="jquants")

    __table_args__ = (
        UniqueConstraint("symbol", "announcement_date", name="uq_earnings_symbol_date"),
        Index("ix_earnings_symbol_date", "symbol", "announcement_date"),
    )


class SupplyDemand(Base):
    """JPX需給統計 (投資部門別売買状況・信用取引残高・空売り比率, 市場全体集計)"""
    __tablename__ = "supply_demand"

    id          = Column(Integer, primary_key=True)
    date_utc    = Column(DateTime, nullable=False)
    market      = Column(String(20), nullable=False)   # 例: TSE_ALL
    metric_name = Column(String(30), nullable=False)    # foreign_net_ratio | margin_ratio | short_selling_ratio
    value       = Column(Float)
    source      = Column(String(20), default="jpx")

    __table_args__ = (
        UniqueConstraint("market", "metric_name", "date_utc", name="uq_supply_demand_key"),
        Index("ix_supply_demand_metric_date", "metric_name", "date_utc"),
    )
