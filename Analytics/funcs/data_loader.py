"""汎用データ入出力ユーティリティ"""
from pathlib import Path
import yaml
import pandas as pd


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs)


def load_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def load_excel(path: str | Path, sheet_name=0, **kwargs) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, **kwargs)


def save_csv(df: pd.DataFrame, path: str | Path, index: bool = False) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index, encoding="utf-8-sig")
    print(f"保存: {path} ({len(df):,} 行)")


def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"保存: {path} ({len(df):,} 行)")


def save_excel(df: pd.DataFrame, path: str | Path, sheet_name: str = "Sheet1") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, sheet_name=sheet_name, index=False)
    print(f"保存: {path} ({len(df):,} 行)")
