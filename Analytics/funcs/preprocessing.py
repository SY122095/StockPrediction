"""前処理ユーティリティ"""
import numpy as np
import pandas as pd
from typing import Sequence


def winsorize(df: pd.DataFrame, cols: Sequence[str], lower: float = 0.01, upper: float = 0.99) -> pd.DataFrame:
    """外れ値をパーセンタイルでクリップ"""
    df = df.copy()
    for col in cols:
        lo = df[col].quantile(lower)
        hi = df[col].quantile(upper)
        df[col] = df[col].clip(lo, hi)
    return df


def fill_missing(df: pd.DataFrame, cols: Sequence[str], method: str = "ffill") -> pd.DataFrame:
    """欠損値補完"""
    df = df.copy()
    if method == "ffill":
        df[cols] = df[cols].ffill()
    elif method == "bfill":
        df[cols] = df[cols].bfill()
    elif method == "zero":
        df[cols] = df[cols].fillna(0)
    elif method == "mean":
        df[cols] = df[cols].fillna(df[cols].mean())
    elif method == "median":
        df[cols] = df[cols].fillna(df[cols].median())
    return df


def train_test_split_by_date(
    df: pd.DataFrame, date_col: str, split_date: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """日付で学習/テスト分割"""
    train = df[df[date_col] < split_date].copy().reset_index(drop=True)
    test = df[df[date_col] >= split_date].copy().reset_index(drop=True)
    print(f"学習: {len(train):,} 行 | テスト: {len(test):,} 行 (分割日: {split_date})")
    return train, test


def check_missing(df: pd.DataFrame) -> pd.DataFrame:
    """欠損値サマリー"""
    missing = df.isnull().sum()
    pct = missing / len(df) * 100
    return (
        pd.DataFrame({"count": missing, "pct": pct})
        .loc[missing > 0]
        .sort_values("pct", ascending=False)
    )


def remove_duplicates(df: pd.DataFrame, subset: Sequence[str] | None = None) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=subset).reset_index(drop=True)
    print(f"重複削除: {before - len(df)} 行除去 → {len(df):,} 行")
    return df
