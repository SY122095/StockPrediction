"""J-Quants API V2 (JPX公式) 上場銘柄マスタ・株価・決算発表日・財務サマリー取得

無料プランでの実際のV2エンドポイントは実キーで実地検証済み (2026-07):
- 上場銘柄マスタ: GET /v2/equities/master (パラメータ不要, 全銘柄+ETF/REIT等を含む約4,450件)
- 株価四本値 (単一銘柄): GET /v2/equities/bars/daily?code=XXXX
- 株価四本値 (単一日・全銘柄一括): GET /v2/equities/bars/daily?date=YYYY-MM-DD
  ※無料プランは日付が「12週間遅延」の範囲内でないと400エラーになる (サブスクリプション期間内のみ)
- 財務サマリー: GET /v2/fins/summary?code=XXXX (実地検証済み、200 OK)
- **/v2/fins/announcement は存在しない** (404相当の"endpoint does not exist"応答を実地確認済み)。
  決算発表日は fins/summary の DiscDate 列で代替する (=開示日そのものが決算発表日)。
  ただし fins/summary は過去の開示履歴のみを返すため、**将来の決算発表予定日は取得できない**
  (「今後の決算発表が近い銘柄」機能は本エンドポイントでは実現不可、既発表分のPEAD分析用途のみ)。

銘柄コード変換に注意: J-Quantsは5桁 (4桁+末尾0, 例 "72030")、本プロジェクトの他モジュール
(yfinance系) は "7203.T" 形式を使う。_code_to_symbol / _symbol_to_code で変換する。
"""
from __future__ import annotations

import time
import warnings

import pandas as pd
import requests

from core.config import settings

warnings.filterwarnings("ignore")

_BASE_URL = "https://api.jquants.com/v2"

# 無料プランのレート制限 (約5req/分) を踏まえた安全マージン
_RATE_LIMIT_SLEEP_SEC = 12.5


def _headers() -> dict[str, str]:
    return {"x-api-key": settings.jquants_api_key}


def _configured() -> bool:
    return settings.is_configured("jquants_api_key")


def _code_to_symbol(code: str) -> str:
    """J-Quants 5桁コード ("72030") → プロジェクト標準シンボル ("7203.T")"""
    return f"{str(code)[:4]}.T"


def _symbol_to_code(symbol: str) -> str:
    """プロジェクト標準シンボル ("7203.T") → J-Quants 5桁コード ("72030")"""
    return f"{symbol.replace('.T', '')}0"


# 実際の株式のみ (ETF/REIT/ETN等を除外) を示す ProdCat 値 (実地検証で確認)
_EQUITY_PROD_CAT = "011"

# J-Quants Mkt名 → 本プロジェクトの market_segment 表記
_MARKET_SEGMENT_MAP = {
    "プライム":    "Prime",
    "スタンダード": "Standard",
    "グロース":    "Growth",
}


