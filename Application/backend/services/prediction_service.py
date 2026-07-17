"""予測サービス: DB の OHLCV → 特徴量 → LightGBM 学習/推論 → 予測保存"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.config import settings
from lib.features import build_features
from lib.predictor import (
    DEFAULT_PARAMS,
    ensemble_predict,
    load_model,
    rank_ic,
    save_model,
    walkforward_train,
)
from models.db_models import (
    EarningsEvent,
    Instrument,
    MacroSeries,
    ModelVersion,
    OHLCV,
    Prediction,
    SentimentIndex,
    SupplyDemand,
)

# 学習に使う特徴量 (Forward Return は除外)
# 技術指標 (常時利用可能) + 追加ソース由来 (APIキー未設定時は build_features 側で
# 生成されず、下の `available = [c for c in FEATURE_COLS if c in df_feat.columns]` に
# より自動的に除外されるため後方互換)
FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_20d",
    "logret_1d", "logret_5d",
    "sma_5", "sma_10", "sma_20", "sma_60",
    "ema_5", "ema_20",
    "price_sma5_ratio", "price_sma20_ratio", "price_sma60_ratio",
    "rsi_14", "rsi_28",
    "macd", "macd_signal", "macd_hist",
    "bb_pct", "bb_width",
    "vol_change", "vol_ratio", "turnover_sma5",
    "vol_5d", "vol_20d",
    "ret_1d_rank", "ret_5d_rank", "rsi_14_rank", "vol_ratio_rank",
    # ---- マクロ (FRED, 1日ラグ済み) ----
    "fed_funds_rate", "us10y_yield", "us2y_yield", "us_yield_spread",
    "us_cpi", "us_unemployment", "fed_funds_rate_chg1d", "us10y_yield_chg1d",
    # ---- センチメント ----
    "vix", "vix_chg1d", "vix_zscore", "fear_greed_value",
    # ---- イベント (PEAD) ----
    "days_to_next_earnings", "days_since_last_earnings", "earnings_surprise_pct",
    # ---- 需給 (JPX) ----
    "foreign_net_ratio", "foreign_net_ratio_zscore",
    "margin_ratio", "margin_ratio_zscore",
    "short_selling_ratio", "short_selling_ratio_zscore",
]


def _load_ohlcv(db: Session, asset_class: str, days: int = 500) -> pd.DataFrame:
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(OHLCV)
        .join(Instrument, OHLCV.symbol == Instrument.symbol)
        .filter(Instrument.asset_class == asset_class, OHLCV.date_utc >= cutoff)
        .order_by(OHLCV.symbol, OHLCV.date_utc)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "symbol": r.symbol, "date": r.date_utc,
        "open": r.open, "high": r.high, "low": r.low,
        "close": r.close, "volume": r.volume,
    } for r in rows])


def _load_fred_features(db: Session) -> pd.DataFrame:
    """MacroSeries から FRED由来の系列を wide 形式 (date + 各series_id列) で読み込む"""
    fred_ids = [
        "fed_funds_rate", "us10y_yield", "us2y_yield", "us_yield_spread",
        "us_cpi", "us_unemployment", "usdjpy_fred",
    ]
    rows = db.query(MacroSeries).filter(MacroSeries.series_id.in_(fred_ids)).all()
    if not rows:
        return pd.DataFrame(columns=["date"])
    df = pd.DataFrame([{"date": r.date_utc, "series_id": r.series_id, "value": r.value} for r in rows])
    return df.pivot_table(index="date", columns="series_id", values="value").reset_index()


def _load_vix_features(db: Session) -> pd.DataFrame:
    rows = db.query(SentimentIndex).filter_by(index_name="vix").all()
    if not rows:
        return pd.DataFrame(columns=["date", "vix"])
    df = pd.DataFrame([{"date": r.date_utc, "vix": r.value} for r in rows]).sort_values("date")
    df["vix_chg1d"] = df["vix"].pct_change()
    roll_mean = df["vix"].rolling(60, min_periods=30).mean()
    roll_std = df["vix"].rolling(60, min_periods=30).std()
    df["vix_zscore"] = (df["vix"] - roll_mean) / roll_std.replace(0, np.nan)
    return df.reset_index(drop=True)


def _load_feargreed_features(db: Session) -> pd.DataFrame:
    rows = db.query(SentimentIndex).filter_by(index_name="fear_greed").all()
    if not rows:
        return pd.DataFrame(columns=["date", "fear_greed_value"])
    return pd.DataFrame([{"date": r.date_utc, "fear_greed_value": r.value} for r in rows]).sort_values("date")


def _load_earnings_features(db: Session, symbols: list[str]) -> pd.DataFrame:
    rows = db.query(EarningsEvent).filter(EarningsEvent.symbol.in_(symbols)).all()
    if not rows:
        return pd.DataFrame(columns=["symbol", "announcement_date", "surprise_pct"])
    return pd.DataFrame([{
        "symbol": r.symbol, "announcement_date": r.announcement_date, "surprise_pct": r.surprise_pct,
    } for r in rows])


def _load_supply_demand_features(db: Session, metric_name: str) -> pd.DataFrame:
    rows = db.query(SupplyDemand).filter_by(metric_name=metric_name).all()
    if not rows:
        return pd.DataFrame(columns=["date_utc", "market", "metric_name", "value"])
    return pd.DataFrame([{
        "date_utc": r.date_utc, "market": r.market, "metric_name": r.metric_name, "value": r.value,
    } for r in rows])


def _build_features_with_extras(db: Session, df_raw: pd.DataFrame, asset_class: str) -> pd.DataFrame:
    """DBに保存済みの追加データソース(マクロ/センチメント/イベント/需給)を読み込み、
    build_features に渡す。各ソースが空でも build_features 側で None-safe に処理される。"""
    symbols = df_raw["symbol"].unique().tolist()
    df_fred = _load_fred_features(db)
    df_vix = _load_vix_features(db)
    df_feargreed = _load_feargreed_features(db) if asset_class == "crypto" else None
    df_earnings = _load_earnings_features(db, symbols) if asset_class == "equity_jp" else None

    if asset_class == "equity_jp":
        df_flows = _load_supply_demand_features(db, "foreign_net_ratio")
        df_margin = _load_supply_demand_features(db, "margin_ratio")
        df_short = _load_supply_demand_features(db, "short_selling_ratio")
    else:
        df_flows = df_margin = df_short = None

    return build_features(
        df_raw,
        df_fred=df_fred,
        df_vix=df_vix,
        df_feargreed=df_feargreed,
        df_earnings=df_earnings,
        df_flows=df_flows,
        df_margin=df_margin,
        df_short=df_short,
    )


def train_model(
    db: Session,
    asset_class: str = "equity_jp",
    target: str = "fwd_ret_5d",
    n_splits: int = 5,
) -> dict:
    print(f"\n=== モデル学習: {asset_class} / {target} ===")
    df_raw = _load_ohlcv(db, asset_class)
    if df_raw.empty:
        raise ValueError("OHLCVデータがありません。先にデータを更新してください。")

    df_feat = _build_features_with_extras(db, df_raw, asset_class)
    available = [c for c in FEATURE_COLS if c in df_feat.columns]
    df_clean = df_feat.dropna(subset=available + [target]).copy()

    if len(df_clean) < 500:
        raise ValueError(f"学習データが不足しています ({len(df_clean)} 行)")

    print(f"学習データ: {len(df_clean):,} 行 × {len(available)} 特徴量")
    models, metrics_df, _ = walkforward_train(
        df_clean, available, target, n_splits=n_splits
    )

    version = f"{settings.model_version}_{asset_class}"
    save_model(models, available, version=version)

    mean_ic = float(metrics_df["rank_ic"].mean())
    mv = ModelVersion(
        version_id=version,
        asset_class=asset_class,
        target=target,
        trained_at=datetime.utcnow(),
        mean_rank_ic=mean_ic,
        n_features=len(available),
        n_samples=len(df_clean),
        is_active=1,
    )
    db.merge(mv)
    db.commit()

    return {
        "mean_rank_ic": mean_ic,
        "n_features": len(available),
        "n_samples": len(df_clean),
        "model_version": version,
    }


def run_prediction(
    db: Session,
    asset_class: str = "equity_jp",
    target: str = "fwd_ret_5d",
) -> int:
    version = f"{settings.model_version}_{asset_class}"
    try:
        models, feature_cols = load_model(version=version)
    except FileNotFoundError as e:
        print(e)
        print("先に /api/v1/admin/train を実行してモデルを学習してください。")
        return 0

    df_raw = _load_ohlcv(db, asset_class)
    if df_raw.empty:
        return 0

    df_feat = _build_features_with_extras(db, df_raw, asset_class)
    latest_date = df_feat["date"].max()
    df_latest = df_feat[df_feat["date"] == latest_date].copy()

    available = [c for c in feature_cols if c in df_latest.columns]
    df_latest = df_latest.dropna(subset=available)
    if df_latest.empty:
        print("最新日の特徴量が不足しています")
        return 0

    X = pd.DataFrame(index=df_latest.index, columns=feature_cols, dtype=float)
    for col in available:
        X[col] = df_latest[col].values

    preds = ensemble_predict(models, X)
    df_pred = df_latest[["symbol"]].copy()
    df_pred["predicted_return"] = preds
    df_pred = df_pred.sort_values("predicted_return", ascending=False).reset_index(drop=True)
    df_pred["rank"] = range(1, len(df_pred) + 1)

    for _, row in df_pred.iterrows():
        existing = (
            db.query(Prediction)
            .filter_by(symbol=row["symbol"], date_utc=latest_date, target=target)
            .first()
        )
        if existing:
            existing.predicted_return = row["predicted_return"]
            existing.rank = int(row["rank"])
            existing.model_version = version
        else:
            db.add(Prediction(
                symbol=row["symbol"],
                date_utc=latest_date,
                target=target,
                predicted_return=row["predicted_return"],
                rank=int(row["rank"]),
                model_version=version,
            ))
    db.commit()
    print(f"{len(df_pred)} 銘柄の予測を保存 (as of {latest_date.date()})")
    return len(df_pred)
