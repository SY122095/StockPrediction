# ⑦ 新規アプリケーション開発手順

作成日：2026-06-02  
対象：FXD Intelligence Platform への新規アプリ追加

---

## 目次

1. [開発フロー全体像](#1-開発フロー全体像)
2. [STEP 1：バックエンド（FastAPI）実装](#2-step-1バックエンド実装)
3. [STEP 2：フロントエンド（React）実装](#3-step-2フロントエンド実装)
4. [STEP 3：DBへのアプリ登録](#4-step-3dbへのアプリ登録)
5. [STEP 4：テスト](#5-step-4テスト)
6. [STEP 5：デプロイ](#6-step-5デプロイ)
7. [命名規則・共通ルール](#7-命名規則共通ルール)
8. [開発チェックリスト](#8-開発チェックリスト)

---

## 1. 開発フロー全体像

```
① 要件定義・設計
    └─ アプリ番号の割り当て（例: app13）
    └─ 機能要件・データ要件の整理
    └─ 使用 AI サービスの確認

② Git ブランチ作成
    └─ dev から feature/app13-<name> を分岐

③ バックエンド実装（FastAPI）
    └─ apps/app13_<name>/ ディレクトリ作成
    └─ app.py, config.py, api/ の実装
    └─ core/main.py へのルーター登録

④ フロントエンド実装（React）
    └─ frontend/src/apps/app13_<name>/ ディレクトリ作成
    └─ ページ・コンポーネント実装
    └─ App.tsx へのルート追加

⑤ DB へのアプリ登録
    └─ app_list テーブルにアプリ情報を INSERT

⑥ テスト
    └─ バックエンド：pytest-asyncio + httpx
    └─ フロントエンド：vitest + @testing-library/react

⑦ PR 作成 → レビュー → dev へマージ

⑧ ステージング動作確認

⑨ main へマージ → 本番デプロイ
```

---

## 2. STEP 1：バックエンド実装

### 2.1 ディレクトリ作成

```bash
# プロジェクトルートで実行
APP_NUM="13"
APP_NAME="your_app_name"

mkdir -p apps/app${APP_NUM}_${APP_NAME}/api
touch apps/app${APP_NUM}_${APP_NAME}/__init__.py
touch apps/app${APP_NUM}_${APP_NAME}/api/__init__.py
touch apps/app${APP_NUM}_${APP_NAME}/app.py
touch apps/app${APP_NUM}_${APP_NAME}/config.py
touch apps/app${APP_NUM}_${APP_NAME}/api/generate.py
```

### 2.2 config.py の実装

`templates/fastapi_app/config.py` をコピーして修正：

```python
# apps/app13_your_name/config.py
from functools import lru_cache
from core.config import get_settings


class AppConfig:
    def __init__(self):
        base = get_settings()
        self.max_tokens = base.max_tokens
        self.gpt_deployment = base.gpt_deployment
        self.app_name = "app13_your_name"
        self.system_prompt = """
        あなたは〇〇のための AI アシスタントです。
        （目的に応じてシステムプロンプトを記述）
        """


@lru_cache
def get_app_settings() -> AppConfig:
    return AppConfig()
```

### 2.3 app.py の実装

`templates/fastapi_app/app.py` をコピーして修正：

```python
# apps/app13_your_name/app.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth.service import get_current_user
from apps.app13_your_name.config import get_app_settings
from apps.app13_your_name.api import generate

app13_router = APIRouter()  # ルーター名はアプリごとにユニークにする
cfg = get_app_settings()


class GenerateRequest(BaseModel):
    prompt: str


@app13_router.get("/health")
async def health_check():
    return {"status": "ok"}


@app13_router.post("/generate")
async def generate_endpoint(
    req: GenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    result = await generate.run(
        prompt=req.prompt,
        user_id=current_user["id"],
        system_prompt=cfg.system_prompt,
    )
    return {"result": result}
```

### 2.4 core/main.py へのルーター追加

```python
# core/main.py に追加
from apps.app13_your_name.app import app13_router

# --- API --- の箇所に追加
app.include_router(app13_router, prefix="/api/your-app-name", tags=["your-app-name"])
```

> **命名規則：** prefix は kebab-case（ハイフン区切り）。例: `/api/project-summary`, `/api/hr-search`

---

## 3. STEP 2：フロントエンド実装

### 3.1 ディレクトリ作成

```bash
cd frontend/src/apps
mkdir -p app13_your_name/pages
mkdir -p app13_your_name/components
mkdir -p app13_your_name/hooks
touch app13_your_name/types.ts
```

### 3.2 ページコンポーネントの作成

`templates/react_app/pages/MainPage.tsx` をコピーして修正：

```typescript
// frontend/src/apps/app13_your_name/pages/MainPage.tsx
// API_ENDPOINT と APP_TITLE を変更する
const APP_TITLE = "〇〇アプリ";
const API_ENDPOINT = "/api/your-app-name/chat";
```

### 3.3 App.tsx へのルート追加

```typescript
// frontend/src/App.tsx
import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";

// 既存のインポートに追加（コード分割）
const App13 = lazy(() => import("./apps/app13_your_name/pages/MainPage"));

// Routes 内に追加
<Route
  path="/app13-your-name"
  element={
    <ProtectedRoute>
      <Suspense fallback={<Loading />}>
        <App13 />
      </Suspense>
    </ProtectedRoute>
  }
/>
```

### 3.4 アプリ一覧への追加（トップページ）

トップページのアプリカード表示は `app_list` テーブルから動的に取得するため、DB に登録するだけで自動的に表示される（STEP 3 参照）。

---

## 4. STEP 3：DBへのアプリ登録

```sql
-- app_list テーブルへの INSERT
INSERT INTO app_list 
    (app_key, name, description, route, icon, required_level, is_active, sort_order)
VALUES
    (
        'app13',                                    -- 内部識別キー
        '〇〇アプリ',                               -- 表示名
        '〇〇を行うための AI サポートアプリです',    -- 説明文
        '/app13-your-name',                        -- フロントエンドルートパス
        'AutoAwesome',                             -- MUI アイコン名
        10,                                        -- 必要アクセスレベル（10=一般）
        1,                                         -- 表示フラグ
        130                                        -- 表示順（アプリ番号 × 10）
    );
```

MUI アイコン名の参考：
- `Chat` - チャット系
- `Description` - 文書系
- `People` - 人材系
- `BarChart` - データ分析系
- `Assignment` - 案件管理系
- `Search` - 検索系
- `AutoAwesome` - AI系

---

## 5. STEP 4：テスト

### 5.1 バックエンドテスト

```python
# tests/test_app13.py
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/your-app-name/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_generate_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/your-app-name/generate", json={"prompt": "test"})
    assert resp.status_code == 401
```

```bash
# テスト実行
source fastapi-env/bin/activate
pytest tests/test_app13.py -v
```

### 5.2 フロントエンドテスト

```typescript
// frontend/src/apps/app13_your_name/__tests__/MainPage.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MainPage from "../pages/MainPage";

test("renders app title", () => {
  render(
    <MemoryRouter>
      <MainPage />
    </MemoryRouter>
  );
  expect(screen.getByText("〇〇アプリ")).toBeInTheDocument();
});
```

```bash
cd frontend
npm run test
```

---

## 6. STEP 5：デプロイ

### 6.1 ローカル確認

```bash
# バックエンド起動
source fastapi-env/bin/activate
uvicorn core.main:app --reload --port 8000

# フロントエンド起動（別ターミナル）
cd frontend
npm run dev
# → http://localhost:5173 で確認
```

### 6.2 本番デプロイ（VM）

```bash
# VM に SSH 接続後
cd /home/azureuser/fxd-intelligence

# 最新コードを取得
git pull origin main

# Python パッケージ更新（必要な場合）
source fastapi-env/bin/activate
pip install -r requirements.txt

# フロントエンドビルド
cd frontend
npm ci && npm run build
cd ..

# FastAPI 再起動
sudo systemctl restart fxd-platform

# ログで起動確認
sudo journalctl -u fxd-platform -n 20 --no-pager
```

### 6.3 GitHub Actions での自動デプロイ

`main` ブランチへのマージ後に自動でデプロイが走る（`04_git_github.md` の CI/CD 設定参照）。

---

## 7. 命名規則・共通ルール

| 項目 | 規則 | 例 |
|------|------|-----|
| アプリ番号 | 3桁数字（01〜999） | `app13`, `app701` |
| バックエンドルーター変数名 | `app{番号}_router` | `app13_router` |
| API prefix | `/api/{kebab-case}` | `/api/hr-search` |
| フロントエンドルートパス | `/{kebab-case}` | `/hr-search` |
| フロントエンドフォルダ | `app{番号}_{snake_case}` | `app13_hr_search` |
| Pydantic スキーマ | UpperCamelCase + `Request/Response` | `GenerateRequest`, `SearchResponse` |
| エンドポイント | snake_case 関数名 | `generate_endpoint`, `list_projects` |
| コンポーネント | UpperCamelCase | `MainPage`, `ChatHistory` |
| カスタムフック | `use` + UpperCamelCase | `useSSEChat`, `useProjects` |

### 絶対に守るルール

1. **シークレット情報はコードに書かない** → 環境変数 or Key Vault
2. **すべての API エンドポイントに認証を付ける** → `Depends(get_current_user)`
3. **テーブル名はホワイトリスト検証する** → `_validate_table()` を必ず呼ぶ
4. **SSE は POST + Cookie 認証で実装する** → `@microsoft/fetch-event-source` 使用
5. **Markdown 表示は react-markdown を使う** → `dangerouslySetInnerHTML` 禁止
6. **configs.yaml にシークレットを書かない** → `.env` + `pydantic-settings`
7. **`async def` エンドポイントから同期 DB 関数を直接呼ばない** → `asyncio.to_thread()` でラップ（`05_fastapi_design.md` §5.2 参照）
8. **新規テーブルを追加したら `core/models.py` も更新する** → Alembic autogenerate のために必須（`03_database_design.md` §7 参照）

---

## 8. 開発チェックリスト

### バックエンド

- [ ] `apps/appXX_<name>/` ディレクトリ作成完了
- [ ] `config.py` でシステムプロンプトと設定を定義
- [ ] `app.py` でルーター定義（変数名はユニーク）
- [ ] すべてのエンドポイントに `Depends(get_current_user)` を付与
- [ ] テーブル名アクセスに `_validate_table()` を使用（`services/azure/database.py` の `ALLOWED_TABLES` にも追加）
- [ ] `async def` エンドポイントの DB 呼び出しは `asyncio.to_thread()` でラップ
- [ ] `core/main.py` にルーター追加
- [ ] `/health` エンドポイント追加（監視用）
- [ ] `tests/test_appXX.py` 作成・パス確認

### フロントエンド

- [ ] `frontend/src/apps/appXX_<name>/` ディレクトリ作成完了
- [ ] `App.tsx` にルート追加（`React.lazy` でコード分割）
- [ ] `ProtectedRoute` でラップ（認証必須）
- [ ] SSE は `@microsoft/fetch-event-source` を使用（GET EventSource 禁止）
- [ ] Markdown は `react-markdown` を使用（`dangerouslySetInnerHTML` 禁止）
- [ ] `axios.defaults.withCredentials = true` が設定済みか確認
- [ ] テスト作成・パス確認

### DB

- [ ] `app_list` テーブルへのアプリ情報 INSERT
- [ ] 新規テーブルが必要な場合は `core/models.py` にクラスを追加
- [ ] `services/azure/database.py` の `ALLOWED_TABLES` に追加
- [ ] `alembic revision --autogenerate -m "add_appXX_tables"` でマイグレーション生成・適用

### デプロイ前

- [ ] ローカルで動作確認完了
- [ ] `git diff` でシークレットが含まれていないか確認
- [ ] PR 作成・レビュー完了
- [ ] `dev` → `main` マージ後に本番動作確認