def fetch_listed_instruments(include_tokyo_pro: bool = False) -> pd.DataFrame:
    """東証上場銘柄マスタを取得する (株式のみ、ETF/REIT等は除外)。

    戻り値の列: symbol, name, market_segment, sector33_code, sector33_name
    デフォルトでは TOKYO PRO MARKET (プロ投資家向け特別市場) は除外する。
    """
    cols = ["symbol", "name", "market_segment", "sector33_code", "sector33_name"]
    if not _configured():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため fetch_listed_instruments をスキップします")
        return pd.DataFrame(columns=cols)

    try:
        r = requests.get(f"{_BASE_URL}/equities/master", headers=_headers(), timeout=30)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)

        df = pd.DataFrame(rows)
        df = df[df["ProdCat"] == _EQUITY_PROD_CAT].copy()
        if not include_tokyo_pro:
            df = df[df["MktNm"] != "TOKYO PRO MARKET"]

        df["symbol"] = df["Code"].map(_code_to_symbol)
        df["market_segment"] = df["MktNm"].map(_MARKET_SEGMENT_MAP).fillna(df["MktNm"])
        df = df.rename(columns={"CoName": "name", "S33": "sector33_code", "S33Nm": "sector33_name"})
        df = df.drop_duplicates(subset="symbol", keep="last")
        return df[cols].reset_index(drop=True)
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_listed_instruments 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def fetch_daily_quotes_by_date(date: str) -> pd.DataFrame:
    """指定日の全銘柄株価四本値を1コールで取得する (J-Quantsのbars/dailyはdate指定で全銘柄一括対応)。

    戻り値の列: symbol, date, open, high, low, close, volume, turnover_value
    無料プランのサブスクリプション期間外の日付は空 DataFrame を返す (エラーにしない)。
    """
    cols = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_value"]
    if not _configured():
        return pd.DataFrame(columns=cols)

    try:
        r = requests.get(f"{_BASE_URL}/equities/bars/daily", params={"date": date}, headers=_headers(), timeout=30)
        if r.status_code == 400:
            # サブスクリプション対象期間外の日付など。休日でもここに来ることがある
            return pd.DataFrame(columns=cols)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)

        df = pd.DataFrame(rows)
        df["symbol"] = df["Code"].map(_code_to_symbol)
        df = df.rename(columns={
            "Date": "date", "O": "open", "H": "high", "L": "low", "C": "close",
            "Vo": "volume", "Va": "turnover_value",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[cols]
    except Exception as e:
        print(f"  WARN [J-Quants] fetch_daily_quotes_by_date({date}) 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def _probe_subscription_end_date(after: str) -> str | None:
    """`after`以降のダミー日付で400を意図的に起こし、エラーメッセージから
    実際のサブスクリプション対象期間の終端日を抽出する (無駄なレート制限消費を避けるため)。"""
    import re

    try:
        r = requests.get(
            f"{_BASE_URL}/equities/bars/daily", params={"date": after}, headers=_headers(), timeout=15
        )
        if r.status_code != 400:
            return None
        msg = r.json().get("message", "")
        # 例: "Your subscription covers the following dates: 2024-04-26 ~ 2026-04-26. ..."
        dates_found = re.findall(r"\d{4}-\d{2}-\d{2}", msg)
        return dates_found[1] if len(dates_found) >= 2 else None
    except Exception:
        return None


def fetch_daily_quotes_range(start: str, end: str, sleep_sec: float = _RATE_LIMIT_SLEEP_SEC) -> pd.DataFrame:
    """日付範囲の全銘柄株価四本値を取得する (1営業日=1APIコール、レート制限を考慮して逐次実行)。

    無料プランはサブスクリプション対象期間 (直近12週間遅延) を超える日付は400になるため、
    事前に1コールだけ probe して対象期間の終端でrequestedの範囲を切り詰め、
    無駄なレート制限待ちを避ける。
    """
    cols = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_value"]
    if not _configured():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため fetch_daily_quotes_range をスキップします")
        return pd.DataFrame(columns=cols)

    dates = pd.bdate_range(start=start, end=end)
    if len(dates) == 0:
        return pd.DataFrame(columns=cols)

    subscription_end = _probe_subscription_end_date(dates[-1].strftime("%Y-%m-%d"))
    if subscription_end is not None:
        clipped = dates[dates <= pd.Timestamp(subscription_end)]
        if len(clipped) < len(dates):
            print(f"  INFO [J-Quants] サブスクリプション対象期間は〜{subscription_end}まで。"
                  f"範囲を {len(dates)}→{len(clipped)} 営業日に短縮します")
        dates = clipped
    time.sleep(sleep_sec)  # probe呼び出し分のレート制限消化

    print(f"  [J-Quants] 一括株価取得: {len(dates)} 営業日分 (約 {len(dates) * sleep_sec / 60:.1f} 分)")
    frames = []
    for i, d in enumerate(dates):
        df_day = fetch_daily_quotes_by_date(d.strftime("%Y-%m-%d"))
        if not df_day.empty:
            frames.append(df_day)
        if i < len(dates) - 1:
            time.sleep(sleep_sec)

    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


def fetch_financial_summary(symbol: str) -> pd.DataFrame:
    """財務サマリー (売上・営業利益・純利益・EPS 実績/予想) を取得する。

    Args:
        symbol: プロジェクト標準形式 ("7203.T")。内部でJ-Quantsの5桁コードに変換する
                (この変換を怠ると `'code' must be 4 or 5 characters.` で400になる、実地確認済み)。

    戻り値の列: symbol, disc_date, period_type, fy_end, sales, op, np, eps,
                forecast_eps_this (当期予想EPS, 実績開示時は空のことが多い),
                forecast_eps_next (来期予想EPS)
    数値列は空文字列/欠測を NaN として float 化する。
    """
    cols = ["symbol", "disc_date", "period_type", "fy_end", "sales", "op", "np",
            "eps", "forecast_eps_this", "forecast_eps_next"]
    if not _configured():
        print(f"  WARN [J-Quants:{symbol}] JQUANTS_API_KEY が未設定/ダミーのため fetch_financial_summary をスキップします")
        return pd.DataFrame(columns=cols)

    try:
        code = _symbol_to_code(symbol)
        r = requests.get(f"{_BASE_URL}/fins/summary", params={"code": code}, headers=_headers(), timeout=15)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "Code": "symbol", "DiscDate": "disc_date", "CurPerType": "period_type",
            "CurFYEn": "fy_end", "Sales": "sales", "OP": "op", "NP": "np", "EPS": "eps",
            "FEPS": "forecast_eps_this", "NxFEPS": "forecast_eps_next",
        })
        df["symbol"] = df["symbol"].map(_code_to_symbol)
        df["disc_date"] = pd.to_datetime(df["disc_date"])
        for c in ["sales", "op", "np", "eps", "forecast_eps_this", "forecast_eps_next"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
        keep = [c for c in cols if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  WARN [J-Quants:{symbol}] fetch_financial_summary 取得失敗: {e}")
        return pd.DataFrame(columns=cols)


def fetch_earnings_calendar(symbol: str | None = None) -> pd.DataFrame:
    """決算発表(開示)日一覧を取得する。

    J-Quants V2には独立した「決算発表予定カレンダー」エンドポイントが存在しないため
    (`/v2/fins/announcement` は404相当で無効と実地確認済み)、fins/summary の開示日 (DiscDate)
    を代用する。**この方法では過去の開示のみ取得可能で、将来の予定日は分からない点に注意。**

    戻り値の列: symbol, announcement_date, fiscal_period
    """
    cols = ["symbol", "announcement_date", "fiscal_period"]
    if symbol is None:
        return pd.DataFrame(columns=cols)
    fin = fetch_financial_summary(symbol)
    if fin.empty:
        return pd.DataFrame(columns=cols)
    out = fin.rename(columns={"disc_date": "announcement_date"}).copy()
    out["fiscal_period"] = out["period_type"].astype(str) + out["fy_end"].astype(str).str.slice(0, 7)
    return out[cols]


def build_earnings_events(symbols: list[str]) -> pd.DataFrame:
    """複数銘柄の財務サマリー(実績/予想EPS)からPEAD用イベントテーブルを構築する。

    戻り値の列: symbol, announcement_date, fiscal_period, actual_eps, forecast_eps, surprise_pct

    surprise_pct は「当該開示の実績EPS」と「直前の開示時点で示されていた予想EPS」の乖離率。
    直前開示の forecast_eps_this (当期予想) が空の場合は forecast_eps_next (来期予想。
    直前開示時点では『来期』だったものが今回『当期実績』として開示されたケースに対応) で代替する。
    この対応関係は開示種別(Q1〜Q4/FY)を厳密に追跡したものではない近似である点に注意。
    """
    cols = ["symbol", "announcement_date", "fiscal_period", "actual_eps", "forecast_eps", "surprise_pct"]
    if not _configured():
        print("  WARN [J-Quants] JQUANTS_API_KEY が未設定/ダミーのため build_earnings_events をスキップします")
        return pd.DataFrame(columns=cols)

    records = []
    for symbol in symbols:
        fin = fetch_financial_summary(symbol)
        if fin.empty:
            continue
        fin = fin.sort_values("disc_date").reset_index(drop=True)
        # 直前開示の予想値 (当期予想優先、無ければ来期予想) を今回の予想値として近似使用
        prev_forecast = fin["forecast_eps_this"].shift(1)
        prev_forecast = prev_forecast.fillna(fin["forecast_eps_next"].shift(1))

        merged = pd.DataFrame({
            "symbol": fin["symbol"],
            "announcement_date": fin["disc_date"],
            "fiscal_period": fin["period_type"].astype(str) + fin["fy_end"].astype(str).str.slice(0, 7),
            "actual_eps": fin["eps"],
            "forecast_eps": prev_forecast,
        })
        merged["surprise_pct"] = (
            (merged["actual_eps"] - merged["forecast_eps"]) / merged["forecast_eps"].abs() * 100
        )
        merged.loc[merged["forecast_eps"].isna() | (merged["forecast_eps"] == 0), "surprise_pct"] = None
        records.append(merged)

    if not records:
        return pd.DataFrame(columns=cols)
    df = pd.concat(records, ignore_index=True)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]
