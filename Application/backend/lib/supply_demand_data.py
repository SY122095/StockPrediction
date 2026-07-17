"""JPX統計データ取得: 投資部門別売買状況・信用取引残高・空売り比率

JPXの統計ページは非ブラウザUAからのアクセスを403で拒否することが多く(実機確認済み)、
またページ構成・ファイルURLが予告なく変わりやすい (docs/api_setup_guide.md 4章の注意点)。
そのため「ブラウザ相当UAでのライブ取得を試みる → 失敗したらローカル手動配置ファイルに
フォールバックする → それも無ければ空 DataFrame」の3段構えにする。

手動配置先: Application/backend/data/jpx_manual/
  - 投資部門別売買状況の週次Excel/CSVをダウンロードしてこのフォルダに置くと、
    ライブ取得失敗時に自動的に読み込まれる。
"""
from __future__ import annotations

import warnings
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

warnings.filterwarnings("ignore")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

MANUAL_DATA_DIR = Path(__file__).parent.parent / "data" / "jpx_manual"

_PAGES = {
    "investor_flows": "https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html",
    "margin_balance":  "https://www.jpx.co.jp/markets/statistics-equities/margin/index.html",
    "short_selling":   "https://www.jpx.co.jp/markets/statistics-equities/short-selling/index.html",
}

_EMPTY_COLS = ["date_utc", "market", "metric_name", "value"]


def _find_latest_file_link(index_url: str, extensions: tuple[str, ...] = (".xlsx", ".xls", ".csv")) -> str | None:
    from bs4 import BeautifulSoup

    r = requests.get(index_url, headers=_BROWSER_HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(extensions):
            return urljoin(index_url, href)
    return None


def _download_bytes(url: str) -> bytes:
    r = requests.get(url, headers=_BROWSER_HEADERS, timeout=30)
    r.raise_for_status()
    return r.content


def _latest_local_file(hint: str) -> Path | None:
    if not MANUAL_DATA_DIR.exists():
        return None
    candidates = sorted(
        [p for p in MANUAL_DATA_DIR.glob(f"*{hint}*") if p.suffix.lower() in (".xlsx", ".xls", ".csv")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_excel_or_csv(path_or_bytes, filename_hint: str = "") -> pd.DataFrame | None:
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            if filename_hint.lower().endswith(".csv"):
                import io
                return pd.read_csv(io.BytesIO(path_or_bytes))
            import io
            return pd.read_excel(io.BytesIO(path_or_bytes))
        path = Path(path_or_bytes)
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        return pd.read_excel(path)
    except Exception as e:
        print(f"  WARN [JPX] Excel/CSV 解析失敗: {e}")
        return None


def _fetch_raw(source_key: str, local_hint: str) -> pd.DataFrame | None:
    page_url = _PAGES[source_key]
    try:
        file_url = _find_latest_file_link(page_url)
        if file_url:
            raw = _download_bytes(file_url)
            df = _load_excel_or_csv(raw, filename_hint=file_url)
            if df is not None:
                return df
    except Exception as e:
        print(f"  WARN [JPX:{source_key}] ライブ取得失敗 ({e})。ローカル手動配置ファイルを探索します"
              f" → {MANUAL_DATA_DIR}")

    local = _latest_local_file(local_hint)
    if local is not None:
        print(f"  INFO [JPX:{source_key}] ローカルファイルを使用: {local.name}")
        return _load_excel_or_csv(local)

    print(
        f"  WARN [JPX:{source_key}] データ取得不可。{page_url} から手動DLし、"
        f"{MANUAL_DATA_DIR} に配置してください"
    )
    return None


def _to_metric_frame(df_raw: pd.DataFrame, market: str, metric_name: str, value_col_hint: str) -> pd.DataFrame:
    """生の表から date/value 列を推測して正規化する (best-effort)。

    JPXのExcelレイアウトは頻繁に変わるため、列名に日付/対象キーワードを含む列を
    ヒューリスティックに探す。見つからない場合は空 DataFrame を返す。
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=_EMPTY_COLS)

    date_col = next((c for c in df_raw.columns if "日" in str(c) or "date" in str(c).lower()), None)
    value_col = next((c for c in df_raw.columns if value_col_hint in str(c)), None)
    if date_col is None or value_col is None:
        print(f"  WARN [JPX] {metric_name}: 列の自動検出に失敗（レイアウト変更の可能性）。空データを返します")
        return pd.DataFrame(columns=_EMPTY_COLS)

    out = pd.DataFrame({
        "date_utc": pd.to_datetime(df_raw[date_col], errors="coerce"),
        "value": pd.to_numeric(df_raw[value_col], errors="coerce"),
    }).dropna()
    out["market"] = market
    out["metric_name"] = metric_name
    return out[_EMPTY_COLS]


def fetch_jpx_investor_flows(market: str = "TSE_ALL") -> pd.DataFrame:
    """投資部門別売買状況 (週次) から外国人投資家の売買代金比率を抽出する。"""
    df_raw = _fetch_raw("investor_flows", local_hint="investor")
    return _to_metric_frame(df_raw, market, "foreign_net_ratio", value_col_hint="海外")


def fetch_jpx_margin_balance(market: str = "TSE_ALL") -> pd.DataFrame:
    """信用取引残高 (週次) から信用倍率を抽出する。"""
    df_raw = _fetch_raw("margin_balance", local_hint="margin")
    return _to_metric_frame(df_raw, market, "margin_ratio", value_col_hint="信用")


def fetch_jpx_short_selling_ratio(market: str = "TSE_ALL") -> pd.DataFrame:
    """空売り比率 (日次) を抽出する。"""
    df_raw = _fetch_raw("short_selling", local_hint="short")
    return _to_metric_frame(df_raw, market, "short_selling_ratio", value_col_hint="空売り")
