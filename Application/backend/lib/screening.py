"""急騰候補スクリーニング: 流動性フィルタ + ルールベース急騰スコア (LightGBM非依存)

広いユニバース(東証全上場銘柄)を対象に、時価総額ではなく「流動性(売買代金)」で
足切りしたうえで、出来高スパイク・モメンタム・高値ブレイクを組み合わせた軽量スコアで
ランキングする。コア層のLightGBM予測パイプラインとは完全に独立している。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_liquidity_filter(
    df_ohlcv: pd.DataFrame,
    min_avg_turnover: float = 5_000_000,
    min_trading_coverage: float = 0.9,
    window: int = 20,
) -> set[str]:
    """直近 window 営業日の平均売買代金・取引成立日数カバレッジで通過銘柄を絞り込む。

    時価総額は一切参照しない (小型株を機械的に除外しないため)。
    df_ohlcv の想定列: symbol, date, close, volume, (turnover_value があれば優先使用)
    """
    if df_ohlcv is None or df_ohlcv.empty:
        return set()

    df = df_ohlcv.sort_values(["symbol", "date"]).copy()
    if "turnover_value" in df.columns and df["turnover_value"].notna().any():
        df["turnover"] = df["turnover_value"].fillna(df["close"] * df["volume"])
    else:
        df["turnover"] = df["close"] * df["volume"]

    recent = df.groupby("symbol").tail(window)
    agg = recent.groupby("symbol").agg(
        avg_turnover=("turnover", "mean"),
        trading_days=("volume", lambda s: (s.fillna(0) > 0).sum()),
        n_days=("volume", "size"),
    )
    agg["coverage"] = agg["trading_days"] / agg["n_days"].clip(lower=1)

    passed = agg[
        (agg["avg_turnover"] >= min_avg_turnover) & (agg["coverage"] >= min_trading_coverage)
    ]
    return set(passed.index)


def compute_surge_scores(df_ohlcv: pd.DataFrame, breakout_window: int = 20) -> pd.DataFrame:
    """出来高スパイク・モメンタム・高値ブレイクの複合スコアを日付×銘柄で計算する。

    戻り値の列: symbol, date, volume_spike, momentum_5d, breakout_20d, composite
    値が大きいほど「急騰候補らしさ」が高いことを示す。
    """
    cols = ["symbol", "date", "volume_spike", "momentum_5d", "breakout_20d", "composite"]
    if df_ohlcv is None or df_ohlcv.empty:
        return pd.DataFrame(columns=cols)

    df = df_ohlcv.sort_values(["symbol", "date"]).copy()

    # 出来高スパイク: 直近出来高の20日トレーリングz-score
    vol_mean = df.groupby("symbol")["volume"].transform(lambda x: x.rolling(20, min_periods=10).mean())
    vol_std = df.groupby("symbol")["volume"].transform(lambda x: x.rolling(20, min_periods=10).std())
    df["volume_spike"] = (df["volume"] - vol_mean) / vol_std.replace(0, np.nan)

    # モメンタム: 5営業日リターン
    df["momentum_5d"] = df.groupby("symbol")["close"].pct_change(5)

    # 高値ブレイク: 直近N日高値(当日除く)からの乖離率
    prior_high = df.groupby("symbol")["close"].transform(
        lambda x: x.shift(1).rolling(breakout_window, min_periods=breakout_window // 2).max()
    )
    df["breakout_20d"] = (df["close"] - prior_high) / prior_high.replace(0, np.nan)

    # 複合スコア: 日付ごとのクロスセクション百分位ランクの平均
    rank_cols = ["volume_spike", "momentum_5d", "breakout_20d"]
    for c in rank_cols:
        df[f"{c}_rank"] = df.groupby("date")[c].rank(pct=True)
    df["composite"] = df[[f"{c}_rank" for c in rank_cols]].mean(axis=1)

    return df[cols].reset_index(drop=True)
