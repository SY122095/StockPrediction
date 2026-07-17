# ④ Git / GitHub 管理ガイド

作成日：2026-06-02

---

## 目次

1. [Git 用語解説（初学者向け）](#1-git-用語解説初学者向け)
2. [Bash コマンド一覧](#2-bash-コマンド一覧)
3. [ブランチ戦略](#3-ブランチ戦略)
4. [GitHub ページでの操作](#4-github-ページでの操作)
5. [よくある操作フロー](#5-よくある操作フロー)
6. [.gitignore 設定](#6-gitignore-設定)
7. [GitHub Actions CI/CD](#7-github-actions-cicd)（7.1 Azure OIDC 認証 / 7.2 自動デプロイ / 7.3 セキュリティスキャン）

---

## 1. Git 用語解説（初学者向け）

| 用語 | わかりやすい説明 |
|------|----------------|
| **リポジトリ（repo）** | プロジェクトのファイルと変更履歴をまとめて管理する「箱」 |
| **コミット（commit）** | 変更内容を「セーブポイント」として記録すること。後から戻れる |
| **ブランチ（branch）** | 開発の「分岐」。本番に影響を与えずに新機能を開発できる |
| **マージ（merge）** | あるブランチの変更を別のブランチに取り込むこと |
| **プル（pull）** | リモート（GitHub）の最新変更をローカルに取り込む |
| **プッシュ（push）** | ローカルの変更をリモート（GitHub）にアップロードする |
| **クローン（clone）** | GitHub のリポジトリをローカルにコピーする |
| **フェッチ（fetch）** | リモートの情報を取得するが、ローカルには反映しない（pull の前半） |
| **ステージ（stage）** | コミットする変更を「準備エリア」に追加すること（git add） |
| **プルリクエスト（PR）** | ブランチの変更を main/dev に取り込む際の「レビュー申請」 |
| **コンフリクト（conflict）** | 同じ箇所を複数人が編集したときに起きる競合。手動で解決が必要 |
| **スタッシュ（stash）** | 作業途中の変更を一時保存して、ブランチを切り替える機能 |
| **HEAD** | 現在作業中のコミットを指すポインタ（「今いる場所」） |
| **origin** | リモートリポジトリ（GitHub）のデフォルト名 |
| **main / master** | 本番リリース用の主ブランチ |
| **dev / develop** | 開発用ブランチ。機能ブランチをここにマージしてから main へ |

---

## 2. Bash コマンド一覧

### 2.1 初期設定

```bash
# ユーザー設定（初回のみ）
git config --global user.name "山内祥平"
git config --global user.email "yamauchi@fxd.co.jp"

# 確認
git config --list

# SSH 鍵生成（GitHub との認証用）
ssh-keygen -t ed25519 -C "yamauchi@fxd.co.jp"
cat ~/.ssh/id_ed25519.pub  # この内容を GitHub に登録する
```

### 2.2 リポジトリ操作

```bash
# クローン（初回）
git clone git@github.com:<組織名>/fxd-intelligence.git
cd fxd-intelligence

# 現在の状態確認
git status

# 変更差分確認
git diff

# ログ確認（直近 10 件）
git log --oneline -10

# ブランチ一覧確認
git branch        # ローカルのみ
git branch -a     # リモートも含む
```

### 2.3 ブランチ操作

```bash
# ブランチ切り替え
git checkout main        # main へ切り替え
git checkout dev         # dev へ切り替え
git switch main          # 新しい書き方（git 2.23以降）
git switch dev

# 新規ブランチ作成と切り替え（dev から分岐するのが基本）
git checkout dev
git pull origin dev              # 最新の dev を取得
git checkout -b feature/app-xxx  # 新規ブランチ作成
# または
git switch -c feature/app-xxx

# ブランチ削除（マージ済みのもの）
git branch -d feature/app-xxx    # ローカル削除
git push origin --delete feature/app-xxx  # リモート削除
```

### 2.4 コミット

```bash
# 特定ファイルをステージに追加
git add apps/app12_project_management/app.py
git add frontend/src/apps/app12_project_management/

# 変更ファイルをすべてステージに追加（機密ファイルに注意）
git add .

# ステージの確認
git status
git diff --staged

# コミット
git commit -m "feat: 案件管理エージェント API を追加"

# コミットメッセージの書き方（推奨）
# feat:    新機能追加
# fix:     バグ修正
# docs:    ドキュメント変更
# refactor: リファクタリング（機能変更なし）
# security: セキュリティ修正
# chore:   設定変更・依存パッケージ更新
```

### 2.5 リモートとの同期

```bash
# リモートの変更を取り込む（pull = fetch + merge）
git pull origin main
git pull origin dev

# ローカルの変更をリモートへアップロード
git push origin feature/app-xxx

# 初回プッシュ（上流ブランチを設定）
git push -u origin feature/app-xxx

# 現在のブランチと同じ名前でプッシュ
git push origin HEAD
```

### 2.6 マージ

```bash
# dev へ feature ブランチをマージ（ローカル）
git checkout dev
git pull origin dev
git merge feature/app-xxx

# main へ dev をマージ（本番反映）
git checkout main
git pull origin main
git merge dev
git push origin main
```

### 2.7 コンフリクト解決

```bash
# コンフリクト発生時の確認
git status  # "both modified" のファイルが表示される

# コンフリクト箇所（<<<< HEAD ... ==== ... >>>> branch）を手動編集

# 解決後
git add <コンフリクトしたファイル>
git commit -m "fix: コンフリクト解消"
```

### 2.8 スタッシュ（作業中断）

```bash
# 作業中の変更を一時保存
git stash
git stash push -m "作業中: 案件一覧 UI 修正"

# 別のブランチで作業後に復元
git stash pop        # 最新のスタッシュを復元（削除される）
git stash apply      # 最新のスタッシュを復元（残す）

# スタッシュ一覧確認
git stash list
```

### 2.9 取り消し操作

```bash
# ステージのキャンセル（コミット前）
git restore --staged <ファイル名>

# ファイルの変更をリセット（注意：変更が消える）
git restore <ファイル名>

# 直前のコミットを取り消し（変更は残す）
git reset --soft HEAD~1

# 直前のコミットを完全に取り消し（変更も消える：危険）
# git reset --hard HEAD~1  ← 慎重に使う

# リモートの状態に強制的にリセット（危険：ローカル変更が消える）
# git reset --hard origin/dev  ← 慎重に使う
```

### 2.10 便利コマンド

```bash
# 変更ファイルの一覧のみ表示
git status -s

# 詳細なログ（グラフ付き）
git log --oneline --graph --all

# 特定ファイルのログ
git log --oneline -- apps/app12_project_management/app.py

# 誰がいつ何を書いたか確認
git blame core/main.py

# タグ作成（リリースバージョン管理）
git tag -a v1.0.0 -m "version 1.0.0 release"
git push origin --tags
```

---

## 3. ブランチ戦略

```
main（本番：vm-fxd-prod へ手動承認デプロイ）
  └── develop（ステージング：vm-fxd-stg へ自動デプロイ）
        ├── feature/app-xxx（新機能開発）
        ├── feature/security-fix（セキュリティ修正）
        ├── hotfix/xxx（緊急修正：main から直接分岐）
        └── docs/xxx（ドキュメント更新）
```

**デプロイフロー：**

```
feature/* ──[PR]──→ develop ──[push で自動]──→ vm-fxd-stg（ステージングで動作確認）
                        │
                       [PR + レビュー承認]
                        ↓
                      main ──[Environment 承認後]──→ vm-fxd-prod（本番反映）
```

### 運用ルール

| ルール | 内容 |
|--------|------|
| main への直接プッシュ禁止 | 必ず PR（プルリクエスト）経由 |
| main マージ前にステージングで動作確認 | develop にマージ → vm-fxd-stg で確認してから main に PR |
| PR には最低 1 名レビュー | セキュリティ修正は 2 名 |
| feature ブランチは develop から分岐 | main から分岐しない |
| コミット前に `git pull` | コンフリクトを最小化 |
| 機密情報をコミットしない | .gitignore を確認してから git add |
| 本番デプロイは GitHub Environments の承認者が承認 | 誤操作・意図しない本番反映を防止 |

---

## 4. GitHub ページでの操作

### 4.1 dev の内容を main に反映（Pull Request）

1. GitHub リポジトリページを開く
2. 上部の「Pull requests」タブをクリック
3. 「New pull request」をクリック
4. **base:** `main` ← **compare:** `dev` を選択
5. 「Create pull request」をクリック
6. タイトルと説明を入力
   ```
   タイトル例：[Release] v1.2.0 案件管理エージェント追加
   説明：変更内容の概要、テスト結果、注意事項を記載
   ```
7. レビュアーを設定して「Create pull request」
8. レビュー承認後「Merge pull request」→「Confirm merge」

### 4.2 Branch Protection Rules 設定（管理者作業）

1. リポジトリ Settings → Branches
2. 「Add rule」→ Branch name pattern: `main`
3. 以下をチェック：
   - ✅ Require a pull request before merging
   - ✅ Require approvals（1 名以上）
   - ✅ Require status checks to pass（CI/CD）
   - ✅ Require branches to be up to date before merging
   - ✅ Restrict who can push to matching branches

### 4.3 Secrets 設定（Actions 用）

1. Settings → Secrets and variables → Actions
2. 「New repository secret」で以下を登録：

**ステージング（develop → vm-fxd-stg）用：**

| シークレット名 | 内容 |
|--------------|------|
| `AZURE_STG_VM_HOST` | ステージング VM の IP アドレスまたは Azure FQDN |
| `AZURE_STG_VM_USER` | SSH ユーザー名（`azureuser`） |
| `AZURE_STG_VM_SSH_KEY` | SSH 秘密鍵（PEM ファイルの内容） |

**本番（main → vm-fxd-prod）用：**

| シークレット名 | 内容 |
|--------------|------|
| `AZURE_PROD_VM_HOST` | 本番 VM の IP アドレス（パブリック IP なし構成の場合はプライベート IP） |
| `AZURE_PROD_VM_USER` | SSH ユーザー名（`azureuser`） |
| `AZURE_PROD_VM_SSH_KEY` | SSH 秘密鍵（PEM ファイルの内容） |

3. **GitHub Environments の設定（本番承認フロー）：**
   - Settings → Environments → 「New environment」→ 名前：`production`
   - 「Required reviewers」に承認者（リリース担当者）を追加
   - 「Deployment branches」→ `main` のみ許可
   - この設定により、main へのマージ時に承認者が承認するまで本番デプロイが保留されます

---

## 5. よくある操作フロー

### フロー 1：新機能開発

```bash
# 1. dev を最新化
git checkout dev
git pull origin dev

# 2. 機能ブランチ作成
git checkout -b feature/add-project-agent

# 3. 開発・テスト

# 4. コミット
git add .
git commit -m "feat: PydanticAI プロジェクトエージェント実装"

# 5. dev に最新差分を取り込んでからプッシュ
git fetch origin dev
git rebase origin/dev   # または git merge origin/dev
git push origin feature/add-project-agent

# 6. GitHub で PR を作成（base: dev ← compare: feature/add-project-agent）
```

### フロー 2：本番リリース（ステージング確認 → 本番反映）

```bash
# 1. develop を最新化してステージングへ自動デプロイ
git checkout develop
git pull origin develop
git merge feature/add-project-agent
git push origin develop
# → GitHub Actions が自動で vm-fxd-stg にデプロイ
# → http://<ステージングIP> で動作確認

# 2. ステージングで動作確認が取れたら develop → main に PR（GitHub 上で）
#    GitHub Environments の承認者が「Approve」を押すと本番デプロイ開始

# 3. main にマージされたらタグ付け
git checkout main
git pull origin main
git tag -a v1.2.0 -m "v1.2.0 案件管理エージェント"
git push origin --tags

# 4. 本番デプロイは GitHub Actions が自動実行（承認後）
#    手動デプロイが必要な場合（VM に SSH 接続後）
cd /home/azureuser/fxd-intelligence
git pull origin main
source fastapi-env/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
sudo systemctl restart fxd-platform
```

### フロー 3：緊急修正（hotfix）

```bash
# 1. main から hotfix ブランチ作成
git checkout main
git pull origin main
git checkout -b hotfix/security-cors-fix

# 2. 修正・コミット
git commit -m "security: CORS 設定を本番ドメインのみに制限"

# 3. main への PR → マージ
git push origin hotfix/security-cors-fix

# 4. main のマージ後に dev にも反映
git checkout dev
git merge main
git push origin dev
```

---

## 6. .gitignore 設定

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
fastapi-env/
ai-env/
.venv/
*.egg-info/
dist/
build/

# Node.js
node_modules/
frontend/dist/

# 環境変数・シークレット（最重要）
.env
.env.local
.env.production
configs.yaml
local.settings.json
service_account_key.json
*.pem
*.key

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# ログ・一時ファイル
*.log
tmp/
output/

# Jupyter
.ipynb_checkpoints/
```

> **重要：** `configs.yaml` と `.env` は必ず `.gitignore` に含めること。すでにコミットしてしまった場合は以下で履歴から削除：
> ```bash
> git filter-branch --force --index-filter \
>   "git rm --cached --ignore-unmatch configs.yaml" \
>   --prune-empty --tag-name-filter cat -- --all
> ```

---

## 7. GitHub Actions CI/CD

### 7.1 Azure Workload Identity（OIDC キーレス認証）のセットアップ（推奨）

SSH 秘密鍵を GitHub Secrets に登録する代わりに、Azure Workload Identity を使うとキーレスで認証できる。ただし VM への SSH デプロイには別途 Bastion 経由の仕組みが必要なため、**シンプルさを優先する場合は 7.2 の SSH 鍵方式でも問題ない**。

```bash
# Azure CLI でアプリ登録
APP_ID=$(az ad app create --display-name "github-actions-fxd" --query appId -o tsv)
az ad sp create --id "$APP_ID"

# GitHub Actions 用フェデレーション資格情報を設定（ブランチごとに作成）
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<GitHub組織名>/fxd-intelligence:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-develop",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<GitHub組織名>/fxd-intelligence:ref:refs/heads/develop",
  "audiences": ["api://AzureADTokenExchange"]
}'

# リソースグループへのロール付与（Contributor はスコープを絞ること）
az role assignment create \
  --assignee "$APP_ID" \
  --role "Contributor" \
  --scope "/subscriptions/<sub>/resourceGroups/rg-fxd-platform"
```

**GitHub Secrets に登録する値（OIDC 方式）：**

| シークレット名 | 内容 |
|--------------|------|
| `AZURE_CLIENT_ID` | 上記 `APP_ID` |
| `AZURE_TENANT_ID` | Azure テナント ID |
| `AZURE_SUBSCRIPTION_ID` | Azure サブスクリプション ID |

**GitHub Actions ワークフロー（OIDC 認証ステップ）：**

```yaml
permissions:
  contents: read
  id-token: write   # OIDC に必要

- name: Authenticate to Azure
  uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

---

### 7.2 自動デプロイワークフロー（マルチ環境）

`.github/workflows/deploy.yml` として保存する。

- `develop` ブランチへの push → **ステージング（vm-fxd-stg）に自動デプロイ**
- `main` ブランチへの push → GitHub Environments の承認後 → **本番（vm-fxd-prod）にデプロイ**

```yaml
name: Deploy to Azure VM

on:
  push:
    branches:
      - main
      - develop

jobs:
  # ---- ステージングデプロイ（develop push 時・承認不要）----
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Cache node modules
        uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: ${{ runner.os }}-node-${{ hashFiles('frontend/package-lock.json') }}
          restore-keys: |
            ${{ runner.os }}-node-

      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build

      - name: Copy frontend dist to staging VM
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.AZURE_STG_VM_HOST }}
          username: ${{ secrets.AZURE_STG_VM_USER }}
          key: ${{ secrets.AZURE_STG_VM_SSH_KEY }}
          source: "frontend/dist"
          target: "/home/azureuser/fxd-intelligence/"
          rm: true

      - name: Deploy to staging VM via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.AZURE_STG_VM_HOST }}
          username: ${{ secrets.AZURE_STG_VM_USER }}
          key: ${{ secrets.AZURE_STG_VM_SSH_KEY }}
          script: |
            cd /home/azureuser/fxd-intelligence
            git pull origin develop
            source fastapi-env/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart fxd-platform
            echo "✅ Staging deploy complete: $(date '+%Y-%m-%d %H:%M:%S JST')"

  # ---- 本番デプロイ（main push 時・Environment 承認必要）----
  deploy-production:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production   # GitHub Environments で承認者を設定すること

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Cache node modules
        uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: ${{ runner.os }}-node-${{ hashFiles('frontend/package-lock.json') }}
          restore-keys: |
            ${{ runner.os }}-node-

      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build

      - name: Copy frontend dist to production VM
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.AZURE_PROD_VM_HOST }}
          username: ${{ secrets.AZURE_PROD_VM_USER }}
          key: ${{ secrets.AZURE_PROD_VM_SSH_KEY }}
          source: "frontend/dist"
          target: "/home/azureuser/fxd-intelligence/"
          rm: true

      - name: Deploy to production VM via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.AZURE_PROD_VM_HOST }}
          username: ${{ secrets.AZURE_PROD_VM_USER }}
          key: ${{ secrets.AZURE_PROD_VM_SSH_KEY }}
          script: |
            cd /home/azureuser/fxd-intelligence
            git pull origin main
            source fastapi-env/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart fxd-platform
            echo "🚀 Production deploy complete: $(date '+%Y-%m-%d %H:%M:%S JST')"
```

### 7.2 セキュリティスキャンワークフロー

```yaml
name: Security Scan

on:
  pull_request:
    branches:
      - main
      - dev

jobs:
  bandit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Bandit (Python security scan)
        run: |
          pip install bandit
          bandit -r . -x fastapi-env,ai-env --severity-level medium

  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy (dependency scan)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: "fs"
          scan-ref: "."
          format: "table"
          exit-code: "1"
          severity: "CRITICAL,HIGH"
```

### 7.3 環境別デプロイ先まとめ

| ブランチ | デプロイ先 VM | 承認 | ドメイン | SSL |
|---------|-------------|------|---------|-----|
| `develop` | `vm-fxd-stg`（ステージング） | 不要・自動 | IP 直接アクセス | なし（HTTP） |
| `main` | `vm-fxd-prod`（本番） | GitHub Environments で承認必要 | `fxd-platform.example.com` | Front Door マネージド証明書 |

**GitHub Environments（production）の設定手順：**

1. リポジトリ → Settings → Environments → 「New environment」
2. 名前：`production`
3. 「Required reviewers」に承認者を追加
4. 「Deployment branches and tags」→ 「Selected branches and tags」→ `main` を追加
5. 設定保存後、main への push 時に承認者へ通知メールが届き、承認するまでデプロイが保留される

> `staging` 環境も同様に作成しておくと、ステージングデプロイのログが Environments タブで確認できます（承認は不要）。

### 7.4 デプロイ後の確認手順

```bash
# ステージング動作確認（ブラウザ）
# http://<AZURE_STG_VM_HOST>/
# http://<AZURE_STG_VM_HOST>/api/docs  （Swagger UI）

# ステージング VM ログ確認（SSH 接続後）
ssh -i ~/VM-fxd-stg_key.pem azureuser@<AZURE_STG_VM_HOST>
sudo journalctl -u fxd-platform -n 50 --no-pager

# 本番 VM ログ確認（Bastion 経由）
az network bastion ssh \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --target-resource-id "<vm-fxd-prod のリソース ID>" \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/id_rsa
sudo journalctl -u fxd-platform -n 50 --no-pager
```

---

*Git の操作は破壊的なコマンド（`--hard`、`--force`）を使う前に必ず確認すること。不明な点はチームに相談。*
