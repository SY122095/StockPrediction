"""
初回セットアップスクリプト
実行: python init_db.py [--start YYYY-MM-DD]

処理内容:
  1. SQLite テーブル作成
  2. 株式・暗号資産データのダウンロード
  ※ モデル学習は /api/v1/admin/train エンドポイントから実行
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.database import Base, SessionLocal, engine
from models import db_models  # noqa: F401 - テーブル定義をロード
from services.data_service import refresh_all


def main():
    parser = argparse.ArgumentParser(description="株価予測システム 初期化")
    parser.add_argument("--start", default="2022-01-01", help="データ取得開始日 (YYYY-MM-DD)")
    args = parser.parse_args()

    print("=" * 50)
    print("株価予測システム 初期化")
    print("=" * 50)

    print("\n[1/2] テーブル作成...")
    Base.metadata.create_all(bind=engine)
    print("  完了")

    print(f"\n[2/2] データダウンロード (start={args.start})...")
    print("  ※ 初回は数分かかる場合があります\n")
    db = SessionLocal()
    try:
        result = refresh_all(db, start=args.start)
        print(f"\n  株式: {result['equity_jp']:,} 件")
        print(f"  暗号資産: {result['crypto']:,} 件")
    finally:
        db.close()

    print("\n" + "=" * 50)
    print("初期化完了！")
    print()
    print("次のステップ:")
    print("  1. uvicorn main:app --reload  → API サーバー起動")
    print("  2. POST /api/v1/admin/train   → モデル学習")
    print("  3. POST /api/v1/admin/predict → 予測実行")
    print("  4. streamlit run ../frontend/app.py  → ダッシュボード起動")
    print("=" * 50)


if __name__ == "__main__":
    main()
