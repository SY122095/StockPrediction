from fastapi import FastAPI, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Base, engine, get_db
from models.schemas import AdminStatusOut
from routers import events, macro, predictions, sentiment, stocks, supply_demand

# テーブル作成
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="株価予測システム REST API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なオリジンに限定すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(predictions.router)
app.include_router(macro.router)
app.include_router(sentiment.router)
app.include_router(events.router)
app.include_router(supply_demand.router)


# ---- ルート ----

@app.get("/", tags=["root"])
def root():
    return {"app": settings.app_name, "version": settings.version, "status": "running"}


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok"}


# ---- 管理エンドポイント ----

@app.post("/api/v1/admin/refresh", tags=["admin"])
def admin_refresh(
    start: str = Query("2022-01-01", description="データ取得開始日 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    from services.data_service import refresh_all
    result = refresh_all(db, start=start)
    return {"status": "ok", "inserted": result}


@app.post("/api/v1/admin/train", tags=["admin"])
def admin_train(
    asset_class: str = Query("equity_jp", description="equity_jp | crypto"),
    target: str = Query("fwd_ret_5d", description="予測ターゲット"),
    n_splits: int = Query(5, ge=3, le=10),
    db: Session = Depends(get_db),
):
    from services.prediction_service import train_model
    try:
        result = train_model(db, asset_class=asset_class, target=target, n_splits=n_splits)
        return {"status": "ok", **result}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/admin/predict", tags=["admin"])
def admin_predict(
    asset_class: str = Query("equity_jp"),
    target: str = Query("fwd_ret_5d"),
    db: Session = Depends(get_db),
):
    from services.prediction_service import run_prediction
    n = run_prediction(db, asset_class=asset_class, target=target)
    return {"status": "ok" if n > 0 else "error", "predictions_saved": n}


@app.get("/api/v1/admin/status", tags=["admin"], response_model=AdminStatusOut)
def admin_status():
    """外部データソースのAPIキー設定状況 (キー自体は返さない)。"""
    return AdminStatusOut(
        fred_configured=settings.is_configured("fred_api_key"),
        jquants_configured=settings.is_configured("jquants_api_key"),
    )


@app.post("/api/v1/admin/refresh-macro", tags=["admin"])
def admin_refresh_macro(
    start: str = Query("2022-01-01"),
    db: Session = Depends(get_db),
):
    from services.macro_service import refresh_macro
    result = refresh_macro(db, start=start)
    return {"status": "ok", **result}


@app.post("/api/v1/admin/refresh-sentiment", tags=["admin"])
def admin_refresh_sentiment(db: Session = Depends(get_db)):
    from services.sentiment_service import refresh_sentiment
    result = refresh_sentiment(db)
    return {"status": "ok", **result}


@app.post("/api/v1/admin/refresh-events", tags=["admin"])
def admin_refresh_events(
    asset_class: str = Query("equity_jp"),
    db: Session = Depends(get_db),
):
    from services.event_service import refresh_earnings
    n = refresh_earnings(db, asset_class=asset_class)
    return {"status": "ok", "earnings_saved": n}


@app.post("/api/v1/admin/refresh-supply-demand", tags=["admin"])
def admin_refresh_supply_demand(db: Session = Depends(get_db)):
    from services.supply_demand_service import refresh_supply_demand
    result = refresh_supply_demand(db)
    return {"status": "ok", **result}
