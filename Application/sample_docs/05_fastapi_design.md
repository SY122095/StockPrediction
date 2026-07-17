# ⑤ FastAPI 設計ガイド

作成日：2026-06-02  
バージョン：Python 3.12 / FastAPI 0.133 / PydanticAI

---

## 目次

1. [全体アーキテクチャ](#1-全体アーキテクチャ)
2. [AIエージェント設計（PydanticAI）](#2-aiエージェント設計)
3. [セキュリティ設計（現状からの修正）](#3-セキュリティ設計)
4. [設定管理（pydantic-settings）](#4-設定管理)
5. [データベース接続設計](#5-データベース接続設計)
   - 5.1 接続プール設定
   - [5.2 同期 DB 呼び出しの async ラップ（必須）](#52-同期-db-呼び出しの-async-ラップ必須)
6. [データ取得・加工コード](#6-データ取得加工コード)
7. [ログ設計（structlog）](#7-ログ設計)
8. [テスト設計](#8-テスト設計)
9. [新規アプリ追加手順](#9-新規アプリ追加手順)

---

## 1. 全体アーキテクチャ

```
fxd-intelligence-dev/
├── core/
│   ├── main.py              # FastAPI エントリポイント・ルーター集約
│   ├── db.py                # DB 接続（接続プール）
│   ├── auth/
│   │   ├── router.py        # /api/auth エンドポイント
│   │   ├── service.py       # JWT 発行・検証ロジック
│   │   ├── repository.py    # DB CRUD
│   │   └── models.py        # Pydantic スキーマ
│   ├── top/
│   │   ├── router.py        # /api/app-list エンドポイント
│   │   └── services.py      # アプリ一覧取得ロジック
│   └── configs.yaml         # ※本番では廃止 → Key Vault へ移行
│
├── apps/
│   ├── app01_corporate_summary/
│   │   ├── app.py           # ルーター定義
│   │   ├── api/
│   │   │   ├── generate.py  # 生成 API
│   │   │   └── build_prompt.py
│   │   └── config.py        # アプリ固有設定
│   └── appXX_<name>/        # 新規アプリはこのパターンで追加
│
├── agents/
│   └── project_management/
│       ├── project_agent.py # PydanticAI エージェント定義
│       ├── router.py        # 意図分類ルーター
│       ├── api_router.py    # FastAPI エンドポイント
│       ├── models.py        # 入出力スキーマ
│       └── tools/           # ツール定義
│           ├── project_tools.py
│           ├── hr_tools.py
│           └── document_tools.py
│
└── services/
    ├── azure/
    │   ├── database.py      # SQL 操作
    │   ├── storage.py       # Blob Storage 操作
    │   └── generation.py    # Azure OpenAI 呼び出し
    ├── microsoft/
    │   └── sharepoint.py    # Graph API 操作
    └── utils/
        └── utils.py
```

---

## 2. AIエージェント設計

### 2.1 全体フロー

```
ユーザー入力（POST /api/project-agent/chat）
    ↓
ルーターエージェント（意図分類）
    ├── 案件・タスクに関する質問   → ProjectAgent
    ├── 人材・スキル・稼働状況    → HRAgent
    ├── 規程・文書の検索          → DocumentAgent
    ├── スケジュール・予定確認     → ScheduleAgent
    └── その他                    → GeneralAgent
            ↓
    各エージェントが Tool を呼び出し
            ↓
    SSE（Server-Sent Events）でストリーミング返答
```

### 2.2 ルーターエージェント実装

```python
# agents/project_management/router.py
from pydantic_ai import Agent
from pydantic import BaseModel


class RouterResult(BaseModel):
    intent: str  # "project" | "hr" | "document" | "schedule" | "general"
    confidence: float
    sub_query: str


router_agent = Agent(
    model="azure:gpt-4o",
    result_type=RouterResult,
    system_prompt="""
    ユーザーの質問を以下のカテゴリに分類してください：
    - project: 案件・プロジェクト・タスクに関する質問
    - hr: 人材・スキル・稼働状況に関する質問
    - document: 規程・文書・PDF の検索
    - schedule: スケジュール・会議・予定
    - general: その他の汎用的な質問
    必ず日本語で sub_query を整理してください。
    """,
)
```

### 2.3 案件管理エージェント実装

```python
# agents/project_management/project_agent.py
from pydantic_ai import Agent
from pydantic import BaseModel
from typing import AsyncGenerator

import openai
from pydantic_ai.models.openai import OpenAIModel

from core.config import get_settings
from agents.project_management.tools.project_tools import (
    search_projects_tool,
    get_project_detail_tool,
    search_resources_tool,
    draft_approval_tool,
)
from agents.project_management.tools.document_tools import search_documents_tool
from agents.project_management.tools.hr_tools import get_schedule_tool

cfg = get_settings()


class ProjectContext(BaseModel):
    user_id: int
    project_id: str | None = None
    conversation_history: list[dict] = []


azure_client = openai.AsyncAzureOpenAI(
    api_key=cfg.azure_openai_api_key,
    azure_endpoint=cfg.azure_openai_endpoint,
    api_version=cfg.azure_openai_api_version,
    azure_deployment=cfg.gpt_deployment,
)
model = OpenAIModel(cfg.gpt_deployment, openai_client=azure_client)

project_agent = Agent(
    model=model,
    deps_type=ProjectContext,
    system_prompt="""
    あなたは案件管理の専門 AI アシスタントです。
    以下のツールを使い、案件・リソース・文書情報を横断的に回答してください。
    - 回答は必ず日本語で、事実ベースで行ってください
    - ツールの結果に基づいた回答のみを行い、不確かな情報は「確認できませんでした」と伝えてください
    - 個人情報・機密情報の取り扱いには十分注意してください
    """,
    tools=[
        search_projects_tool,
        get_project_detail_tool,
        search_resources_tool,
        search_documents_tool,
        get_schedule_tool,
        draft_approval_tool,
    ],
)
```

### 2.4 ツール定義例

```python
# agents/project_management/tools/project_tools.py
from pydantic_ai import RunContext
from services.azure.database import get_records_by_filter
from agents.project_management.project_agent import ProjectContext


async def search_projects_tool(
    ctx: RunContext[ProjectContext],
    keyword: str,
    status: str | None = None,
    assignee: str | None = None,
) -> list[dict]:
    """案件名・担当者・ステータスで案件を検索する。"""
    return await get_records_by_filter(
        table="projects",
        keyword=keyword,
        status=status,
        assignee=assignee,
    )


async def get_project_detail_tool(
    ctx: RunContext[ProjectContext],
    project_code: str,
) -> dict:
    """案件コードで案件の詳細情報を取得する。"""
    import asyncio
    results = await asyncio.gather(
        get_project_by_code(project_code),
        get_project_tasks(project_code),
        search_related_documents(project_code),
    )
    project, tasks, docs = results
    return {"project": project, "tasks": tasks, "related_documents": docs}


async def draft_approval_tool(
    ctx: RunContext[ProjectContext],
    project_code: str,
    amount: float,
    purpose: str,
) -> str:
    """稟議書のドラフトテキストを生成する。"""
    from services.azure.generation import generate_text
    prompt = f"""
    以下の情報で稟議書のドラフトを作成してください：
    案件コード: {project_code}
    金額: {amount:,.0f}円
    目的: {purpose}
    
    稟議書フォーマットに従い、件名・目的・金額・承認理由を含めてください。
    """
    return await generate_text(prompt)
```

### 2.5 SSE エンドポイント実装

```python
# agents/project_management/api_router.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from core.auth.service import get_current_user
from agents.project_management.project_agent import project_agent, ProjectContext
from agents.project_management.router import router_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    project_id: str | None = None
    conversation_history: list[dict] = []


@router.post("/chat")
async def project_agent_chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    async def event_stream():
        try:
            # 意図分類
            router_result = await router_agent.run(req.message)
            intent = router_result.data.intent

            # コンテキスト構築
            context = ProjectContext(
                user_id=current_user["id"],
                project_id=req.project_id,
                conversation_history=req.conversation_history,
            )

            # エージェント選択（現状は project_agent に統合）
            agent = project_agent  # 将来的に intent で切り替え

            async with agent.run_stream(
                req.message, deps=context
            ) as result:
                async for chunk in result.stream_text(delta=True):
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx でのバッファリング無効化
        },
    )


@router.get("/projects")
async def list_projects(
    keyword: str = "",
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    from services.azure.database import get_records_by_filter
    return await get_records_by_filter("projects", keyword=keyword, status=status)
```

---

## 3. セキュリティ設計

### 3.1 JWT 認証（httpOnly Cookie 版）

> **注意**: `python-jose` は CVE-2024-33664/33663 により **`PyJWT[crypto]`** に移行済み。  
> インポートは `import jwt`（パッケージ名ではなく標準スタイル）、例外は `jwt.InvalidTokenError` を使用する。

```python
# core/auth/service.py（PyJWT 版）
import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict

from core.config import get_settings

settings = get_settings()
SECRET_KEY = settings.jwt_secret_key       # C-1: 環境変数から取得（32文字以上必須）
ALGORITHM  = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.InvalidTokenError:              # ← JWTError ではなく InvalidTokenError
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    access_token: Optional[str] = Cookie(default=None),
) -> Dict:
    """H-3: httpOnly Cookie を優先し、フォールバックで Bearer ヘッダーを受け付ける。"""
    token = access_token or (bearer.credentials if bearer else None)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_token(token)
    from core.db import get_raw_conn
    # ... ユーザー取得ロジック（core/auth/service.py の実装を参照）
    return payload
```

```python
# ログイン時に httpOnly Cookie を発行
@router.post("/login")
def login(req: LoginRequest, response: Response):
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,   # 本番=True / ステージング HTTP 時は .env で False
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return {"user": user}
```

### 3.2 CORS 設定（環境変数管理）

```python
# core/main.py（修正版）
import os
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Type"],
)
```

### 3.3 SQL インジェクション対策

```python
# services/azure/database.py（修正版）
ALLOWED_TABLES = frozenset({
    "users", "app_list", "projects", "project_tasks", "hr_master",
    "approvals", "audit_log", "chat_sessions", "chat_messages",
    "App701_basic", "App701_transaction", "App701_deposit",
    "App701_contact", "App701_scoring", "allowed_users",
})


def _validate_table(table_name: str) -> None:
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Unauthorized table: {table_name}")


def get_records(table_name: str) -> pd.DataFrame:
    _validate_table(table_name)
    conn = get_raw_conn()
    df = pd.read_sql(f"SELECT * FROM [{table_name}]", conn)
    conn.close()
    return df


def get_records_by_user(table_name: str, user_id: int, ...) -> pd.DataFrame:
    _validate_table(table_name)
    # WHERE 句は必ずパラメータバインディング
    query = f"SELECT * FROM [{table_name}] WHERE user_id = ?"
    ...
```

### 3.4 レート制限（slowapi）

```python
# core/main.py に追加
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# エンドポイントでの使用例
@router.post("/chat")
@limiter.limit("10/minute")  # 1分間に10リクエストまで
async def project_agent_chat(request: Request, ...):
    ...
```

---

## 4. 設定管理

### 4.1 pydantic-settings による設定クラス

```python
# core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str = "2024-02-01"
    gpt_deployment: str = "gpt4o-prod"
    embedding_deployment: str = "embedding-large-prod"

    # Azure SQL
    sql_server: str
    sql_database: str
    sql_driver: str = "ODBC Driver 18 for SQL Server"

    # Azure Storage
    storage_connection: str
    storage_tmp_container: str = "tmp"
    storage_permanent_container: str = "permanent"

    # Azure AI Search
    search_endpoint: str = ""
    search_api_key: str = ""
    search_index_name: str = "project-documents"

    # Microsoft Graph
    graph_client_id: str
    graph_client_secret: str
    graph_tenant_id: str

    # App
    allowed_origins: str = "http://localhost:5173"
    max_tokens: int = 16384
    max_response: int = 3000


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4.2 設定ファイル（configs.yaml）の役割の変更

本番環境では `configs.yaml` を廃止し、すべて環境変数 or Azure Key Vault 経由に移行。

```yaml
# configs.yaml（開発用のみ残す・.gitignore に追加）
# ※本番では一切使用しない
# ※このファイルには実際の API キーを書かない
# ※ローカル開発時は .env ファイルを使用すること

# 設定の説明のみ記載
App:
  max_tokens: 16384
  max_response: 3000
  time_format: '%Y-%m-%d %H:%M:%S'
```

---

## 5. データベース接続設計

### 5.1 接続プール設定

```python
# core/db.py（接続プール設定）— 実装の詳細は実際のファイルを参照
# pyodbc（同期）+ SQLAlchemy エンジン + Managed Identity トークン対応
# pool_size=10 / max_overflow=20 / pool_pre_ping=True / pool_recycle=1800
```

実際の実装は [core/db.py](../core/db.py) を参照。`_build_conn_str()` が接続文字列を組み立て、  
`_get_managed_identity_token()` が Azure AD トークンを取得する。

---

### 5.2 同期 DB 呼び出しの async ラップ（必須）

> **⚠️ 重要**: `pyodbc` は**同期ドライバ**であり、`async def` エンドポイントから直接呼ぶと  
> uvicorn のスレッドプールを占有し、同時接続数が増えたときにレスポンスが詰まる。  
> DB 呼び出しは必ず `asyncio.to_thread()` でオフロードすること。

#### NG パターン（ブロッキング）

```python
@router.get("/items")
async def get_items():
    return get_records("app_list")   # 同期関数を async から直接呼ぶ → スレッド占有
```

#### OK パターン（asyncio.to_thread でオフロード）

```python
import asyncio
from services.azure.database import get_records, get_records_by_user

@router.get("/items")
async def get_items():
    return await asyncio.to_thread(get_records, "app_list")


@router.get("/customer/{cif}")
async def get_customer(cif: str):
    # 複数テーブルを並列取得（asyncio.gather + asyncio.to_thread の組み合わせ）
    basic, txn, deposit = await asyncio.gather(
        asyncio.to_thread(get_records_by_user, "App701_basic",       cif, "cif"),
        asyncio.to_thread(get_records_by_user, "App701_transaction",  cif, "cif"),
        asyncio.to_thread(get_records_by_user, "App701_deposit",      cif, "cif"),
    )
    return {
        "basic":   basic.to_dict(orient="records"),
        "txn":     txn.to_dict(orient="records"),
        "deposit": deposit.to_dict(orient="records"),
    }
```

#### services/azure/database.py の `get_records_parallel()` を活用する

`services/azure/database.py` に `get_records_parallel(*queries)` が実装済み。  
複数テーブルを並列取得する場合はこちらを優先して使用する。

```python
from services.azure.database import get_records_parallel

@router.get("/customer/{cif}")
async def get_customer(cif: str):
    basic, txn, deposit = await get_records_parallel(
        ("App701_basic",       cif, "cif"),
        ("App701_transaction", cif, "cif"),
        ("App701_deposit",     cif, "cif"),
    )
    return {"basic": basic.to_dict(orient="records"), ...}
```

---

## 6. データ取得・加工コード

### 6.1 非同期並列クエリ（N+1 解消）

```python
# apps/app701_business_assistant/app.py（修正版）
import asyncio
from fastapi import Depends
from core.auth.service import get_current_user
from services.azure.database import get_records_by_user_async

@app07_assistant_router.get("/customer/{cif}")
async def get_cust_data(
    cif: str,
    current_user: dict = Depends(get_current_user),
):
    tables = [
        "App701_basic",
        "App701_transaction",
        "App701_deposit",
        "App701_contact",
        "App701_scoring",
    ]
    results = await asyncio.gather(
        *[get_records_by_user_async(t, cif, user_column="cif") for t in tables]
    )
    basic, transaction, deposit, contact, scoring = results

    return {
        "basicInfo":    basic.to_dict(orient="records"),
        "transInfo":    transaction.to_dict(orient="records"),
        "depositInfo":  deposit.to_dict(orient="records"),
        "depositColumns": deposit.columns.tolist(),
        "contactInfo":  contact.to_dict(orient="records"),
        "scoringInfo":  scoring.to_dict(orient="records"),
    }
```

### 6.2 SharePoint からのデータ取得・SQL 同期

```python
# services/microsoft/sharepoint.py
from msgraph import GraphServiceClient
from azure.identity import DefaultAzureCredential
from services.azure.database import upsert_projects

credential = DefaultAzureCredential()
graph_client = GraphServiceClient(credentials=credential)

SITE_ID = "fxd.sharepoint.com:/sites/project-management"
LIST_ID = "案件進捗管理"  # 実際のリスト名に変更が必要

async def sync_projects_from_sharepoint():
    """SharePoint の案件管理リストを SQL に同期する。"""
    items = await graph_client.sites.by_site_id(SITE_ID)\
        .lists.by_list_id(LIST_ID)\
        .items.get()

    projects = []
    for item in items.value:
        fields = item.fields.additional_data
        projects.append({
            "project_code": fields.get("案件コード", ""),
            "name": fields.get("案件名", ""),
            "status": fields.get("ステータス", ""),
            "priority": fields.get("優先度", "Medium"),
            "end_date": fields.get("完了予定日"),
            "sharepoint_item_id": item.id,
        })

    await upsert_projects(projects)
    return len(projects)
```

### 6.3 Embedding 生成・AI Search 登録

```python
# services/project_management/document_processor.py
import tiktoken
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

enc = tiktoken.get_encoding("cl100k_base")
MAX_CHUNK_TOKENS = 512
CHUNK_OVERLAP = 50


def chunk_text(text: str) -> list[str]:
    """テキストを 512 トークン・50 オーバーラップで分割する。"""
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + MAX_CHUNK_TOKENS, len(tokens))
        chunk = enc.decode(tokens[start:end])
        chunks.append(chunk)
        start += MAX_CHUNK_TOKENS - CHUNK_OVERLAP
    return chunks


async def embed_and_index(
    document_id: str,
    text: str,
    source: str,
    project_id: str | None = None,
):
    """テキストを Embedding し AI Search に登録する。"""
    chunks = chunk_text(text)
    docs = []
    for i, chunk in enumerate(chunks):
        embedding = aoai_client.embeddings.create(
            model="embedding-large-prod",
            input=chunk
        ).data[0].embedding

        docs.append({
            "id": f"{document_id}-{i}",
            "content": chunk,
            "embedding": embedding,
            "source": source,
            "project_id": project_id or "",
        })

    search_client.upload_documents(documents=docs)
```

---

## 7. ログ設計

```python
# core/logging.py
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# 使用例
logger.info("project_search", user_id=123, keyword="案件A", results=5)
logger.error("db_error", table="projects", error=str(e))
```

---

## 8. テスト設計

```python
# tests/test_api_router.py
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app


@pytest.mark.asyncio
async def test_chat_endpoint_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/project-agent/chat", json={"message": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_projects_with_auth(auth_token):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": auth_token},
    ) as ac:
        resp = await ac.get("/api/project-agent/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

---

## 9. 新規アプリ追加手順

新しいアプリを追加する場合は **⑦ 新規アプリケーション開発手順** を参照。

### 簡易チェックリスト

- [ ] `apps/appXX_<name>/` ディレクトリ作成
- [ ] `app.py`（ルーター定義）
- [ ] `config.py`（アプリ固有設定）
- [ ] `core/main.py` にルーターを追加
- [ ] `app_list` テーブルにアプリ情報を追加
- [ ] フロントエンド `apps/appXX_<name>/` を作成
- [ ] `App.tsx` にルートを追加
- [ ] テスト作成
