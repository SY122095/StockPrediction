# ⑧ その他留意点・設定・仕様

作成日：2026-06-02

---

## 目次

1. [設定ファイル（YAML）管理](#1-設定ファイルyaml管理)
2. [Python バージョン管理](#2-python-バージョン管理)
3. [ディレクトリ構造（最適化版）](#3-ディレクトリ構造最適化版)
4. [セキュリティ対応優先度一覧](#4-セキュリティ対応優先度一覧)
5. [依存パッケージ管理](#5-依存パッケージ管理)
6. [各種仕様書](#6-各種仕様書)
7. [実装前確認事項](#7-実装前確認事項)

---

## 1. 設定ファイル（YAML）管理

### 1.1 YAML ファイルの役割分担

| ファイル | 用途 | Git 管理 | 環境 |
|---------|------|---------|------|
| `core/configs.yaml` | 設定のデフォルト値・構造定義のみ（シークレット禁止） | ✅ 管理する | 全環境 |
| `.env` | ローカル開発用シークレット（Key Vault URI 等） | ❌ .gitignore | ローカル |
| `.env.example` | .env のサンプル（実際の値は書かない） | ✅ 管理する | — |
| `local.settings.json` | Azure Functions のローカル設定 | ❌ .gitignore | ローカル |
| `azure-functions/*/host.json` | Azure Functions のホスト設定 | ✅ 管理する | 全環境 |

### 1.2 configs.yaml（本番対応版）

シークレット情報を一切含めず、設定構造の定義のみにする。

```yaml
# core/configs.yaml（シークレットなし版）
# 実際の値は環境変数または Key Vault から取得する

App:
  max_tokens: 16384
  max_response: 3000
  time_format: '%Y-%m-%d %H:%M:%S'
  summary_num: 3

# 以下の設定は環境変数で上書きされる
# AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, etc.
```

### 1.3 .env.example（テンプレート）

```dotenv
# .env.example（Git 管理 OK）
# 実際の値を入れた .env を作成すること（.gitignore 済み）

# Key Vault（本番はこれだけで OK）
KEY_VAULT_URL=https://kv-fxd-prod.vault.azure.net/
AZURE_CLIENT_ID=

# ローカル開発時のみ直接設定（本番は Key Vault 経由）
JWT_SECRET_KEY=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-02-01
GPT_DEPLOYMENT=gpt4o-prod
EMBEDDING_DEPLOYMENT=embedding-large-prod

SQL_SERVER=fxd-platform.database.windows.net
SQL_DATABASE=ai-platform-db

STORAGE_CONNECTION=
STORAGE_TMP_CONTAINER=tmp
STORAGE_PERMANENT_CONTAINER=permanent

GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
GRAPH_TENANT_ID=

ALLOWED_ORIGINS=http://localhost:5173
```

---

## 2. Python バージョン管理

### 2.1 使用バージョン

**Python 3.12.x**（3.12系列）を使用する。

理由：
- pydantic-ai の最新サポート
- 型ヒントの強化（`str | None` 等）
- 非同期機能の改善
- パフォーマンス向上（CPython 3.12 は 3.11 比 5〜10% 高速）

### 2.2 バージョン固定設定

```
# .python-version（pyenv 使用時）
3.12.10
```

```toml
# pyproject.toml（将来移行時）
[tool.poetry]
name = "fxd-intelligence"
version = "1.0.0"
description = "FXD AI Intelligence Platform"

[tool.poetry.dependencies]
python = ">=3.12,<3.13"
fastapi = "^0.133"
pydantic-ai = ">=0.0.14"
pydantic-settings = ">=2.3"
```

### 2.3 requirements.txt の整理

```text
# requirements.txt（本番用・整理版）

# Web フレームワーク
fastapi==0.133.1
uvicorn[standard]==0.41.0

# 設定管理
pydantic-settings>=2.3.0

# 認証
PyJWT[crypto]>=2.8.0          # python-jose は CVE-2024-33664/33663 のため PyJWT へ移行
passlib[bcrypt]==1.7.4

# データベース
pyodbc==5.1.0
sqlalchemy==2.0.41
pandas==2.2.3

# Azure SDK
azure-identity>=1.16.0
azure-keyvault-secrets>=4.8.0
azure-storage-blob>=12.20.0
azure-ai-documentintelligence>=1.0.0
azure-search-documents>=11.4.0
openai>=1.40.0

# AI エージェント
pydantic-ai>=0.0.14
langchain==1.2.10
langgraph==1.0.9

# Microsoft Graph
msgraph-sdk>=1.0.0

# ドキュメント処理
pypdfium2>=4.28.0
python-docx>=1.1.0
python-pptx>=0.6.23
openpyxl>=3.1.0
tiktoken>=0.7.0

# セキュリティ
slowapi>=0.1.9
nh3>=0.2.14               # bleach は 2023年サンセット宣言のため nh3 へ移行

# ログ
structlog>=24.0.0

# テスト
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0

# ML/Data（必要なアプリのみ）
numpy>=1.26.0
torch>=2.0.0
transformers>=4.40.0
```

---

## 3. ディレクトリ構造（最適化版）

現状のディレクトリ構造を評価した結果、**基本的な構造は適切**。以下の最適化案を推奨。

```
fxd-intelligence/
├── core/                          # フレームワーク中核
│   ├── main.py                    # FastAPI エントリポイント
│   ├── config.py                  # ★追加: pydantic-settings 設定クラス
│   ├── db.py                      # DB 接続（接続プール設定済み）
│   ├── logging.py                 # ★追加: structlog 設定
│   ├── auth/
│   │   ├── router.py
│   │   ├── service.py             # JWT 認証（httpOnly Cookie版に修正）
│   │   ├── repository.py
│   │   └── models.py
│   ├── top/
│   │   ├── router.py              # ★修正: Depends(get_current_user) 追加
│   │   └── services.py
│   └── configs.yaml               # ★修正: シークレットなし版

├── apps/                          # 機能アプリ（各アプリ独立）
│   ├── app01_corporate_summary/
│   ├── app02_ai_chat/
│   ├── app04_regulation_exploration/
│   ├── app08_document_summary/
│   ├── app10_partner_list/
│   ├── app12_project_management/
│   ├── app701_business_assistant/
│   └── app999_app_sample/         # ★サンプルアプリ（開発参考用）

├── agents/                        # ★追加: PydanticAI エージェント
│   └── project_management/
│       ├── project_agent.py
│       ├── router.py
│       ├── api_router.py
│       ├── models.py
│       └── tools/
│           ├── project_tools.py
│           ├── hr_tools.py
│           └── document_tools.py

├── services/                      # 共有サービス
│   ├── azure/
│   │   ├── database.py            # ★修正: テーブル名ホワイトリスト追加
│   │   ├── storage.py
│   │   └── generation.py
│   ├── microsoft/
│   │   └── sharepoint.py
│   └── utils/
│       └── utils.py

├── frontend/                      # React フロントエンド
│   ├── src/
│   │   ├── theme/                 # テーマ設定
│   │   ├── auth/                  # 認証関連
│   │   ├── apps/                  # 各アプリ UI
│   │   ├── components/            # ★追加: 共通コンポーネント
│   │   │   └── MarkdownRenderer.tsx
│   │   ├── hooks/                 # ★追加: 共通カスタムフック
│   │   │   └── useSSEChat.ts
│   │   ├── lib/                   # ★追加: axios インスタンス等
│   │   │   └── api.ts
│   │   ├── main.tsx
│   │   └── App.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts

├── tests/                         # ★追加: テストディレクトリ
│   ├── conftest.py
│   └── test_*.py

├── .github/                       # ★追加: GitHub Actions
│   └── workflows/
│       ├── deploy.yml
│       └── security-scan.yml

├── requirements.txt               # Python 依存パッケージ
├── .env.example                   # ★追加: 環境変数テンプレート
├── .gitignore                     # ★修正: configs.yaml 等を追加
└── fastapi-env/                   # 仮想環境（Git 管理外）
```

### 変更不要（現状で問題なし）の部分

- `apps/` の番号付きディレクトリ構造 → 識別しやすく適切
- `services/azure/`, `services/microsoft/` の分離 → 責務が明確
- `frontend/src/apps/` の構造 → バックエンドと対応していて一貫性あり

---

## 4. セキュリティ対応優先度一覧

`analysis.md` および `gaps.md` を統合した対応表。

| 優先度 | 問題 | 場所 | 対応方法 | 完了基準 |
|--------|------|------|---------|---------|
| 🔴 C-1 | SECRET_KEY がハードコード | `core/auth/service.py` | 環境変数 `JWT_SECRET_KEY` 必須化 | 起動時エラーで気付ける状態 |
| 🔴 C-2 | JWT が URL クエリパラメータに露出 | `app701/.../Top.tsx` | `@microsoft/fetch-event-source` + POST | SSE が POST で動作確認 |
| 🔴 C-3 | CORS が全オリジン許可 | `core/main.py` | 環境変数 `ALLOWED_ORIGINS` で管理 | 本番ドメインのみ許可 |
| 🔴 C-4 | XSS（dangerouslySetInnerHTML） | `app701/.../Top.tsx` | `react-markdown` に移行 | script タグが実行されない |
| 🔴 C-5 | configs.yaml に平文シークレット | `core/configs.yaml` | Azure Key Vault へ移行 | Git 履歴からも削除 |
| 🟠 H-1 | SQL インジェクション（テーブル名） | `services/azure/database.py` | ホワイトリスト検証追加 | 未許可テーブルでエラー発生 |
| 🟠 H-2 | JWT を localStorage に保存 | `auth/pages/LoginPage.tsx` | httpOnly Cookie へ移行 | localStorage にトークンなし |
| 🟠 H-3 | 認証なしエンドポイント | `core/top/router.py` | `Depends(get_current_user)` 追加 | 未認証で 401 返却 |
| 🟠 H-4 | 登録制限がハードコード | `core/auth/router.py` | `allowed_users` テーブルで管理 | DB から判定 |
| 🟠 H-5 | Azure Functions 認証未設定 | `azure-functions/*/function_app.py` | Managed Identity + Admin レベル | パスワードレス認証 |
| 🟡 M-1 | グローバル変数での認証管理 | `auth/useAuth.ts` | Zustand ストアへ移行 | React DevTools で状態確認可能 |
| 🟡 M-2 | チャット送信が GET メソッド | API 全般 | POST + ボディに変更 | URL にメッセージ内容が露出しない |
| 🟡 M-3 | N+1 問題（直列クエリ） | `app701/app.py` | `asyncio.gather` で並列化 | レスポンスタイムの改善 |
| 🟡 M-4 | DB 接続プール未設定 | `core/db.py` | pool_size=10 等を設定 | 同時接続でエラーなし |
| 🟡 M-5 | df.to_html() のスタイル衝突 | `app701/app.py` | JSON + MUI DataGrid に変更 | テーブル表示が統一 |

---

## 5. 依存パッケージ管理

### 5.1 追加が必要なパッケージ

```bash
# Python（バックエンド）
pip install \
  pydantic-ai>=0.0.14 \
  pydantic-settings>=2.3.0 \
  azure-search-documents>=11.4.0 \
  azure-keyvault-secrets>=4.8.0 \
  msgraph-sdk>=1.0.0 \
  structlog>=24.0.0 \
  slowapi>=0.1.9 \
  python-docx>=1.1.0 \
  python-pptx>=0.6.23 \
  tiktoken>=0.7.0 \
  pytest-asyncio>=0.23.0

# npm（フロントエンド）
npm install \
  @microsoft/fetch-event-source \
  react-markdown \
  remark-gfm \
  zustand \
  @tanstack/react-query \
  react-hook-form \
  zod \
  @hookform/resolvers

npm install -D \
  vitest \
  @testing-library/react \
  @testing-library/jest-dom \
  jsdom
```

### 5.2 削除可能なパッケージ

| パッケージ | 削除理由 | 代替 |
|-----------|---------|------|
| `marked` | XSS リスク | `react-markdown` |
| `@types/marked` | marked 削除に伴い不要 | — |
| `python-jose[cryptography]` | **CVE-2024-33664/33663**（ECDSA キー混同・アルゴリズム混同の脆弱性）・メンテナンス停滞 | `PyJWT[crypto]>=2.8.0` |
| `bleach` | 2023年プロジェクトサンセット宣言・メンテナンス終了 | `nh3>=0.2.14` |

---

## 6. 各種仕様書

### 6.1 API 仕様（エンドポイント一覧）

| メソッド | エンドポイント | 認証 | 説明 |
|--------|-------------|------|------|
| POST | `/api/auth/login` | 不要 | ログイン（Cookie 発行） |
| POST | `/api/auth/logout` | Cookie | ログアウト（Cookie 削除） |
| POST | `/api/auth/register` | 不要 | ユーザー登録（ホワイトリスト確認） |
| GET | `/api/auth/me` | Cookie | 現在のユーザー情報取得 |
| GET | `/api/app-list/apps` | Cookie | アプリ一覧取得 |
| POST | `/api/corporate-summary-app/generate` | Cookie | 企業概要生成 |
| POST | `/api/chat-app/chat` | Cookie | AI チャット |
| POST | `/api/regulation-exploration-app/search` | Cookie | 規程検索 |
| POST | `/api/pdf-summary/generate` | Cookie | PDF 要約 |
| GET | `/api/partner-list/partners` | Cookie | パートナー一覧 |
| POST | `/api/project-management/generate` | Cookie | プロジェクト管理 |
| POST | `/api/business-assistant07/chat` | Cookie | 業務支援チャット（修正版） |
| GET | `/api/business-assistant07/customer/{cif}` | Cookie | 顧客詳細取得 |
| POST | `/api/project-agent/chat` | Cookie | 案件管理エージェント（SSE） |
| GET | `/api/project-agent/projects` | Cookie | 案件一覧 |
| GET | `/api/project-agent/projects/{id}` | Cookie | 案件詳細 |
| GET | `/api/project-agent/resources` | Cookie | リソース検索 |
| POST | `/api/project-agent/draft-approval` | Cookie | 稟議書ドラフト生成 |

### 6.2 アクセスレベル定義

| レベル | 対象 | アクセス可能アプリ |
|--------|------|----------------|
| 0 | システム管理者 | 全アプリ + 管理機能 |
| 5 | 部門管理者 | 全アプリ |
| 10 | 一般ユーザー | required_level ≤ 10 のアプリ |
| 20 | 閲覧専用 | required_level ≤ 20 のアプリ |

### 6.3 Azure Functions 仕様

| Function 名 | トリガー | スケジュール（UTC） | JST 換算 | 役割 |
|------------|---------|----------------|---------|------|
| `fn_sync_project_sheet` | Timer | `0 0 * * *` | 毎日 9:00 | SharePoint → SQL 案件同期 |
| `fn_sync_approval_docs` | Timer | `30 0 * * *` | 毎日 9:30 | 稟議書情報同期 |
| `fn_sync_hr_master` | Timer | `0 23 * * 0` | 毎週月曜 8:00 | 人事マスタ更新 |
| `fn_embed_documents` | Blob Trigger | 随時 | — | Embedding 生成・AI Search 登録 |
| `fn_score_ai` | Timer | `0 17 1 * *` | 毎月2日 2:00 | AI スコアリング |
| `fn_alert_deadline` | Timer | `0 23 * * *` | 毎日 8:00 | 期日アラート Teams 通知 |

### 6.4 用語定義

| 用語 | 定義 |
|------|------|
| CIF | Customer Information File の略。顧客識別番号 |
| SSE | Server-Sent Events。サーバーからクライアントへのストリーミング通信 |
| RAG | Retrieval-Augmented Generation。ベクトル検索で文書を取得してAIに渡す手法 |
| Embedding | テキストをベクトル（数値の配列）に変換したもの。類似検索に使用 |
| PydanticAI | Python の型安全な AI エージェントフレームワーク |
| Graph API | Microsoft 365 のデータにアクセスするための API |
| Managed Identity | Azure リソース用の Azure AD ID。秘密鍵なしで他 Azure サービスへ認証できる |
| Key Vault | Azure のシークレット管理サービス |
| MERGE 文 | SQL の UPSERT（INSERT or UPDATE）操作。SharePoint データの差分同期に使用 |

---

---

## 7. 実装前確認事項

実装を開始する前に以下を必ず確認すること。バージョンやモデル名は時期によって変わるため、ドキュメントの記載値をそのまま使わず都度検証する。

### 7.1 パッケージバージョン確認

| パッケージ | ドキュメント記載値 | 確認コマンド | 注意 |
|-----------|-----------------|------------|------|
| `fastapi` | `0.133.1` | `pip index versions fastapi` | 実在するバージョンかを確認 |
| `uvicorn[standard]` | `0.41.0` | `pip index versions uvicorn` | 実在するバージョンかを確認 |
| `pydantic-ai` | `>=0.0.14` | `pip index versions pydantic-ai` | API 変更が多い。changelog を必ず確認 |
| `PyJWT` | `>=2.8.0` | `pip index versions PyJWT` | `python-jose` から移行済み |
| `nh3` | `>=0.2.14` | `pip index versions nh3` | `bleach` から移行済み |
| `azure-search-documents` | `>=11.4.0` | `pip index versions azure-search-documents` | ベクトル検索 API 変更に注意 |

```bash
# インストール可能な最新バージョン確認
pip index versions fastapi
pip index versions uvicorn

# ドライランで競合確認
pip install fastapi uvicorn[standard] --dry-run
```

### 7.2 Azure OpenAI モデル名確認

デプロイ名（`gpt4o-prod` 等）はリソースごとに異なる。コードに直書きせず `core/config.py` の設定値から参照すること。

| 設定値 | デフォルト値 | 確認方法 |
|--------|------------|---------|
| `gpt_deployment` | `gpt4o-prod` | Azure Portal → OpenAI → モデル デプロイ一覧 |
| `embedding_deployment` | `embedding-large-prod` | 同上 |
| `api_version` | `2024-02-01` | Azure OpenAI リリースノートで最新 GA バージョンを確認 |

```bash
# デプロイ一覧確認（CLI）
az cognitiveservices account deployment list \
  --name aoai-fxd-prod \
  --resource-group rg-fxd-platform \
  --output table
```

> **GPT-5 / o シリーズへの移行時：** モデル名・API バージョン・`max_tokens` の上限が変わる可能性がある。新モデルをデプロイしたら `core/config.py` の `gpt_deployment`・`max_tokens` を更新し、ステージング環境で動作確認してから本番反映すること。

### 7.3 PydanticAI の API 変更への注意

PydanticAI はバージョン間での API 変更が多い。`pydantic-ai` を更新する際は必ず [公式 Changelog](https://ai.pydantic.dev/changelog/) を確認すること。

特に変更されやすい箇所：
- `Agent` の `model` 引数の形式（`"openai:gpt-4o"` 等のプレフィックス）
- `RunContext` の型定義
- `run_stream()` の戻り値・メソッド名

```bash
# 更新前に差分を確認
pip install pydantic-ai --dry-run
pip show pydantic-ai  # 現在のバージョン確認
```

### 7.4 Alembic `env.py` の DATABASE_URL 変換

Azure SQL Database を使用する場合、非同期 URL を同期 URL に変換している箇所は URL フォーマットが変わると壊れる可能性がある。

```python
# 現在の実装（脆弱）
database_url = os.environ.get("DATABASE_URL", "").replace(
    "mssql+aioodbc://", "mssql+pyodbc://"
)

# より堅牢な実装
from urllib.parse import urlparse
url = os.environ.get("DATABASE_URL", "")
if "+aioodbc" in url:
    url = url.replace("+aioodbc", "+pyodbc", 1)
config.set_main_option("sqlalchemy.url", url)
```

### 7.5 Azure Functions の `requirements.txt`

各 Azure Functions ディレクトリの `requirements.txt` は、その関数が実際に使うパッケージのみを最小構成で記載すること。VM 全体の `requirements.txt` をそのまま流用しない。

```text
# azure-functions/fn_embed_documents/requirements.txt（例）
azure-identity>=1.16.0
azure-keyvault-secrets>=4.8.0
azure-storage-blob>=12.20.0
azure-search-documents>=11.4.0
openai>=1.40.0
tiktoken>=0.7.0
```

---

*このドキュメントは FXD Intelligence Platform の運用・開発に関わるすべての関係者向けに作成しました。*  
*内容の更新が必要な場合は PR を通じて変更してください。*
