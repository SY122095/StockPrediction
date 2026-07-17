# FXD Intelligence Platform - ナレッジベース

作成日：2026-06-02  
対象プロジェクト：FXD Intelligence Platform（FastAPI × React × Azure）

---

## ドキュメント一覧

| ファイル | 内容 | 主な対象者 |
|---------|------|-----------|
| [01_cloud_platform.md](01_cloud_platform.md) | Azure/GCP/AWS サービス洗い出し・コスト比較・設定方法・構築フロー | インフラ担当・管理者 |
| [02_vm_settings.md](02_vm_settings.md) | Linux VM 設定・FastAPI×React 起動・ファイアウォール・systemd | インフラ担当・開発者 |
| [03_database_design.md](03_database_design.md) | テーブル設計・データソース・更新頻度・ER 図 | 開発者・DBA |
| [04_git_github.md](04_git_github.md) | Git コマンド集・ブランチ戦略・GitHub 操作・CI/CD | 全開発者 |
| [05_fastapi_design.md](05_fastapi_design.md) | FastAPI 設計・PydanticAI エージェント・セキュリティ修正 | バックエンド開発者 |
| [06_react_design.md](06_react_design.md) | React(MUI) 設計・セキュリティ修正・状態管理・テンプレート | フロントエンド開発者 |
| [07_new_app_development.md](07_new_app_development.md) | 新規アプリ追加の全ステップ・チェックリスト | 全開発者 |
| [08_other_notes.md](08_other_notes.md) | YAML 設定・Python バージョン・ディレクトリ構造・仕様書 | 全開発者 |

## テンプレート一覧

| ファイル | 内容 |
|---------|------|
| [templates/fastapi_app/app.py](templates/fastapi_app/app.py) | FastAPI ルーターテンプレート |
| [templates/fastapi_app/config.py](templates/fastapi_app/config.py) | アプリ設定テンプレート |
| [templates/fastapi_app/api/generate.py](templates/fastapi_app/api/generate.py) | Azure OpenAI 呼び出しテンプレート |
| [templates/react_app/pages/MainPage.tsx](templates/react_app/pages/MainPage.tsx) | React ページテンプレート（SSE 対応） |
| [templates/react_app/components/MarkdownRenderer.tsx](templates/react_app/components/MarkdownRenderer.tsx) | XSS 安全な Markdown レンダラー |

---

## 重要な優先対応事項

### 🔴 即時対応（今週中）

1. `core/auth/service.py` の `SECRET_KEY` を環境変数へ移行
2. `app701` の SSE トークンを URL から排除 → POST + Cookie に変更
3. `core/main.py` の CORS を本番ドメインのみに制限
4. `core/configs.yaml` の API キーを Azure Key Vault へ移行・Git 履歴から削除
5. Markdown 表示を `react-markdown` に移行（`dangerouslySetInnerHTML` 削除）

### 🟠 今月中対応

6. `services/azure/database.py` にテーブル名ホワイトリスト検証を追加
7. `core/top/router.py` の認証なしエンドポイントに `Depends(get_current_user)` 追加
8. JWT を httpOnly Cookie ベースに変更
9. 登録制限ロジックを `allowed_users` テーブルへ移行
10. Azure Functions の Managed Identity 設定

---

## プロジェクト概要

- **バックエンド**: FastAPI（Python 3.12）+ Uvicorn
- **フロントエンド**: React 19 + TypeScript + Material UI 7
- **AI**: Azure OpenAI（GPT-4o / o1 / GPT-5）+ PydanticAI
- **DB**: Azure SQL Database（SQL Server）
- **ストレージ**: Azure Blob Storage
- **認証**: JWT（httpOnly Cookie）+ Microsoft Entra ID
- **ホスティング**: Azure VM（Ubuntu 22.04）
- **自動化**: Azure Functions（Python 3.12）
- **ベクトル検索**: Azure AI Search
- **シークレット管理**: Azure Key Vault（移行予定）
