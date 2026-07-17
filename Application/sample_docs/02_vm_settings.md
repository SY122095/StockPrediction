# ② VM設定ガイド（FastAPI × React）

作成日：2026-06-02  
対象OS：Ubuntu 22.04 LTS on Azure VM

---

## 目次

1. [VM初期セットアップ](#1-vm初期セットアップ)
2. [Python 3.12 環境構築](#2-python-312-環境構築)
3. [Node.js / npm 環境構築](#3-nodejs--npm-環境構築)
4. [FastAPI プロジェクト設定](#4-fastapi-プロジェクト設定)
5. [React フロントエンドのビルド](#5-react-フロントエンドのビルド)
6. [systemd サービス化（自動起動）](#6-systemd-サービス化自動起動)
7. [ファイアウォール設定](#7-ファイアウォール設定)
8. [Nginx リバースプロキシ設定](#8-nginx-リバースプロキシ設定)
9. [ODBC ドライバー設定（Azure SQL 接続）](#9-odbc-ドライバー設定)
10. [環境変数・シークレット設定](#10-環境変数シークレット設定)
11. [設定項目まとめ（表）](#11-設定項目まとめ)
12. [環境別構成の違い（本番 vs ステージング）](#12-環境別構成の違い本番-vs-ステージング)

---

## 1. VM初期セットアップ

### 1.1 SSH 接続

本番 VM はパブリック IP なし構成のため、**Azure Bastion** 経由でブラウザ SSH または CLI SSH を使用する。ステージング VM は開発者固定 IP からの直接接続も可。

**本番（Bastion 経由）：**
```bash
# Azure CLI で Bastion 経由 SSH（ローカル PC から）
az network bastion ssh \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --target-resource-id "/subscriptions/<sub>/resourceGroups/rg-fxd-platform/providers/Microsoft.Compute/virtualMachines/vm-fxd-prod" \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/id_rsa

# ポートフォワーディング（ローカル 8080 → VM の 8000）
az network bastion tunnel \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --target-resource-id "/subscriptions/<sub>/resourceGroups/rg-fxd-platform/providers/Microsoft.Compute/virtualMachines/vm-fxd-prod" \
  --resource-port 8000 \
  --port 8080
# → http://localhost:8080/docs でアクセス可能
```

> **ポータルからのブラウザ SSH：** Azure Portal → VM → 「接続」→「Bastion」→ ユーザー名・秘密キーを入力 → 「接続」

**ステージング（PEM キー直接接続）：**
```bash
# 初回接続時のパーミッション設定
chmod 400 ~/VM-fxd-stg_key.pem
ssh -i ~/VM-fxd-stg_key.pem azureuser@<ステージング VM の IP>
```

### 1.2 システムパッケージ更新

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  git \
  curl \
  wget \
  build-essential \
  libssl-dev \
  libffi-dev \
  unzip \
  htop \
  net-tools \
  ufw \
  nginx
```

### 1.3 タイムゾーン設定

```bash
# タイムゾーンを JST に設定
sudo timedatectl set-timezone Asia/Tokyo
timedatectl status  # 確認
```

---

## 2. Python 3.12 環境構築

### 2.1 pyenv によるインストール（推奨）

```bash
# pyenv 依存パッケージ
sudo apt install -y \
  libbz2-dev \
  libncurses-dev \
  libreadline-dev \
  libsqlite3-dev \
  libxml2-dev \
  libxmlsec1-dev \
  liblzma-dev \
  tk-dev \
  zlib1g-dev

# pyenv インストール
curl https://pyenv.run | bash

# シェル設定に追記（~/.bashrc）
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Python 3.12.x インストール
pyenv install 3.12.10
pyenv global 3.12.10

# 確認
python --version  # Python 3.12.10
pip --version
```

### 2.2 仮想環境作成

```bash
# プロジェクトディレクトリへ移動
cd /home/azureuser/fxd-intelligence-dev

# 仮想環境作成
python -m venv fastapi-env

# 有効化
source fastapi-env/bin/activate

# requirements.txt からインストール
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Node.js / npm 環境構築

```bash
# nvm でインストール（バージョン管理ができるので推奨）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc

# Node.js LTS インストール
nvm install --lts
nvm use --lts

# 確認
node --version   # v22.x.x 等
npm --version
```

---

## 4. FastAPI プロジェクト設定

### 4.1 リポジトリのクローン

```bash
cd /home/azureuser
git clone https://github.com/<組織名>/fxd-intelligence.git
cd fxd-intelligence
```

### 4.2 設定ファイルの配置

```bash
# configs.yaml は Git 管理外 → Key Vault 経由で取得（本番）
# ローカル開発時のみ .env を使用
cp .env.example .env
# .env を編集して各種シークレットを設定（Key Vault URI を記載）
```

### 4.3 ODBC ドライバー（次セクション参照）

### 4.4 DB 初期化（初回デプロイのみ）

Azure SQL Database 作成・アプリコードクローン後、**最初の一度だけ**実行する。

```bash
cd /home/azureuser/fxd-intelligence
source fastapi-env/bin/activate

# テーブル作成
python scripts/init_db.py

# Alembic マイグレーション管理開始（初回のみ）
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
alembic current  # 適用確認
```

> **注意：** `init_db.py` を2回以上実行しても `IF NOT EXISTS` のため安全。ただし Alembic の `revision` は初回のみ実行すること（2回目以降は `alembic upgrade head` のみ）。

### 4.5 FastAPI 起動確認

```bash
cd /home/azureuser/fxd-intelligence
source fastapi-env/bin/activate

# 開発サーバー起動（ポート 8000）
uvicorn core.main:app --host 0.0.0.0 --port 8000 --reload

# Bastion トンネルでローカルからアクセス確認
# az network bastion tunnel ... --resource-port 8000 --port 8080
# → http://localhost:8080/docs （Swagger UI）
```

---

## 5. React フロントエンドのビルド

```bash
cd /home/azureuser/fxd-intelligence/frontend

# 依存パッケージインストール
npm install

# 本番ビルド
npm run build
# → frontend/dist/ に静的ファイルが生成される

# 確認：dist フォルダに index.html があるか
ls dist/
```

> **Note:** FastAPI の `core/main.py` が `frontend/dist/` をそのまま配信するため、`npm run build` 後に uvicorn を再起動すれば最新 UI が反映される。

---

## 6. systemd サービス化（自動起動）

### 6.1 サービスファイル作成

```bash
sudo nano /etc/systemd/system/fxd-platform.service
```

```ini
[Unit]
Description=FXD Intelligence Platform (FastAPI)
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/fxd-intelligence
ExecStart=/home/azureuser/fxd-intelligence/fastapi-env/bin/uvicorn \
    core.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2
Restart=always
RestartSec=10

# 環境変数（Key Vault URI を指定）
Environment="AZURE_CLIENT_ID=<Managed Identity Client ID>"
Environment="KEY_VAULT_URL=https://kv-fxd-prod.vault.azure.net/"

# ログ
StandardOutput=journal
StandardError=journal
SyslogIdentifier=fxd-platform

[Install]
WantedBy=multi-user.target
```

### 6.2 サービス起動・管理

```bash
# サービス登録・起動
sudo systemctl daemon-reload
sudo systemctl enable fxd-platform
sudo systemctl start fxd-platform

# 状態確認
sudo systemctl status fxd-platform

# ログ確認（直近 50 行）
sudo journalctl -u fxd-platform -n 50 --no-pager

# ログをリアルタイム監視
sudo journalctl -u fxd-platform -f

# 再起動
sudo systemctl restart fxd-platform

# 停止
sudo systemctl stop fxd-platform
```

---

## 7. ファイアウォール設定

### 7.1 UFW（Linux ファイアウォール）設定

```bash
# デフォルト設定
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH（必須：これを先に許可しないとロックアウトされる）
sudo ufw allow 22/tcp

# HTTP / HTTPS（外部公開用）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# FastAPI 直接アクセス（開発時のみ・本番では閉じる）
# sudo ufw allow 8000/tcp  ← 本番では Nginx 経由のみにする

# UFW 有効化
sudo ufw enable
sudo ufw status verbose
```

### 7.2 Azure NSG（Network Security Group）設定

Azure Portal から VM の NSG に以下のルールを追加：

| 優先度 | 名前 | ポート | プロトコル | 送信元 | 操作 | 備考 |
|--------|------|--------|----------|--------|------|------|
| 100 | Allow-SSH | 22 | TCP | 会社IPアドレス | 許可 | 特定IPのみに制限 |
| 110 | Allow-HTTPS | 443 | TCP | Any | 許可 | 本番アクセス |
| 120 | Allow-HTTP | 80 | TCP | Any | 許可 | HTTPS リダイレクト用 |
| 200 | Deny-Direct-API | 8000 | TCP | Any | 拒否 | Nginx 経由のみ許可 |
| 4096 | DenyAll | * | * | Any | 拒否 | デフォルト拒否 |

```bash
# Azure CLI での NSG ルール追加例
az network nsg rule create \
  --resource-group rg-fxd-platform \
  --nsg-name fxd-vm-nsg \
  --name Allow-SSH \
  --priority 100 \
  --protocol Tcp \
  --destination-port-range 22 \
  --source-address-prefix "<会社のパブリックIP>/32" \
  --access Allow
```

### 7.3 JIT（Just-In-Time）アクセス設定（セキュリティ強化版）

```bash
# Azure CLI で JIT ポリシー設定
az security jit-policy create \
  --resource-group rg-fxd-platform \
  --vm-name fxd-vm \
  --location japaneast \
  --ports '[{"number":22,"protocol":"TCP","allowedSourceAddressPrefix":"*","maxRequestAccessDuration":"PT3H"}]'
```

---

## 8. Nginx リバースプロキシ設定

### 8.1 Nginx インストール

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 8.2 サイト設定ファイル

```bash
sudo nano /etc/nginx/sites-available/fxd-platform
```

```nginx
server {
    listen 80;
    server_name <ドメイン or IPアドレス>;

    # HTTPS へリダイレクト（SSL 設定後）
    # return 301 https://$host$request_uri;

    # API プロキシ（FastAPI へ転送）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE（Server-Sent Events）対応
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }

    # 静的アセット（React）
    location /assets/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_cache_valid 200 1d;
        expires 1d;
        add_header Cache-Control "public, max-age=86400";
    }

    # React SPA フォールバック
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

```bash
# サイトを有効化
sudo ln -s /etc/nginx/sites-available/fxd-platform /etc/nginx/sites-enabled/
sudo nginx -t  # 設定テスト
sudo systemctl reload nginx
```

### 8.3 SSL（HTTPS）設定

```bash
# Certbot で無料 SSL（ドメインがある場合）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <ドメイン名>

# 自動更新確認
sudo certbot renew --dry-run
```

---

## 9. ODBC ドライバー設定

Azure SQL Database への接続に必要。

```bash
# Microsoft ODBC Driver 18 for SQL Server インストール
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | \
  sudo tee /etc/apt/sources.list.d/mssql-release.list

sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18 mssql-tools18 unixodbc-dev

# 接続テスト
sqlcmd -S fxd-platform.database.windows.net -U fxd-admin -P '<パスワード>' \
  -Q "SELECT @@VERSION"
```

---

## 10. 環境変数・シークレット設定

### 10.1 .env ファイル（ローカル開発時のみ）

```bash
# .env.example をコピーして編集
cp .env.example .env
```

```dotenv
# .env（Git 管理外・.gitignore に必ず含める）
KEY_VAULT_URL=https://kv-fxd-prod.vault.azure.net/
AZURE_CLIENT_ID=<Managed Identity Client ID>

# ローカル開発時のみ直接設定（本番では Key Vault から取得）
JWT_SECRET_KEY=<ランダム文字列 32文字以上>
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
```

### 10.2 本番環境変数確認

```bash
# systemd サービスが環境変数を正しく読み込んでいるか確認
sudo systemctl show fxd-platform | grep Environment

# 環境変数一覧（プロセス）
sudo cat /proc/$(pgrep -f uvicorn)/environ | tr '\0' '\n'
```

---

## 11. 設定項目まとめ

| カテゴリ | 設定項目 | コマンド/場所 | 状態確認方法 | 備考 |
|---------|---------|-------------|-------------|------|
| **OS** | タイムゾーン JST | `timedatectl set-timezone Asia/Tokyo` | `timedatectl` | 必須 |
| **OS** | パッケージ更新 | `apt update && apt upgrade` | `apt list --upgradable` | 月次実施推奨 |
| **Python** | バージョン 3.12.x | `pyenv install 3.12.10` | `python --version` | 必須 |
| **Python** | 仮想環境 | `python -m venv fastapi-env` | `which python` | 必須 |
| **Python** | 依存パッケージ | `pip install -r requirements.txt` | `pip list` | 必須 |
| **Node.js** | LTS バージョン | `nvm install --lts` | `node --version` | フロントエンドビルド用 |
| **ODBC** | Driver 18 | Microsoft リポジトリから apt install | `odbcinst -q -d` | Azure SQL 接続に必須 |
| **FastAPI** | uvicorn 起動 | systemd サービス | `systemctl status fxd-platform` | 自動起動設定 |
| **React** | 本番ビルド | `npm run build` | `ls frontend/dist/` | デプロイ時に必要 |
| **Nginx** | リバースプロキシ | `/etc/nginx/sites-available/` | `nginx -t` | SSE 対応設定必須 |
| **SSL** | HTTPS 設定 | certbot | `certbot certificates` | ドメインがある場合 |
| **UFW** | SSH 許可 | `ufw allow 22/tcp` | `ufw status` | 必ず最初に設定 |
| **UFW** | HTTPS 許可 | `ufw allow 443/tcp` | `ufw status` | 必須 |
| **NSG** | SSH を会社 IP のみ | Azure Portal / CLI | Azure Portal NSG 確認 | セキュリティ強化版 |
| **NSG** | 8000 番ポートを閉じる | NSG ルール追加 | Azure Portal NSG 確認 | Nginx 経由のみに制限 |
| **Key Vault** | Managed Identity 設定 | `az vm identity assign` | `az vm identity show` | シークレット管理 |
| **systemd** | 自動起動設定 | `systemctl enable fxd-platform` | `systemctl is-enabled fxd-platform` | 必須 |
| **環境変数** | KEY_VAULT_URL | systemd EnvironmentFile | `systemctl show fxd-platform` | 本番必須 |

---

### よくあるエラーと対処法

| エラー | 原因 | 対処 |
|--------|------|------|
| `Permission denied (publickey)` | PEM キーのパーミッション | `chmod 400 key.pem` |
| `uvicorn: command not found` | 仮想環境が有効でない | `source fastapi-env/bin/activate` |
| `ModuleNotFoundError` | requirements.txt 未インストール | `pip install -r requirements.txt` |
| `ODBC Driver not found` | ODBC ドライバー未インストール | 9章の手順を実行 |
| `502 Bad Gateway` | FastAPI が起動していない | `systemctl restart fxd-platform` |
| `Connection refused` | UFW/NSG でポートがブロック | UFW・NSG 設定を確認 |
| `npm: command not found` | nvm が有効でない | `source ~/.bashrc` |

---

---

## 12. 環境別構成の違い（本番 vs ステージング）

### 12.1 環境比較

| 項目 | staging VM（`vm-fxd-stg`） | production VM（`vm-fxd-prod`） |
|------|--------------------------|-------------------------------|
| VM サイズ | Standard_B2ms（2vCPU/8GB・~$35/月） | Standard_D4s_v3（4vCPU/16GB・~$140/月） |
| ドメイン | 不要（Azure 付与 FQDN または開発者 IP で直接アクセス） | `fxd-platform.example.com` |
| SSL 証明書 | なし（HTTP）または自己署名 | Front Door マネージド証明書（自動発行・自動更新） |
| Front Door + WAF | 不要 | 必要 |
| Nginx | シンプル HTTP 設定（本セクション 12.3） | `nginx/fxd.conf`（SSL + セキュリティヘッダー完全設定） |
| systemd 永続化 | 推奨 | 必須 |
| NSG | 開発者の固定 IP から HTTP/SSH を直接許可 | `AzureFrontDoor.Backend` からのみ HTTPS 許可 |
| Azure Bastion | 省略可（NSG で開発者 IP から SSH 直接許可） | 必須 |
| Redis / VPN Gateway | 省略可 | 必要 |
| VM 夜間自動停止 | 推奨（コスト削減） | 停止しない |
| `cookie_secure` | `False`（HTTP アクセスのため） | `True`（HTTPS 必須） |
| workers（uvicorn） | 1 | 2〜4 |
| Key Vault | `kv-fxd-stg`（ステージング専用） | `kv-fxd-prod` |

---

### 12.2 ステージング VM の NSG 設定

本番は Front Door 経由のみを許可しますが、ステージングは開発者 IP から直接アクセスできます。

```bash
# ステージング NSG 作成
az network nsg create \
  --resource-group rg-fxd-stg \
  --name nsg-fxd-stg \
  --location japaneast

# 開発者固定 IP から HTTP/HTTPS を直接許可
az network nsg rule create \
  --resource-group rg-fxd-stg \
  --nsg-name nsg-fxd-stg \
  --name AllowDevHTTPS \
  --priority 100 --direction Inbound --access Allow \
  --protocol Tcp --destination-port-ranges 443 80 \
  --source-address-prefixes "<開発者の固定 IP>/32"

# SSH も開発者 IP から直接許可（Bastion 不要）
az network nsg rule create \
  --resource-group rg-fxd-stg \
  --nsg-name nsg-fxd-stg \
  --name AllowDevSSH \
  --priority 110 --direction Inbound --access Allow \
  --protocol Tcp --destination-port-ranges 22 \
  --source-address-prefixes "<開発者の固定 IP>/32"

# それ以外はすべて拒否
az network nsg rule create \
  --resource-group rg-fxd-stg \
  --nsg-name nsg-fxd-stg \
  --name DenyAllInbound \
  --priority 4096 --direction Inbound --access Deny \
  --protocol '*' --destination-port-ranges '*' \
  --source-address-prefixes '*'
```

> 開発者の IP が固定でない場合は、GitHub Actions からデプロイする際の IP を確認して追加するか、Bastion を使う構成に切り替えてください。

---

### 12.3 ステージング Nginx 設定（シンプル HTTP）

ドメイン・SSL 証明書は不要です。IP アドレス直接アクセスで動作確認できれば十分です。

```bash
sudo nano /etc/nginx/sites-available/fxd-platform
```

```nginx
server {
    listen 80;
    server_name _;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    client_max_body_size 50M;

    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location ~* ^/api/.*/stream {
        proxy_pass               http://127.0.0.1:8000;
        proxy_buffering          off;
        proxy_cache              off;
        proxy_read_timeout       300s;
        proxy_send_timeout       300s;
        chunked_transfer_encoding on;
        proxy_set_header         Connection '';
        proxy_http_version       1.1;
    }

    location / {
        root      /home/azureuser/fxd-intelligence/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

---

### 12.4 `cookie_secure` の環境別切り替え

`core/auth/router.py` の `response.set_cookie(secure=True)` は HTTPS 必須です。ステージングで HTTP アクセスする場合は `False` にする必要があります。

**`core/config.py` にフラグを追加：**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... 既存の設定 ...

    # HTTP ステージングでは False に設定
    cookie_secure: bool = True

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**`core/auth/router.py` での使用（変更箇所）：**

```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=settings.cookie_secure,  # ← ハードコードせず設定から取得
    samesite="lax",
    max_age=settings.access_token_expire_minutes * 60,
    path="/",
)
```

**ステージング systemd サービスファイル（`/etc/systemd/system/fxd-platform.service`）：**

```ini
[Unit]
Description=FXD Intelligence Platform (FastAPI) - Staging
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/fxd-intelligence
ExecStart=/home/azureuser/fxd-intelligence/fastapi-env/bin/uvicorn \
    core.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
Restart=on-failure
RestartSec=10

Environment="AZURE_CLIENT_ID=<Staging Managed Identity Client ID>"
Environment="KEY_VAULT_URL=https://kv-fxd-stg.vault.azure.net/"
Environment="COOKIE_SECURE=False"

StandardOutput=journal
StandardError=journal
SyslogIdentifier=fxd-platform

[Install]
WantedBy=multi-user.target
```

> **本番との主な違い：** `--workers 1`、`COOKIE_SECURE=False`、`KEY_VAULT_URL` がステージング用 Key Vault を指定。

---

### 12.5 ステージング VM の夜間自動停止（コスト削減）

Standard_B2ms は停止中のコンピュート費用がゼロになります。業務時間外に自動停止することで月額コストを抑えられます。

```bash
# Azure CLI で自動シャットダウン設定（UTC 11:00 = JST 20:00）
az vm auto-shutdown \
  --resource-group rg-fxd-stg \
  --name vm-fxd-stg \
  --time 1100

# 手動停止
az vm deallocate --resource-group rg-fxd-stg --name vm-fxd-stg

# 手動起動
az vm start --resource-group rg-fxd-stg --name vm-fxd-stg
```

> Azure Portal では VM → 「Operations」→「Auto-shutdown」から GUI で設定できます。自動起動が必要な場合は Logic Apps または GitHub Actions のスケジュール実行で対応してください。

---

*このドキュメントは Azure VM（Ubuntu 22.04）上で FastAPI × React を運用するための社内ナレッジです。*
