"""センチメントデータ収集サービス: Fear&Greed Index (暗号資産) → SQLite"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from lib.sentiment_data import fetch_fear_greed_index
from models.db_models import SentimentIndex


def refresh_sentiment(db: Session) -> dict[str, int]:
    """暗号資産向け Fear&Greed Index を取得・保存する (認証不要、常に実行可能)。"""
    inserted = 0
    df = fetch_fear_greed_index(limit=0)
    for _, row in df.iterrows():
        if pd.isna(row["fear_greed_value"]):
            continue
        existing = db.query(SentimentIndex).filter_by(index_name="fear_greed", date_utc=row["date"]).first()
        if existing:
            existing.value = row["fear_greed_value"]
            existing.asset_class = "crypto"
            existing.source = "alternative.me"
        else:
            db.add(SentimentIndex(
                date_utc=row["date"], index_name="fear_greed", asset_class="crypto",
                value=row["fear_greed_value"], source="alternative.me",
            ))
            inserted += 1
    db.commit()
    print(f"センチメントデータ更新: Fear&Greed {inserted} 件")
    return {"fear_greed": inserted}
