"""LightGBM ウォークフォワード学習・推論 (Application 内部用)"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import TimeSeriesSplit

DEFAULT_PARAMS: dict[str, Any] = {
    "objective":        "regression",
    "n_estimators":     300,
    "max_depth":        5,
    "num_leaves":       20,
    "learning_rate":    0.05,
    "colsample_bytree": 0.7,
    "subsample":        0.8,
    "reg_alpha":        0.1,
    "reg_lambda":       0.1,
    "min_child_samples": 20,
    "random_state":     42,
    "n_jobs":           -1,
    "verbose":          -1,
}

MODEL_DIR = Path(__file__).parent.parent / "saved_models"


def rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    corr, _ = spearmanr(y_true, y_pred)
    return float(corr)


def walkforward_train(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    date_col: str = "date",
    n_splits: int = 5,
    params: dict | None = None,
) -> tuple[list[lgb.LGBMRegressor], pd.DataFrame, pd.DataFrame]:
    """ウォークフォワード学習。(models, metrics_df, oof_df) を返す"""
    if params is None:
        params = DEFAULT_PARAMS.copy()

    df = df.dropna(subset=feature_cols + [target_col]).copy()
    df = df.sort_values(date_col).reset_index(drop=True)
    dates = df[date_col].sort_values().unique()

    tscv = TimeSeriesSplit(n_splits=n_splits)
    models, metrics_rows, oof_records = [], [], []

    for fold, (tr_idx, va_idx) in enumerate(tscv.split(dates)):
        tr_dates, va_dates = dates[tr_idx], dates[va_idx]
        tr_mask = df[date_col].isin(tr_dates)
        va_mask = df[date_col].isin(va_dates)

        X_tr, y_tr = df.loc[tr_mask, feature_cols], df.loc[tr_mask, target_col]
        X_va, y_va = df.loc[va_mask, feature_cols], df.loc[va_mask, target_col]

        m = lgb.LGBMRegressor(**params)
        m.fit(
            X_tr, y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )
        y_pred = m.predict(X_va)
        ic = rank_ic(y_va.values, y_pred)
        models.append(m)

        metrics_rows.append({
            "fold": fold + 1,
            "train_start": pd.Timestamp(tr_dates.min()),
            "train_end":   pd.Timestamp(tr_dates.max()),
            "val_start":   pd.Timestamp(va_dates.min()),
            "val_end":     pd.Timestamp(va_dates.max()),
            "rank_ic":     ic,
            "n_train":     int(tr_mask.sum()),
            "n_val":       int(va_mask.sum()),
        })

        oof = df.loc[va_mask, [date_col, "symbol", target_col]].copy()
        oof["pred"] = y_pred
        oof_records.append(oof)

        print(
            f"  Fold {fold+1}: RankIC={ic:.4f}  "
            f"Val {pd.Timestamp(va_dates.min()).date()} ~ {pd.Timestamp(va_dates.max()).date()}"
        )

    metrics_df = pd.DataFrame(metrics_rows)
    oof_df = pd.concat(oof_records, ignore_index=True)
    mean_ic = metrics_df["rank_ic"].mean()
    std_ic = metrics_df["rank_ic"].std()
    print(f"\n  平均 RankIC: {mean_ic:.4f} ± {std_ic:.4f}")
    return models, metrics_df, oof_df


def ensemble_predict(models: list[lgb.LGBMRegressor], X: pd.DataFrame) -> np.ndarray:
    return np.mean([m.predict(X) for m in models], axis=0)


def save_model(
    models: list[lgb.LGBMRegressor],
    feature_cols: list[str],
    version: str = "lgbm_v1",
    model_dir: Path | None = None,
) -> Path:
    if model_dir is None:
        model_dir = MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"{version}.pkl"
    with open(path, "wb") as f:
        pickle.dump({"models": models, "feature_cols": feature_cols}, f)
    print(f"モデル保存: {path}")
    return path


def load_model(
    version: str = "lgbm_v1",
    model_dir: Path | None = None,
) -> tuple[list[lgb.LGBMRegressor], list[str]]:
    if model_dir is None:
        model_dir = MODEL_DIR
    path = model_dir / f"{version}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"モデルファイルが見つかりません: {path}")
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["models"], data["feature_cols"]
