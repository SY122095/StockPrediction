from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_upgrades() -> None:
    """Base.metadata.create_all は既存テーブルへの列追加を行わないため、
    既存テーブルに対する非破壊的な ALTER TABLE ADD COLUMN をここで補う。
    SQLite の ADD COLUMN は既存データを保持したまま実行できる。"""
    inspector = inspect(engine)
    if "instruments" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("instruments")}
    new_cols = {
        "market_segment": "VARCHAR(20)",
        "sector33_code":  "VARCHAR(10)",
        "sector33_name":  "VARCHAR(50)",
        "is_active":      "INTEGER DEFAULT 1",
        "is_core":        "INTEGER DEFAULT 0",
    }
    with engine.begin() as conn:
        for col, coltype in new_cols.items():
            if col not in existing_cols:
                conn.execute(text(f"ALTER TABLE instruments ADD COLUMN {col} {coltype}"))
