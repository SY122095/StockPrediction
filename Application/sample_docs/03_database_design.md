# ③ データベース設計ガイド

作成日：2026-06-02  
対象DB：Azure SQL Database（SQL Server 互換）

---

## 目次

1. [テーブル設計](#1-テーブル設計)
2. [データソース詳細](#2-データソース詳細)
3. [更新頻度と方法](#3-更新頻度と方法)
4. [ER図（概念）](#4-er図概念)
5. [インデックス設計](#5-インデックス設計)
6. [テーブル初期化スクリプト](#6-テーブル初期化スクリプト)
7. [SQLAlchemy ORM モデル定義](#7-sqlalchemy-ormモデル定義)
8. [Alembic マイグレーション](#8-alembicマイグレーション)

---

## 1. テーブル設計

### 1.1 認証・ユーザー管理

#### `users`（ユーザーマスタ）

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INT | PK, IDENTITY | ユーザーID |
| email | NVARCHAR(255) | UNIQUE, NOT NULL | メールアドレス（ログインID） |
| username | NVARCHAR(100) | NOT NULL | 表示名 |
| password_hash | NVARCHAR(255) | NOT NULL | bcrypt ハッシュ |
| user_level | INT | NOT NULL, DEFAULT 10 | アクセスレベル（0=管理者, 10=一般） |
| is_active | BIT | NOT NULL, DEFAULT 1 | アカウント有効フラグ |
| created_at | DATETIME2 | DEFAULT GETDATE() | 作成日時 |
| updated_at | DATETIME2 | DEFAULT GETDATE() | 更新日時 |

```sql
CREATE TABLE users (
    id           INT            IDENTITY(1,1) PRIMARY KEY,
    email        NVARCHAR(255)  NOT NULL UNIQUE,
    username     NVARCHAR(100)  NOT NULL,
    password_hash NVARCHAR(255) NOT NULL,
    user_level   INT            NOT NULL DEFAULT 10,
    is_active    BIT            NOT NULL DEFAULT 1,
    created_at   DATETIME2      DEFAULT GETDATE(),
    updated_at   DATETIME2      DEFAULT GETDATE()
);
```

#### `allowed_users`（登録許可ホワイトリスト）

現状コードでメールアドレスがハードコードされている部分を DB 管理に移行するためのテーブル。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| email | NVARCHAR(255) | PK | 許可メールアドレス |
| user_level | INT | NOT NULL | 付与するアクセスレベル |
| is_active | BIT | NOT NULL, DEFAULT 1 | 許可フラグ |
| note | NVARCHAR(500) | NULL | 備考 |

```sql
CREATE TABLE allowed_users (
    email      NVARCHAR(255) PRIMARY KEY,
    user_level INT           NOT NULL,
    is_active  BIT           NOT NULL DEFAULT 1,
    note       NVARCHAR(500) NULL
);
```

---

### 1.2 アプリ管理

#### `app_list`（アプリ一覧）

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INT | PK, IDENTITY | アプリID |
| app_key | NVARCHAR(50) | UNIQUE, NOT NULL | 内部識別キー（例: app01） |
| name | NVARCHAR(200) | NOT NULL | 表示名 |
| description | NVARCHAR(1000) | NULL | 説明文 |
| route | NVARCHAR(200) | NOT NULL | フロントエンドのルートパス |
| icon | NVARCHAR(100) | NULL | アイコン名（MUI Icons） |
| required_level | INT | NOT NULL, DEFAULT 10 | 必要アクセスレベル |
| is_active | BIT | NOT NULL, DEFAULT 1 | 表示フラグ |
| sort_order | INT | NOT NULL, DEFAULT 100 | 表示順 |

```sql
CREATE TABLE app_list (
    id             INT           IDENTITY(1,1) PRIMARY KEY,
    app_key        NVARCHAR(50)  NOT NULL UNIQUE,
    name           NVARCHAR(200) NOT NULL,
    description    NVARCHAR(1000) NULL,
    route          NVARCHAR(200) NOT NULL,
    icon           NVARCHAR(100) NULL,
    required_level INT           NOT NULL DEFAULT 10,
    is_active      BIT           NOT NULL DEFAULT 1,
    sort_order     INT           NOT NULL DEFAULT 100
);
```

---

### 1.3 業務支援アシスタント（App701）

#### `App701_basic`（顧客基本情報）

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INT | PK, IDENTITY | レコードID |
| cif | NVARCHAR(20) | NOT NULL | 顧客識別番号 |
| name | NVARCHAR(200) | NOT NULL | 顧客名 |
| age | INT | NULL | 年齢 |
| address | NVARCHAR(500) | NULL | 住所 |
| phone | NVARCHAR(50) | NULL | 電話番号 |
| email | NVARCHAR(255) | NULL | メールアドレス |
| user_id | INT | FK → users.id | 担当者ID |
| is_active | BIT | DEFAULT 1 | 有効フラグ |
| created_at | DATETIME2 | DEFAULT GETDATE() | 作成日時 |

#### `App701_transaction`（取引情報）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| cif | NVARCHAR(20) | 顧客CIF |
| transaction_date | DATE | 取引日 |
| transaction_type | NVARCHAR(50) | 取引種別 |
| amount | DECIMAL(18,2) | 金額 |
| description | NVARCHAR(500) | 摘要 |
| is_active | BIT | 有効フラグ |

#### `App701_deposit`（普通預金明細）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| cif | NVARCHAR(20) | 顧客CIF |
| account_number | NVARCHAR(50) | 口座番号 |
| balance | DECIMAL(18,2) | 残高 |
| transaction_date | DATE | 取引日 |
| debit | DECIMAL(18,2) | 出金額 |
| credit | DECIMAL(18,2) | 入金額 |

#### `App701_contact`（交渉履歴）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| cif | NVARCHAR(20) | 顧客CIF |
| contact_date | DATETIME2 | 交渉日時 |
| contact_type | NVARCHAR(50) | 交渉種別（訪問/電話/メール） |
| content | NVARCHAR(MAX) | 交渉内容 |
| staff_id | INT | 担当者ID |
| is_active | BIT | 有効フラグ |

#### `App701_scoring`（AIスコアリング）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| cif | NVARCHAR(20) | 顧客CIF |
| score | DECIMAL(5,2) | AIスコア（0〜100） |
| risk_level | NVARCHAR(20) | リスクレベル（Low/Medium/High） |
| scored_at | DATETIME2 | スコアリング日時 |
| model_version | NVARCHAR(50) | 使用モデルバージョン |

---

### 1.4 案件管理（App12 / PydanticAI エージェント）

#### `projects`（案件マスタ）

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INT | PK, IDENTITY | 案件ID |
| project_code | NVARCHAR(50) | UNIQUE, NOT NULL | 案件コード |
| name | NVARCHAR(500) | NOT NULL | 案件名 |
| status | NVARCHAR(50) | NOT NULL | ステータス（進行中/完了/保留） |
| priority | NVARCHAR(20) | NOT NULL | 優先度（High/Medium/Low） |
| start_date | DATE | NULL | 開始日 |
| end_date | DATE | NULL | 終了日（予定） |
| actual_end_date | DATE | NULL | 実際の終了日 |
| budget | DECIMAL(18,2) | NULL | 予算 |
| owner_id | INT | FK → users.id | 案件責任者 |
| department | NVARCHAR(100) | NULL | 担当部署 |
| description | NVARCHAR(MAX) | NULL | 案件概要 |
| is_active | BIT | DEFAULT 1 | 有効フラグ |
| created_at | DATETIME2 | DEFAULT GETDATE() | 作成日時 |
| updated_at | DATETIME2 | DEFAULT GETDATE() | 更新日時 |
| sharepoint_item_id | NVARCHAR(100) | NULL | SharePoint リスト ItemId |

```sql
CREATE TABLE projects (
    id                  INT            IDENTITY(1,1) PRIMARY KEY,
    project_code        NVARCHAR(50)   NOT NULL UNIQUE,
    name                NVARCHAR(500)  NOT NULL,
    status              NVARCHAR(50)   NOT NULL,
    priority            NVARCHAR(20)   NOT NULL DEFAULT 'Medium',
    start_date          DATE           NULL,
    end_date            DATE           NULL,
    actual_end_date     DATE           NULL,
    budget              DECIMAL(18,2)  NULL,
    owner_id            INT            NULL REFERENCES users(id),
    department          NVARCHAR(100)  NULL,
    description         NVARCHAR(MAX)  NULL,
    is_active           BIT            NOT NULL DEFAULT 1,
    created_at          DATETIME2      DEFAULT GETDATE(),
    updated_at          DATETIME2      DEFAULT GETDATE(),
    sharepoint_item_id  NVARCHAR(100)  NULL
);
```

#### `project_tasks`（タスク管理）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| project_id | INT | FK → projects.id |
| title | NVARCHAR(500) | タスク名 |
| assignee_id | INT | FK → hr_master.id |
| status | NVARCHAR(50) | 未着手/進行中/完了 |
| due_date | DATE | 期日 |
| priority | NVARCHAR(20) | 優先度 |
| description | NVARCHAR(MAX) | 詳細 |
| is_active | BIT | 有効フラグ |

#### `audit_log`（変更履歴）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| table_name | NVARCHAR(100) | 対象テーブル |
| record_id | INT | 対象レコードID |
| action | NVARCHAR(20) | INSERT/UPDATE/DELETE |
| before_value | NVARCHAR(MAX) | 変更前（JSON） |
| after_value | NVARCHAR(MAX) | 変更後（JSON） |
| changed_by | INT | 変更者（users.id） |
| changed_at | DATETIME2 | 変更日時 |
| reason | NVARCHAR(500) | 変更理由 |

#### `hr_master`（人事マスタ）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| employee_code | NVARCHAR(50) | 社員番号 |
| name | NVARCHAR(200) | 氏名 |
| email | NVARCHAR(255) | メールアドレス |
| department | NVARCHAR(100) | 部署 |
| position | NVARCHAR(100) | 役職 |
| skills | NVARCHAR(MAX) | スキルタグ（JSON配列） |
| work_rate | DECIMAL(5,2) | 稼働率（0〜100%） |
| is_active | BIT | 在籍フラグ |
| updated_at | DATETIME2 | 更新日時 |

#### `approvals`（稟議管理）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| project_id | INT | FK → projects.id |
| approval_number | NVARCHAR(50) | 稟議番号 |
| title | NVARCHAR(500) | 稟議件名 |
| amount | DECIMAL(18,2) | 金額 |
| status | NVARCHAR(50) | 申請中/承認済/却下 |
| applicant_id | INT | FK → hr_master.id |
| applied_at | DATETIME2 | 申請日時 |
| approved_at | DATETIME2 | 承認日時 |
| approver_id | INT | 承認者ID |
| document_url | NVARCHAR(500) | 稟議書URL（SharePoint） |

---

### 1.5 AIチャット（App02）

#### `chat_sessions`（チャットセッション）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| user_id | INT | FK → users.id |
| title | NVARCHAR(500) | セッションタイトル |
| is_active | BIT | 有効フラグ |
| created_at | DATETIME2 | 作成日時 |
| updated_at | DATETIME2 | 最終更新日時 |

#### `chat_messages`（チャット履歴）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INT | PK |
| session_id | INT | FK → chat_sessions.id |
| role | NVARCHAR(20) | user / assistant |
| content | NVARCHAR(MAX) | メッセージ内容 |
| tokens_used | INT | 使用トークン数 |
| created_at | DATETIME2 | 作成日時 |

---

## 2. データソース詳細

| データソース | 種別 | 取得内容 | 接続方法 | 担当アプリ |
|------------|------|---------|---------|-----------|
| **SharePoint List** | Microsoft 365 | 案件進捗管理シート（タスク・ステータス） | Graph API (`/sites/{site-id}/lists/{list-id}/items`) | App12, Azure Functions |
| **SharePoint Files** | Microsoft 365 | 稟議書PDF、規程文書 | Graph API (`/drives/{drive-id}/items`) | App12, Document AI |
| **Outlook** | Microsoft 365 | メール履歴（案件関連） | Graph API (`/users/{user-id}/messages`) | 将来拡張 |
| **Teams** | Microsoft 365 | チャット・会議メモ | Graph API (`/teams/{team-id}/channels`) | 将来拡張 |
| **Azure Blob Storage** | Azure | アップロードされたファイル（PDF/Excel等） | Azure SDK (`BlobServiceClient`) | App08, App00 |
| **Azure AI Search** | Azure | ベクトル化済み文書 | `azure-search-documents` SDK | App02, App12 |
| **ERP/会計システム** | 社内 | 収支データ（月次） | CSV 連携（要確認） | App12（将来） |

### SharePoint 接続設定例

```python
# services/microsoft/sharepoint.py
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential

credential = ClientSecretCredential(
    tenant_id=cfg.tenant_id,
    client_id=cfg.client_id,
    client_secret=cfg.client_secret  # 本番は Key Vault 経由
)
graph_client = GraphServiceClient(credentials=credential)

# 案件管理シート取得
items = await graph_client.sites.by_site_id(SITE_ID)\
    .lists.by_list_id(LIST_ID)\
    .items.get()
```

---

## 3. 更新頻度と方法

### 3.1 Azure Functions タイマー一覧

| Function 名 | トリガー | スケジュール（JST） | 役割 | 対象テーブル |
|------------|---------|-----------------|------|------------|
| `fn_sync_project_sheet` | Timer | 毎日 9:00 | SharePoint → SQL 案件同期 | projects, project_tasks |
| `fn_sync_approval_docs` | Timer | 毎日 9:30 | 稟議書情報同期 | approvals |
| `fn_sync_hr_master` | Timer | 毎週月曜 8:00 | 人事マスタ更新 | hr_master |
| `fn_embed_documents` | Blob Trigger | ファイルアップロード時 | Embedding 生成・AI Search 登録 | （Azure AI Search） |
| `fn_score_ai` | Timer | 毎月1日 2:00 | AI スコアリング更新 | App701_scoring |
| `fn_alert_deadline` | Timer | 毎日 8:00 | 期日 3 日前 Teams 通知 | project_tasks |

### 3.2 スケジュール設定（UTC 表記）

```python
# Azure Functions の cron 式（UTC）
SCHEDULES = {
    "fn_sync_project_sheet": "0 0 * * *",       # UTC 00:00 = JST 09:00
    "fn_sync_approval_docs": "30 0 * * *",       # UTC 00:30 = JST 09:30
    "fn_sync_hr_master":     "0 23 * * 0",       # UTC 23:00 日曜 = JST 月曜 08:00
    "fn_score_ai":           "0 17 1 * *",       # UTC 17:00 毎月1日 = JST 翌月2日 02:00
    "fn_alert_deadline":     "0 23 * * *",       # UTC 23:00 = JST 08:00
}
```

### 3.3 差分同期ロジック（MERGE 文）

SharePoint から取得したデータは毎回全量を SQL にアップサート（MERGE）する。

```sql
-- projects テーブルへの MERGE（Azure Functions から実行）
MERGE projects AS target
USING (VALUES (?, ?, ?, ?, ?, ?)) 
    AS source (project_code, name, status, priority, end_date, sharepoint_item_id)
ON target.project_code = source.project_code
WHEN MATCHED THEN
    UPDATE SET
        name = source.name,
        status = source.status,
        priority = source.priority,
        end_date = source.end_date,
        updated_at = GETDATE()
WHEN NOT MATCHED THEN
    INSERT (project_code, name, status, priority, end_date, sharepoint_item_id)
    VALUES (source.project_code, source.name, source.status, 
            source.priority, source.end_date, source.sharepoint_item_id);
```

---

## 4. ER図（概念）

```
users
  ├── id (PK)
  ├── email
  └── user_level
       │
       ├──── app_list（required_level でアクセス制御）
       │
       ├──── projects（owner_id → users.id）
       │       ├── project_tasks（project_id → projects.id）
       │       ├── approvals（project_id → projects.id）
       │       └── audit_log（record_id = projects.id）
       │
       ├──── chat_sessions（user_id → users.id）
       │       └── chat_messages（session_id → chat_sessions.id）
       │
       └──── App701_basic（user_id → users.id / CIF で検索）
               ├── App701_transaction（cif で JOIN）
               ├── App701_deposit（cif で JOIN）
               ├── App701_contact（cif で JOIN）
               └── App701_scoring（cif で JOIN）

hr_master（人事マスタ・案件管理エージェントが参照）
  └── email → Microsoft Graph API でスケジュール連携

allowed_users（登録ホワイトリスト）
  └── email → users.email と照合して登録可否判断
```

---

## 5. インデックス設計

```sql
-- users テーブル
CREATE INDEX IX_users_email ON users(email);

-- projects テーブル
CREATE INDEX IX_projects_status ON projects(status);
CREATE INDEX IX_projects_end_date ON projects(end_date);
CREATE INDEX IX_projects_owner ON projects(owner_id);

-- project_tasks テーブル
CREATE INDEX IX_tasks_project ON project_tasks(project_id);
CREATE INDEX IX_tasks_due_date ON project_tasks(due_date);
CREATE INDEX IX_tasks_assignee ON project_tasks(assignee_id);

-- App701_basic（CIF 検索が頻繁）
CREATE INDEX IX_app701_cif ON App701_basic(cif);
CREATE INDEX IX_app701_user ON App701_basic(user_id);

-- chat_sessions / messages
CREATE INDEX IX_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IX_chat_messages_session ON chat_messages(session_id);

-- audit_log
CREATE INDEX IX_audit_table_record ON audit_log(table_name, record_id);
CREATE INDEX IX_audit_changed_at ON audit_log(changed_at);
```

---

## 6. テーブル初期化スクリプト

```python
# services/azure/database.py に追加する initialize_tables() 関数

def initialize_tables():
    """データベースの初期テーブルを作成する。冪等（存在すればスキップ）。"""
    ddl_statements = [
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
        CREATE TABLE users (
            id           INT            IDENTITY(1,1) PRIMARY KEY,
            email        NVARCHAR(255)  NOT NULL UNIQUE,
            username     NVARCHAR(100)  NOT NULL,
            password_hash NVARCHAR(255) NOT NULL,
            user_level   INT            NOT NULL DEFAULT 10,
            is_active    BIT            NOT NULL DEFAULT 1,
            created_at   DATETIME2      DEFAULT GETDATE(),
            updated_at   DATETIME2      DEFAULT GETDATE()
        )
        """,
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='allowed_users' AND xtype='U')
        CREATE TABLE allowed_users (
            email      NVARCHAR(255) PRIMARY KEY,
            user_level INT           NOT NULL,
            is_active  BIT           NOT NULL DEFAULT 1,
            note       NVARCHAR(500) NULL
        )
        """,
        # ... 他のテーブルも同様
    ]

    conn = get_raw_conn()
    cursor = conn.cursor()
    for stmt in ddl_statements:
        cursor.execute(stmt)
    conn.commit()
    cursor.close()
    conn.close()
```

FastAPI 起動時または管理エンドポイント経由で実行：

```bash
# 初期化（管理者トークンが必要）
curl -X POST https://<api-url>/api/project-agent/init-db \
     -H "Authorization: Bearer <admin-token>"
```

---

---

## 7. SQLAlchemy ORM モデル定義

テーブル設計の「正典」は SQL DDL（§1）だが、**Alembic の `autogenerate` を機能させるには ORM モデルが必要**。  
ORM モデルは `core/models.py` で管理する。テーブルを追加・変更した際はここを先に修正してから `alembic revision --autogenerate` を実行する。

```python
# core/models.py（抜粋・全文は実際のファイルを参照）
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, Date
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String(255), unique=True, nullable=False)
    username      = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    user_level    = Column(Integer, nullable=False, default=10)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, server_default=func.getdate())
    updated_at    = Column(DateTime, server_default=func.getdate())

class Project(Base):
    __tablename__ = "projects"
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    project_code       = Column(String(50), unique=True, nullable=False)
    name               = Column(String(500), nullable=False)
    status             = Column(String(50), nullable=False)
    # ... 他カラムは core/models.py を参照

# 全テーブルのモデル定義は core/models.py に集約
# User / AllowedUser / AppList / Project / ProjectTask /
# HrMaster / Approval / AuditLog / ChatSession / ChatMessage /
# App701Basic / App701Transaction / App701Deposit / App701Contact / App701Scoring
```

### 関係性（Relationship）の定義方針

- FK 関係は `relationship()` で明示する（JOIN クエリの自動化・型補完）
- ORM セッション（`core/db.py` の `SessionLocal`）で利用する場合のみ relationship を参照
- 既存の生 SQL パス（`get_raw_conn()`）は後方互換のため継続使用可

---

## 8. Alembic マイグレーション

### 8.1 初回セットアップ（環境構築後に一度だけ実行）

```bash
# 1. 環境変数を設定
cp configs/.env.example .env
# .env の SQL_SERVER / SQL_DATABASE / SQL_DRIVER 等を実際の値に書き換える

# 2. 初期データ挿入（テーブル作成 + app_list シードデータ）
python scripts/init_db.py

# 3. 現状を Alembic 履歴に記録（autogenerate でモデルから DDL を生成）
alembic revision --autogenerate -m "initial tables"

# 4. 生成されたファイルを確認（alembic/versions/ 以下）
#    Azure SQL 固有の型（NVARCHAR → String, DATETIME2 → DateTime, BIT → Boolean）が
#    正しくマッピングされているか確認。必要に応じて手動修正。

# 5. 現在の状態に揃っていることを確認
alembic upgrade head
alembic current
```

### 8.2 カラム追加・テーブル変更時の手順

```bash
# 1. core/models.py の該当クラスにカラムを追加・修正
# 2. 差分マイグレーション生成
alembic revision --autogenerate -m "add_column_xxx_to_yyy"

# 3. 生成ファイルを確認・必要に応じて手動修正
# 4. ステージングで検証
alembic upgrade head

# 5. 本番に適用（GitHub Actions デプロイ後に手動実行、または deploy.yml に組み込む）
alembic upgrade head
```

### 8.3 ロールバック

```bash
# 1 ステップ戻す
alembic downgrade -1

# 特定リビジョンまで戻す（alembic history で確認）
alembic history
alembic downgrade <revision_id>
```

### 8.4 alembic/env.py の構成

`alembic/env.py` は以下を実装済み：

| 機能 | 実装内容 |
|------|---------|
| ORM 参照 | `from core.models import Base` → `target_metadata = Base.metadata` |
| 接続文字列 | `core/db.py` の `_build_conn_str()` を再利用 |
| Managed Identity | `sql_username/sql_password` が空の場合は AAD トークンを自動取得 |
| オフラインモード | `alembic upgrade --sql` でマイグレーション SQL を出力可能 |

---

*テーブル設計は SharePoint・案件管理シートの実際のカラム名と照合してから確定すること（gaps.md「データ整備タスク」参照）。*
