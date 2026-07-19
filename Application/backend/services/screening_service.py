"""急騰候補スクリーニングサービス: 広いユニバースのOHLCV → 流動性フィルタ → ルールベーススコア → DB保存

コア層(既存LightGBM予測パイプライン)とは完全に独立。screening.py のロジックのみを使用する。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from lib.screening import compute_liquidity_filter, compute_surge_scores
from models.db_models import Instrument, OHLCV, ScreeningScore

_SCORE_COLS = ["volume_spike", "momentum_5d", "breakout_20d", "composite"]


def _load_broad_ohlcv(db: Session, days: int = 180) -> pd.DataFrame:
    """is_active な equity_jp 銘柄すべての直近OHLCVを読み込む (コア30銘柄も含めて対象にする)。

    J-Quants無料プランはデータが実時刻から約12週間(84日)遅延するため、"今日"起点の
    トレイリングウィンドウが短いと、実際に取得済みの最新日にすら届かない/20日ローリング
    計算に必要な過去分が足りなくなる。遅延分(84日) + ローリング計算に要する日数(20営業日
    ≒暦日30日) + 余裕を見て180日をデフォルトとする。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(OHLCV)
        .join(Instrument, OHLCV.symbol == Instrument.symbol)
        .filter(
            Instrument.asset_class == "equity_jp",
            Instrument.is_active == 1,
            OHLCV.date_utc >= cutoff,
        )
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


def run_screening(
    db: Session,
    min_avg_turnover: float = 5_000_000,
    min_trading_coverage: float = 0.9,
) -> dict:
    df_raw = _load_broad_ohlcv(db)
    if df_raw.empty:
        print("  WARN [screening] OHLCVデータがありません。先に refresh-equity-broad を実行してください。")
        return {"universe_size": 0, "passed_liquidity_filter": 0, "scored": 0}

    passed_symbols = compute_liquidity_filter(
        df_raw, min_avg_turnover=min_avg_turnover, min_trading_coverage=min_trading_coverage
    )
    if not passed_symbols:
        print("  WARN [screening] 流動性フィルタを通過した銘柄がありません。")
        return {"universe_size": df_raw["symbol"].nunique(), "passed_liquidity_filter": 0, "scored": 0}

    df_filtered = df_raw[df_raw["symbol"].isin(passed_symbols)]
    df_scores = compute_surge_scores(df_filtered)
    if df_scores.empty:
        return {"universe_size": df_raw["symbol"].nunique(), "passed_liquidity_filter": len(passed_symbols), "scored": 0}

    latest_date = df_scores["date"].max()
    df_latest = df_scores[df_scores["date"] == latest_date].dropna(subset=["composite"]).copy()

    saved = 0
    for score_type in _SCORE_COLS:
        ranked = df_latest.sort_values(score_type, ascending=False).reset_index(drop=True)
        ranked["rank"] = ranked.index + 1
        for _, row in ranked.iterrows():
            existing = (
                db.query(ScreeningScore)
                .filter_by(symbol=row["symbol"], date_utc=latest_date, score_type=score_type)
                .first()
            )
            value = row[score_type]
            if pd.isna(value):
                continue
            if existing:
                existing.value = float(value)
                existing.rank = int(row["rank"])
            else:
                db.add(ScreeningScore(
                    symbol=row["symbol"], date_utc=latest_date, score_type=score_type,
                    value=float(value), rank=int(row["rank"]),
                ))
                saved += 1
    db.commit()

    print(
        f"[screening] 対象 {df_raw['symbol'].nunique()} 銘柄 → 流動性通過 {len(passed_symbols)} 銘柄 → "
        f"{len(df_latest)} 銘柄をスコアリング (as of {latest_date.date()})"
    )
    return {
        "universe_size": df_raw["symbol"].nunique(),
        "passed_liquidity_filter": len(passed_symbols),
        "scored": len(df_latest),
        "as_of_date": str(latest_date.date()),
    }
