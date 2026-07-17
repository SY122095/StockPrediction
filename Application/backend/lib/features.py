"""テクニカル指標・特徴量エンジニアリング (Application 内部用)"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---- リターン ----

def add_returns(df: pd.DataFrame, windows: list[int] = [1, 5, 20]) -> pd.DataFrame:
    for w in windows:
        df[f"ret_{w}d"] = df.groupby("symbol")["close"].pct_change(w)
        df[f"logret_{w}d"] = np.log(
            df.groupby("symbol")["close"].transform(lambda x: x / x.shift(w))
        )
    return df


def add_forward_returns(df: pd.DataFrame, windows: list[int] = [1, 5, 20]) -> pd.DataFrame:
    for w in windows:
        df[f"fwd_ret_{w}d"] = df.groupby("symbol")["close"].transform(
            lambda x: x.pct_change(w).shift(-w)
        )
    return df


# ---- 移動平均 ----

def add_moving_averages(df: pd.DataFrame, windows: list[int] = [5, 10, 20, 60]) -> pd.DataFrame:
    for w in windows:
        df[f"sma_{w}"] = df.groupby("symbol")["close"].transform(
            lambda x: x.rolling(w, min_periods=1).mean()
        )
        df[f"ema_{w}"] = df.groupby("symbol")["close"].transform(
            lambda x: x.ewm(span=w, adjust=False).mean()
        )
    for w in windows:
        df[f"price_sma{w}_ratio"] = df["close"] / df[f"sma_{w}"]
    return df


# ---- RSI ----

def add_rsi(df: pd.DataFrame, windows: list[int] = [14, 28]) -> pd.DataFrame:
    for w in windows:
        delta = df.groupby("symbol")["close"].transform(lambda x: x.diff())
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.groupby(df["symbol"]).transform(
            lambda x: x.ewm(com=w - 1, min_periods=w).mean()
        )
        avg_loss = loss.groupby(df["symbol"]).transform(
            lambda x: x.ewm(com=w - 1, min_periods=w).mean()
        )
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df[f"rsi_{w}"] = 100 - (100 / (1 + rs))
    return df


# ---- MACD ----

def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    def _calc(x: pd.Series) -> pd.DataFrame:
        ema_f = x.ewm(span=fast, adjust=False).mean()
        ema_s = x.ewm(span=slow, adjust=False).mean()
        macd = ema_f - ema_s
        sig = macd.ewm(span=signal, adjust=False).mean()
        return pd.DataFrame({"macd": macd, "macd_signal": sig, "macd_hist": macd - sig})

    result = (
        df.groupby("symbol")["close"]
        .apply(_calc)
        .reset_index(level=0, drop=True)
    )
    return pd.concat([df, result], axis=1)


# ---- ボリンジャーバンド ----

def add_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    df["bb_mid"] = df.groupby("symbol")["close"].transform(
        lambda x: x.rolling(window, min_periods=window // 2).mean()
    )
    df["bb_std"] = df.groupby("symbol")["close"].transform(
        lambda x: x.rolling(window, min_periods=window // 2).std()
    )
    df["bb_upper"] = df["bb_mid"] + num_std * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - num_std * df["bb_std"]
    band = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / band
    df["bb_width"] = band / df["bb_mid"]
    return df


# ---- ボリューム ----

def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    df["vol_change"] = df.groupby("symbol")["volume"].transform(lambda x: x.pct_change())
    df["vol_sma20"] = df.groupby("symbol")["volume"].transform(
        lambda x: x.rolling(20, min_periods=5).mean()
    )
    df["vol_ratio"] = df["volume"] / df["vol_sma20"].replace(0, np.nan)
    df["turnover"] = df["close"] * df["volume"]
    df["turnover_sma5"] = df.groupby("symbol")["turnover"].transform(
        lambda x: x.rolling(5, min_periods=2).mean()
    )
    return df


# ---- ボラティリティ ----

def add_volatility(df: pd.DataFrame, windows: list[int] = [5, 20]) -> pd.DataFrame:
    log_ret = np.log(df.groupby("symbol")["close"].transform(lambda x: x / x.shift(1)))
    for w in windows:
        df[f"vol_{w}d"] = log_ret.groupby(df["symbol"]).transform(
            lambda x: x.rolling(w, min_periods=w // 2).std() * np.sqrt(252)
        )
    return df


# ---- クロスセクションランク ----

def add_cs_rank(df: pd.DataFrame, cols: list[str], date_col: str = "date") -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[f"{col}_rank"] = df.groupby(date_col)[col].rank(pct=True)
    return df


# ---- マクロ結合 ----

def merge_macro(df_ohlcv: pd.DataFrame, df_macro: pd.DataFrame) -> pd.DataFrame:
    df = df_ohlcv.merge(df_macro, on="date", how="left")
    macro_cols = [c for c in df_macro.columns if c != "date"]
    df[macro_cols] = df[macro_cols].ffill()
    for col in macro_cols:
        df[f"{col}_ret1d"] = df[col].pct_change()
        df[f"{col}_ret5d"] = df[col].pct_change(5)
    return df


# ---- マクロ特徴量 (FRED, リーク防止で1日ラグ) ----

def add_macro_features(df: pd.DataFrame, df_fred: pd.DataFrame | None) -> pd.DataFrame:
    """FRED由来のマクロ系列を1日ラグしてマージする (発表当日の値を当日の特徴量に
    混入させない = リーク防止, docs/02_要件定義書.md FR-1C 準拠)。"""
    if df_fred is None or df_fred.empty:
        return df

    fred_cols = [c for c in df_fred.columns if c != "date"]
    df_lagged = df_fred.sort_values("date").copy()
    df_lagged[fred_cols] = df_lagged[fred_cols].shift(1)

    df = df.merge(df_lagged, on="date", how="left")
    df[fred_cols] = df.groupby("symbol")[fred_cols].ffill()

    if "us10y_yield" in df.columns and "us2y_yield" in df.columns:
        df["us_yield_spread_calc"] = df["us10y_yield"] - df["us2y_yield"]
    for col in fred_cols:
        df[f"{col}_chg1d"] = df.groupby("symbol")[col].transform(lambda x: x.diff())
    return df


# ---- センチメント特徴量 (VIX / Fear&Greed) ----

def add_sentiment_features(
    df: pd.DataFrame,
    df_vix: pd.DataFrame | None = None,
    df_feargreed: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """VIX (equity向け) / Fear&Greed Index (crypto向け) をマージする。
    どちらも該当データが無ければ何もしない (asset_class を問わず両方試す)。"""
    if df_vix is not None and not df_vix.empty:
        cols = [c for c in ["vix", "vix_chg1d", "vix_zscore"] if c in df_vix.columns]
        merge_df = df_vix[["date"] + cols].sort_values("date").copy()
        merge_df[cols] = merge_df[cols].shift(1)  # 前日終値ベースなのでラグ
        df = df.merge(merge_df, on="date", how="left")
        df[cols] = df.groupby("symbol")[cols].ffill()

    if df_feargreed is not None and not df_feargreed.empty:
        cols = [c for c in ["fear_greed_value"] if c in df_feargreed.columns]
        merge_df = df_feargreed[["date"] + cols].sort_values("date").copy()
        merge_df[cols] = merge_df[cols].shift(1)
        df = df.merge(merge_df, on="date", how="left")
        df[cols] = df.groupby("symbol")[cols].ffill()

    return df


# ---- イベント特徴量 (決算 / PEAD) ----

def add_event_features(df: pd.DataFrame, df_earnings: pd.DataFrame | None) -> pd.DataFrame:
    """決算発表日への近接度・直近サプライズを特徴量化する (PEAD想定)。

    df_earnings の想定列: symbol, announcement_date, surprise_pct
    リーク防止: surprise_pct は発表翌営業日以降のみ有効 (当日は伏せる)。
    """
    df["days_to_next_earnings"] = np.nan
    df["days_since_last_earnings"] = np.nan
    df["earnings_surprise_pct"] = np.nan

    if df_earnings is None or df_earnings.empty or "announcement_date" not in df_earnings.columns:
        return df

    ev = df_earnings.dropna(subset=["announcement_date"]).copy()
    ev["announcement_date"] = pd.to_datetime(ev["announcement_date"])

    for sym, grp in df.groupby("symbol"):
        sym_events = ev[ev["symbol"] == sym].sort_values("announcement_date")
        if sym_events.empty:
            continue
        event_dates = sym_events["announcement_date"].values
        idx = grp.index
        dates = grp["date"].values

        next_idx = np.searchsorted(event_dates, dates, side="right")
        for i, d, ni in zip(idx, dates, next_idx):
            if ni < len(event_dates):
                df.loc[i, "days_to_next_earnings"] = (
                    pd.Timestamp(event_dates[ni]) - pd.Timestamp(d)
                ).days
            if ni > 0:
                last_date = pd.Timestamp(event_dates[ni - 1])
                df.loc[i, "days_since_last_earnings"] = (pd.Timestamp(d) - last_date).days
                if pd.Timestamp(d) > last_date:  # 発表翌日以降のみサプライズを開示 (リーク防止)
                    surprise = sym_events.loc[
                        sym_events["announcement_date"] == event_dates[ni - 1], "surprise_pct"
                    ]
                    if not surprise.empty:
                        df.loc[i, "earnings_surprise_pct"] = surprise.iloc[0]

    return df


# ---- 需給特徴量 (JPX投資部門別売買状況・信用残高・空売り比率) ----

def add_supply_demand_features(
    df: pd.DataFrame,
    df_flows: pd.DataFrame | None = None,
    df_margin: pd.DataFrame | None = None,
    df_short: pd.DataFrame | None = None,
    window: int = 20,
) -> pd.DataFrame:
    """市場全体(銘柄横断)の需給指標を全銘柄に同値でマージする。

    各 df_* の想定列: date_utc, value (long形式, lib/supply_demand_data.py の出力)。
    """
    for df_metric, col_name in (
        (df_flows, "foreign_net_ratio"),
        (df_margin, "margin_ratio"),
        (df_short, "short_selling_ratio"),
    ):
        if df_metric is None or df_metric.empty:
            continue
        m = df_metric[["date_utc", "value"]].rename(
            columns={"date_utc": "date", "value": col_name}
        ).sort_values("date")
        m[col_name] = m[col_name].shift(1)  # 公表ラグを考慮 (前営業日確定値を使用)
        df = df.merge(m, on="date", how="left")
        df[col_name] = df.groupby("symbol")[col_name].ffill()
        roll_mean = df[col_name].rolling(window, min_periods=window // 2).mean()
        roll_std = df[col_name].rolling(window, min_periods=window // 2).std()
        df[f"{col_name}_zscore"] = (df[col_name] - roll_mean) / roll_std.replace(0, np.nan)

    return df


# ---- まとめて追加 ----

def build_features(
    df: pd.DataFrame,
    df_macro: pd.DataFrame | None = None,
    df_fred: pd.DataFrame | None = None,
    df_vix: pd.DataFrame | None = None,
    df_feargreed: pd.DataFrame | None = None,
    df_earnings: pd.DataFrame | None = None,
    df_flows: pd.DataFrame | None = None,
    df_margin: pd.DataFrame | None = None,
    df_short: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df = df.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    df = add_returns(df)
    df = add_forward_returns(df)
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_volume_features(df)
    df = add_volatility(df)

    rank_cols = ["ret_1d", "ret_5d", "ret_20d", "vol_20d", "rsi_14", "vol_ratio"]
    df = add_cs_rank(df, rank_cols)

    if df_macro is not None and not df_macro.empty:
        df = merge_macro(df, df_macro)

    # ---- 追加データソース (キー未設定/取得失敗時は None-safe にスキップ) ----
    df = add_macro_features(df, df_fred)
    df = add_sentiment_features(df, df_vix, df_feargreed)
    df = add_event_features(df, df_earnings)
    df = add_supply_demand_features(df, df_flows, df_margin, df_short)

    return df
