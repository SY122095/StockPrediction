# ① クラウドプラットフォーム設計ガイド

作成日：2026-06-02
更新日：2026-06-17
対象プロジェクト：FXD Intelligence Platform（FastAPI × React）

---

## 目次

1. [必要サービス一覧（現状 vs セキュリティ強化版）](#1-必要サービス一覧)
2. [コスト見積もり](#2-コスト見積もり)
3. [各サービスの設定方法](#3-各サービスの設定方法)
4. [構築フロー](#4-構築フロー)
5. [Azure Bastion / VPN Gateway / WAF 設定コマンド](#5-azure-bastion--vpn-gateway--waf-設定コマンド)

---

## 1. 必要サービス一覧

### 1.1 Azure（現在使用中）

#### 現状構成

| カテゴリ | サービス名 | 用途 | 現状の問題点 |
|----------|-----------|------|-------------|
| AI | Azure OpenAI Service | GPT-4o / o1 / GPT-5 / Embedding | API キーが configs.yaml に平文保存 |
| AI | Azure Document Intelligence | PDF・文書テキスト抽出 | 認証情報が平文 |
| AI | Azure Computer Vision | 画像認識 | 認証情報が平文 |
| AI | Azure AI Search | ベクトルDB・ハイブリッド検索 | （今後追加予定） |
| データ | Azure SQL Database | アプリデータ永続化 | パスワード認証・接続プール未設定 |
| ストレージ | Azure Blob Storage | ファイル・ドキュメント保管 | 接続文字列が平文 |
| コンピュート | Azure Virtual Machine (Linux) | FastAPI + React ホスティング | ファイアウォール設定要確認 |
| 自動化 | Azure Functions | 定期バッチ（SharePoint同期等） | 認証スタブが本番未対応 |
| 認証 | Microsoft Entra ID (Azure AD) | Graph API 認証 | クライアントシークレットが平文 |
| 監視 | なし | — | 未設定 |
| シークレット | なし | — | Key Vault 未使用 |

#### セキュリティ強化版構成

| カテゴリ | サービス名 | 用途 | 追加理由 |
|----------|-----------|------|---------|
| AI | Azure OpenAI Service | GPT-4o / o1 / GPT-5 / Embedding | プライベートエンドポイント化 |
| AI | Azure Document Intelligence | PDF・文書テキスト抽出 | Managed Identity 認証へ移行 |
| AI | Azure Computer Vision | 画像認識 | Managed Identity 認証へ移行 |
| AI | Azure AI Search | ベクトルDB・ハイブリッド検索 | ハイブリッド検索・日本語アナライザー設定 |
| データ | Azure SQL Database | アプリデータ永続化 | Managed Identity + Entra 認証 |
| ストレージ | Azure Blob Storage | ファイル・ドキュメント保管 | Managed Identity 認証 |
| コンピュート | Azure Virtual Machine (Linux) | FastAPI + React ホスティング | NSG・JIT アクセス設定 |
| 自動化 | Azure Functions | 定期バッチ | Managed Identity 有効化 |
| 認証 | Microsoft Entra ID | SSO・Graph API | Managed Identity で秘密鍵不要化 |
| 監視 | Azure Application Insights | APM・トレース・アラート | structlog 連携 |
| 監視 | Azure Monitor | メトリクス・ログ集約 | VM・Functions・SQL 統合監視 |
| シークレット | Azure Key Vault | API キー・接続文字列の集中管理 | CORS・JWT等すべての秘密情報を移行 |
| CDN / WAF | Azure Front Door (Standard) + WAF Policy | 静的アセット配信 + Web アプリファイアウォール | SQLi・XSS・DDoS 防御。WAF Policy を Front Door にアタッチして OWASP ルール適用 |
| キャッシュ | Azure Cache for Redis | セッション・クエリキャッシュ | 会話履歴永続化・高速化 |
| ネットワーク | Azure Virtual Network | プライベートネットワーク | サービス間通信をプライベート化・サブネット分離 |
| **ネットワーク** | **Azure Bastion (Basic)** | パブリック IP なしの安全な SSH/RDP | VM の SSH ポート(22)を NSG で完全閉鎖。Azure Portal 経由ブラウザ SSH のみ許可し総当り攻撃を原理的に防止 |
| **ネットワーク** | **Azure VPN Gateway (VpnGw1)** | 社内ネットワーク ↔ Azure VNet 拠点間 VPN | 社内 PC から Azure VM へプライベート接続。管理アクセスをインターネット非経由に限定（ポイント対サイト VPN も対応） |
| セキュリティ | Azure Defender for Cloud | 脅威検知 | VM・SQL・Storage の脅威対応 |

> **多層防御の考え方（Azure Bastion + VPN Gateway + WAF）**
>
> | レイヤー | サービス | 防御対象 |
> |---------|---------|---------|
> | L7（アプリ層） | Front Door WAF | SQLi・XSS・ボット・プロトコル異常 |
> | L4（ネットワーク層） | NSG + VNet | 不正 IP・ポートスキャン |
> | 管理アクセス | Azure Bastion | SSH/RDP の直接露出を廃止 |
> | 社内接続 | VPN Gateway | インターネット経由の管理を排除 |
>
> **Bastion 導入手順の概要：**
> 1. VNet に `AzureBastionSubnet`（/26 以上）を作成
> 2. Bastion リソースをデプロイ
> 3. NSG でポート 22/3389 のインターネット向きインバウンドを `Deny` に変更
> 4. Azure Portal → VM → 「接続」→「Bastion」から SSH
>
> **VPN Gateway 導入手順の概要：**
> 1. VNet に `GatewaySubnet`（/27 以上）を作成
> 2. VpnGw1 をデプロイ（SKU: VpnGw1、ルートベース）
> 3. ローカルネットワークゲートウェイで社内ルーターの IP・アドレスレンジを登録
> 4. 接続リソースを作成し、事前共有キー (PSK) を Key Vault に保管
> 5. 社内ルーター（Cisco・Fortinet 等）側に Azure の設定を反映

---

### 1.2 Google Cloud Platform (GCP)

#### 現状相当構成（Azure の機能を GCP で置き換え）

| カテゴリ | Azureサービス | GCP相当サービス | 用途 |
|----------|-------------|----------------|------|
| AI/LLM | Azure OpenAI | Vertex AI (Gemini 2.5 Flash/Pro) | 言語モデル推論 |
| AI/文書解析 | Document Intelligence | Document AI | PDF・文書テキスト抽出 |
| AI/検索 | Azure AI Search | Vertex AI Search / AlloyDB+pgvector | ベクトル検索 |
| データ | Azure SQL Database | Cloud SQL (PostgreSQL) | RDB |
| ストレージ | Azure Blob Storage | Cloud Storage | ファイル保管 |
| コンピュート | Azure VM | Compute Engine (e2-standard-2) | アプリホスティング |
| 自動化 | Azure Functions | Cloud Functions (Python) | 定期バッチ |
| 認証 | Microsoft Entra ID | Google Workspace + IAM | 認証・権限管理 |
| 監視 | Application Insights | Cloud Monitoring + Cloud Trace | APM |
| シークレット | Azure Key Vault | Secret Manager | 秘密情報管理 |
| CDN | Azure Front Door | Cloud CDN + Cloud Load Balancing | 高速配信 |
| キャッシュ | Azure Cache for Redis | Memorystore for Redis | キャッシュ |

#### セキュリティ強化版追加サービス（GCP）

| サービス | 用途 |
|---------|------|
| VPC Service Controls | API アクセス境界の設定 |
| Cloud Armor | WAF・DDoS 防御 |
| Binary Authorization | コンテナイメージ署名検証 |
| Artifact Registry | コンテナイメージ管理 |
| Cloud KMS | 暗号鍵管理 |

---

### 1.3 AWS

#### 現状相当構成

| カテゴリ | Azureサービス | AWS相当サービス | 用途 |
|----------|-------------|---------------|------|
| AI/LLM | Azure OpenAI | Amazon Bedrock (Claude 3.5/Nova) | 言語モデル推論 |
| AI/文書解析 | Document Intelligence | Amazon Textract | PDF・文書テキスト抽出 |
| AI/検索 | Azure AI Search | Amazon OpenSearch Service | ベクトル検索 |
| データ | Azure SQL Database | Amazon RDS (SQL Server / PostgreSQL) | RDB |
| ストレージ | Azure Blob Storage | Amazon S3 | ファイル保管 |
| コンピュート | Azure VM | Amazon EC2 (t3.medium) | アプリホスティング |
| 自動化 | Azure Functions | AWS Lambda (Python) | 定期バッチ |
| 認証 | Microsoft Entra ID | Amazon Cognito + IAM | 認証・権限管理 |
| 監視 | Application Insights | Amazon CloudWatch + X-Ray | APM |
| シークレット | Azure Key Vault | AWS Secrets Manager + SSM Parameter Store | 秘密情報管理 |
| CDN | Azure Front Door | Amazon CloudFront | 高速配信 |
| キャッシュ | Azure Cache for Redis | Amazon ElastiCache for Redis | キャッシュ |

#### セキュリティ強化版追加サービス（AWS）

| サービス | 用途 |
|---------|------|
| AWS WAF | Webアプリファイアウォール |
| AWS Shield | DDoS 防御 |
| AWS GuardDuty | 脅威検知 |
| Amazon VPC | プライベートネットワーク |
| AWS KMS | 暗号鍵管理 |

---

## 2. コスト見積もり

### 前提条件
- ユーザー数：社内 30〜50 名（同時接続 5〜10 名）
- 月間 API 呼び出し：GPT-4o 約 10,000 リクエスト、Embedding 約 50,000 リクエスト
- ドキュメント処理：月 100 件（PDF・Excel・Word）
- VM：Ubuntu 22.04 LTS、4 vCPU、16GB RAM 相当

---

### 2.1 Azure コスト見積もり

#### 現状構成

| サービス | プラン/SKU | 月額（概算・USD） | 月額（概算・JPY） |
|---------|-----------|----------------|----------------|
| Azure VM | Standard_D4s_v3 (4vCPU/16GB) | $140 | ¥21,000 |
| Azure OpenAI (GPT-4o) | 10,000 req × $0.01/1K tokens (avg 500 tokens) | $50 | ¥7,500 |
| Azure OpenAI (Embedding) | 50,000 req × $0.00013/1K tokens | $7 | ¥1,050 |
| Azure SQL Database | General Purpose, 2 vCores | $185 | ¥27,750 |
| Azure Blob Storage | LRS, 100GB | $2 | ¥300 |
| Azure Document Intelligence | 100 pages × $0.001 | $1 | ¥150 |
| Azure Functions | Consumption プラン（無料枠内） | $0 | ¥0 |
| **合計** | | **~$385/月** | **~¥57,750/月** |

#### セキュリティ強化版

| 追加サービス | プラン/SKU | 追加月額（概算・USD） | 追加月額（概算・JPY） |
|------------|-----------|------------------|------------------|
| Azure Key Vault | Standard, 10,000 ops | $5 | ¥750 |
| Azure AI Search | Basic プラン | $75 | ¥11,250 |
| Azure Application Insights | 5GB/月 | $8 | ¥1,200 |
| Azure Monitor | 基本メトリクス | $10 | ¥1,500 |
| Azure Cache for Redis | C1 (1GB) | $55 | ¥8,250 |
| Azure Front Door Standard | CDN + WAF Policy（OWASP ルール）| $43 | ¥6,450 |
| Azure VNet + NSG | 基本ネットワーク・サブネット分離 | $5 | ¥750 |
| **Azure Bastion (Basic)** | ブラウザ SSH・パブリック IP 不要 | **$140** | **¥21,000** |
| **Azure VPN Gateway (VpnGw1)** | 拠点間 VPN・ポイント対サイト対応 | **$145** | **¥21,750** |
| **WAF Policy（Front Door）** | OWASP 3.2 ルールセット + Bot Manager | **$8** | **¥1,200** |
| **強化版合計（Bastion/VPN/WAF 込み）** | | **~$879/月** | **~¥131,850/月** |

> **コスト削減のヒント：**
> - Azure Bastion は開発環境では省略可（NSG の JIT アクセスで代替）
> - VPN Gateway は社内 VPN が不要なら省略可（Bastion のみで管理アクセス制御）
> - Bastion + VPN 省略時の強化版合計：~$578/月 → ~¥86,700/月
> - Bastion のみ追加時：~$718/月 → ~¥107,700/月
> - 全セキュリティ強化版（推奨）：~$879/月 → ~¥131,850/月

---

### 2.2 GCP コスト見積もり

#### 現状相当構成

| サービス | プラン/SKU | 月額（概算・USD） | 月額（概算・JPY） |
|---------|-----------|----------------|----------------|
| Compute Engine | e2-standard-4 (4vCPU/16GB) | $110 | ¥16,500 |
| Vertex AI (Gemini 2.5 Flash) | 10,000 req × $0.00015/1K tokens | $8 | ¥1,200 |
| Vertex AI Embedding | 50,000 req × $0.0001/1K tokens | $5 | ¥750 |
| Cloud SQL (PostgreSQL) | db-standard-2, 50GB SSD | $120 | ¥18,000 |
| Cloud Storage | Standard, 100GB | $2 | ¥300 |
| Document AI | 100 pages × $0.0015 | $2 | ¥300 |
| Cloud Functions | 無料枠内 | $0 | ¥0 |
| **合計** | | **~$247/月** | **~¥37,050/月** |

#### セキュリティ強化版

| 追加サービス | 追加月額（概算・USD） | 追加月額（概算・JPY） |
|------------|------------------|------------------|
| Secret Manager | $1 | ¥150 |
| Vertex AI Search | $100 | ¥15,000 |
| Cloud Monitoring | $8 | ¥1,200 |
| Memorystore Redis (1GB) | $50 | ¥7,500 |
| Cloud CDN | $10 | ¥1,500 |
| Cloud Armor | $30 | ¥4,500 |
| **強化版合計** | **~$446/月** | **~¥66,900/月** |

---

### 2.3 AWS コスト見積もり

#### 現状相当構成

| サービス | プラン/SKU | 月額（概算・USD） | 月額（概算・JPY） |
|---------|-----------|----------------|----------------|
| EC2 | t3.xlarge (4vCPU/16GB) | $120 | ¥18,000 |
| Amazon Bedrock (Claude 3.5 Sonnet) | 10,000 req × $0.015/1K tokens | $75 | ¥11,250 |
| Amazon Bedrock Embedding | 50,000 req × $0.0002/1K tokens | $10 | ¥1,500 |
| Amazon RDS (SQL Server SE) | db.t3.medium, 50GB | $180 | ¥27,000 |
| Amazon S3 | Standard, 100GB | $2 | ¥300 |
| Amazon Textract | 100 pages × $0.0015 | $2 | ¥300 |
| Lambda | 無料枠内 | $0 | ¥0 |
| **合計** | | **~$389/月** | **~¥58,350/月** |

#### セキュリティ強化版

| 追加サービス | 追加月額（概算・USD） | 追加月額（概算・JPY） |
|------------|------------------|------------------|
| Secrets Manager | $5 | ¥750 |
| OpenSearch Service (t3.small) | $60 | ¥9,000 |
| CloudWatch | $10 | ¥1,500 |
| ElastiCache Redis (cache.t3.micro) | $20 | ¥3,000 |
| CloudFront | $15 | ¥2,250 |
| WAF + Shield Standard | $20 | ¥3,000 |
| **強化版合計** | **~$519/月** | **~¥77,850/月** |

---

### 2.4 クラウド比較まとめ

| 項目 | Azure | GCP | AWS |
|------|-------|-----|-----|
| **現状相当 月額** | ~¥57,750 | ~¥37,050 | ~¥58,350 |
| **セキュリティ強化版（最小）月額** | ~¥86,700 | ~¥66,900 | ~¥77,850 |
| **セキュリティ強化版（Bastion+VPN+WAF込み）月額** | **~¥131,850** | ~¥92,400 ※ | ~¥104,850 ※ |
| **既存環境との親和性** | ◎（現在使用中） | ○（Gemini連携済み） | △（新規） |
| **Microsoft 365 連携** | ◎（Graph API ネイティブ） | △（別途設定必要） | △（別途設定必要） |
| **Azure OpenAI 利用** | ◎（そのまま使用） | △（別途調達） | △（Bedrock へ移行） |
| **日本語AI性能** | ◎ | ◎ | ○ |
| **Bastion 相当機能** | ◎（Azure Bastion ネイティブ） | △（IAP + OS Login で代替） | △（Systems Manager Session Manager で代替） |
| **VPN Gateway** | ◎（Azure VPN Gateway ネイティブ） | ○（Cloud VPN） | ○（AWS VPN Gateway） |
| **WAF** | ◎（Front Door WAF ネイティブ） | ○（Cloud Armor） | ○（AWS WAF） |
| **運用コスト（習熟度）** | ◎（現チーム習熟済み） | ○ | △ |
| **推奨度** | **第一候補** | 第二候補 | 第三候補 |

※ GCP・AWS の Bastion/VPN/WAF 相当コストは概算（Cloud Armor + IAP + Cloud VPN 等）

> **推奨：Azure 継続使用。** Microsoft 365（SharePoint・Teams・Outlook）との Graph API 連携が最もシームレスで、現チームの習熟度も高い。Bastion・VPN Gateway・WAF はすべて Azure ネイティブで統一管理でき、他クラウドで相当機能を揃えると構成が複雑になりやすい。コスト面では GCP が最安だが、移行コストと学習コストを含めると Azure が最適。

---

## 3. 各サービスの設定方法

> **設定順序について：** 各セクションは依存関係を排除した順番で記載しています。
> VM（3.2）を VNet/NSG の直後に作成することで Managed Identity が早期に確立され、
> 以降は各サービスを作成したタイミングで即座にロールを付与できます。

---

### 3.1 Azure Virtual Network + NSG（基盤ネットワーク）

すべてのリソースが依存するネットワーク基盤です。最初に作成してください。

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「仮想ネットワーク」を選択
2. 名前（`vnet-fxd-prod`）・リージョン（Japan East）・アドレス空間（`10.0.0.0/16`）を入力
3. 「サブネット」タブで以下を追加：
   - `app-subnet`：`10.0.0.0/24`（VM 配置用）
   - `functions-subnet`：`10.0.2.0/24`（Azure Functions VNet 統合用）
   - `private-endpoint-subnet`：`10.0.1.0/24`（SQL・Redis・Storage・AI サービスのプライベートエンドポイント用）
   - `AzureBastionSubnet`：`10.0.255.0/26`（Bastion 専用・**名前変更不可**）
   - `GatewaySubnet`：`10.0.254.0/27`（VPN Gateway 専用・**名前変更不可**）
4. 「セキュリティ」タブ → NSG を各サブネットに関連付け（NSG は後述 CLI で作成後に紐付けも可）

#### NSG ルール一覧

##### nsg-fxd-vm（app-subnet 用）

| 方向 | 優先度 | 名前 | プロトコル | ソース | 宛先ポート | アクション | 説明 |
|------|--------|------|----------|--------|-----------|----------|------|
| Inbound | 100 | AllowHTTPSFromFrontDoor | TCP | AzureFrontDoor.Backend | 443 | Allow | Front Door からの HTTPS |
| Inbound | 110 | AllowHTTPFromFrontDoor | TCP | AzureFrontDoor.Backend | 80 | Allow | HTTP→HTTPS リダイレクト用 |
| Inbound | 200 | AllowBastionSSH | TCP | 10.0.255.0/26 | 22 | Allow | Bastion サブネットからの SSH のみ許可 |
| Inbound | 1000 | DenySSHFromInternet | TCP | Internet | 22 | Deny | インターネットからの直接 SSH を遮断 |
| Inbound | 4096 | DenyAllInbound | * | * | * | Deny | それ以外はすべて拒否 |

##### nsg-fxd-privateendpoint（private-endpoint-subnet 用）

| 方向 | 優先度 | 名前 | プロトコル | ソース | 宛先ポート | アクション | 説明 |
|------|--------|------|----------|--------|-----------|----------|------|
| Inbound | 100 | AllowFromAppSubnet | * | 10.0.0.0/24 | * | Allow | VM からプライベートエンドポイントへ |
| Inbound | 110 | AllowFromFunctionsSubnet | * | 10.0.2.0/24 | * | Allow | Functions からプライベートエンドポイントへ |
| Inbound | 4096 | DenyAllInbound | * | * | * | Deny | それ以外はすべて拒否 |

#### CLI

```bash
# リソースグループ作成
az group create --name rg-fxd-platform --location japaneast

# VNet 作成
az network vnet create \
  --resource-group rg-fxd-platform \
  --name vnet-fxd-prod \
  --location japaneast \
  --address-prefixes 10.0.0.0/16

# VM 用サブネット
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name app-subnet \
  --address-prefixes 10.0.0.0/24

# Functions VNet 統合用サブネット（委任設定必須）
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name functions-subnet \
  --address-prefixes 10.0.2.0/24 \
  --delegations Microsoft.Web/serverFarms

# プライベートエンドポイント用サブネット（ネットワークポリシー無効化必須）
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name private-endpoint-subnet \
  --address-prefixes 10.0.1.0/24 \
  --disable-private-endpoint-network-policies true

# Bastion 用サブネット（名前固定）
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name AzureBastionSubnet \
  --address-prefixes 10.0.255.0/26

# Gateway サブネット（名前固定）
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name GatewaySubnet \
  --address-prefixes 10.0.254.0/27

# --- VM 用 NSG ---
az network nsg create \
  --resource-group rg-fxd-platform \
  --name nsg-fxd-vm \
  --location japaneast

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-vm \
  --name AllowHTTPSFromFrontDoor \
  --priority 100 --direction Inbound --access Allow \
  --protocol Tcp --destination-port-ranges 443 \
  --source-address-prefixes AzureFrontDoor.Backend

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-vm \
  --name AllowHTTPFromFrontDoor \
  --priority 110 --direction Inbound --access Allow \
  --protocol Tcp --destination-port-ranges 80 \
  --source-address-prefixes AzureFrontDoor.Backend

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-vm \
  --name AllowBastionSSH \
  --priority 200 --direction Inbound --access Allow \
  --protocol Tcp --destination-port-ranges 22 \
  --source-address-prefixes 10.0.255.0/26

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-vm \
  --name DenySSHFromInternet \
  --priority 1000 --direction Inbound --access Deny \
  --protocol Tcp --destination-port-ranges 22 \
  --source-address-prefixes Internet

# --- プライベートエンドポイント用 NSG ---
az network nsg create \
  --resource-group rg-fxd-platform \
  --name nsg-fxd-privateendpoint \
  --location japaneast

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-privateendpoint \
  --name AllowFromAppSubnet \
  --priority 100 --direction Inbound --access Allow \
  --protocol '*' --destination-port-ranges '*' \
  --source-address-prefixes 10.0.0.0/24

az network nsg rule create \
  --resource-group rg-fxd-platform --nsg-name nsg-fxd-privateendpoint \
  --name AllowFromFunctionsSubnet \
  --priority 110 --direction Inbound --access Allow \
  --protocol '*' --destination-port-ranges '*' \
  --source-address-prefixes 10.0.2.0/24

# --- NSG をサブネットにアタッチ ---
az network vnet subnet update \
  --resource-group rg-fxd-platform --vnet-name vnet-fxd-prod \
  --name app-subnet --network-security-group nsg-fxd-vm

az network vnet subnet update \
  --resource-group rg-fxd-platform --vnet-name vnet-fxd-prod \
  --name private-endpoint-subnet --network-security-group nsg-fxd-privateendpoint
```

#### プライベート DNS ゾーン（プライベートエンドポイントに必要）

```bash
VNET_ID=$(az network vnet show \
  --resource-group rg-fxd-platform \
  --name vnet-fxd-prod --query id -o tsv)

for ZONE in \
  "privatelink.database.windows.net" \
  "privatelink.blob.core.windows.net" \
  "privatelink.openai.azure.com" \
  "privatelink.cognitiveservices.azure.com" \
  "privatelink.search.windows.net" \
  "privatelink.vaultcore.azure.net" \
  "privatelink.redis.cache.windows.net"; do

  az network private-dns zone create \
    --resource-group rg-fxd-platform --name "$ZONE"

  LINK_NAME="link-$(echo $ZONE | tr '.' '-')"
  az network private-dns link vnet create \
    --resource-group rg-fxd-platform --zone-name "$ZONE" \
    --name "$LINK_NAME" --virtual-network "$VNET_ID" \
    --registration-enabled false
done
```

---

### 3.2 Azure Virtual Machine

VNet・NSG が存在すれば VM は作成できます。ここで Managed Identity を確立し、以降の各サービスを作成するたびに即座にロールを付与します。

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「仮想マシン」を選択
2. 名前（`vm-fxd-prod`）・リージョン（Japan East）・イメージ（Ubuntu Server 22.04 LTS）・サイズ（Standard_D4s_v3）を入力
3. 「管理者アカウント」：SSH 公開キーを設定（パスワード認証は無効化）
4. 「ネットワーク」タブ：VNet `vnet-fxd-prod` の `app-subnet` を選択・パブリック IP は**なし**・NSG は `nsg-fxd-vm` を選択
5. 「管理」タブ：「システム割り当てマネージド ID」を**オン**に設定

#### CLI

```bash
# VM 作成（パブリック IP なし・Managed Identity 付き）
az vm create \
  --resource-group rg-fxd-platform \
  --name vm-fxd-prod \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --vnet-name vnet-fxd-prod \
  --subnet app-subnet \
  --public-ip-address "" \
  --nsg nsg-fxd-vm \
  --admin-username azureuser \
  --ssh-key-values ~/.ssh/id_rsa.pub \
  --assign-identity \
  --location japaneast

# Managed Identity の Object ID を取得（以降のロール付与で使用）
VM_IDENTITY=$(az vm identity show \
  --name vm-fxd-prod \
  --resource-group rg-fxd-platform \
  --query principalId -o tsv)

echo "VM_IDENTITY=$VM_IDENTITY"
# この値を手元にメモしておくこと。以降の 3.3〜3.10 で繰り返し使用する
```

---

### 3.3 Azure Key Vault

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「キー コンテナー」を選択
2. 名前（`kv-fxd-prod`）・リージョン（Japan East）・価格レベル（Standard）を入力
3. 「アクセス構成」タブ → アクセス許可モデルは「Azure RBAC」を選択（推奨）
4. 「ネットワーク アクセス」タブ → 「プライベート エンドポイントと選択されたネットワーク」を選択
   - VNet `vnet-fxd-prod` の `app-subnet` と `functions-subnet` を追加
   - 「信頼された Microsoft サービスがこのファイアウォールをバイパスすることを許可する」をオン
5. 作成後、「アクセス制御（IAM）」→「ロールの割り当ての追加」→ VM の Managed Identity に「キーコンテナー シークレット ユーザー」ロールを付与
6. 「シークレット」メニューから各シークレットを登録（CLI 参照）

#### CLI

```bash
# Key Vault 作成
az keyvault create \
  --name kv-fxd-prod \
  --resource-group rg-fxd-platform \
  --location japaneast \
  --sku standard

# VNet からのアクセスのみ許可
az keyvault network-rule add \
  --name kv-fxd-prod --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod --subnet app-subnet

az keyvault network-rule add \
  --name kv-fxd-prod --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod --subnet functions-subnet

az keyvault update \
  --name kv-fxd-prod --resource-group rg-fxd-platform \
  --default-action Deny --bypass AzureServices

# プライベートエンドポイント作成
KV_ID=$(az keyvault show \
  --name kv-fxd-prod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-kv \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$KV_ID" \
  --group-ids vault --connection-name pe-conn-fxd-kv \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-kv \
  --name dzg-fxd-kv \
  --private-dns-zone "privatelink.vaultcore.azure.net" \
  --zone-name "privatelink.vaultcore.azure.net"

# VM の Managed Identity に読み取り権限を付与（VM は 3.2 で作成済み）
az keyvault set-policy \
  --name kv-fxd-prod \
  --object-id "$VM_IDENTITY" \
  --secret-permissions get list

# シークレット登録（値が確定したものから順次追加）
# ここで登録可能：
az keyvault secret set --vault-name kv-fxd-prod \
  --name "JWT-SECRET-KEY" --value "<ランダム文字列 32 文字以上>"
# 3.4 Entra ID 完了後：GRAPH-CLIENT-SECRET（3.4 CLI で自動登録）
# 3.4.2 DNS 完了後：
az keyvault secret set --vault-name kv-fxd-prod \
  --name "ALLOWED-ORIGINS" --value "https://fxd-platform.example.com"
# 3.5 SQL 完了後：SQL-CONNECTION-STRING
# 3.6 Storage 完了後：STORAGE-CONNECTION-STRING
# 3.7 OpenAI 完了後：AZURE-OPENAI-API-KEY / AZURE-OPENAI-ENDPOINT
```

---

### 3.4 Microsoft Entra ID・カスタムドメイン・Azure DNS・SSL 証明書

---

#### 3.4.1 Entra ID アプリ登録

##### ポータル操作
1. Azure Portal → 「Microsoft Entra ID」→「アプリの登録」→「新規登録」
2. 名前（`fxd-platform-app`）・サポートされるアカウントの種類（シングルテナント）を入力  
   リダイレクト URI は **この時点ではダミー値**（`http://localhost:5173/auth/callback`）を入力  
   → 3.4.2 完了後に `https://fxd-platform.example.com/auth/callback` へ更新すること
3. 「証明書とシークレット」→「新しいクライアント シークレット」で生成し、値を即座に Key Vault に登録（画面を離れると二度と表示されない）
4. 「API のアクセス許可」→「Microsoft Graph」→ 必要な権限（`User.Read`・`Files.ReadWrite`・`Mail.Read` 等）を追加し「管理者の同意を与える」をクリック
5. 「エンタープライズ アプリケーション」→ VM の Managed Identity を検索 → 必要なロールを付与

##### CLI

```bash
# アプリ登録（リダイレクト URI はダミー。3.4.2 完了後に更新すること）
az ad app create \
  --display-name "fxd-platform-app" \
  --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "http://localhost:5173/auth/callback"

APP_ID=$(az ad app list --display-name "fxd-platform-app" --query "[0].appId" -o tsv)

# クライアント シークレット作成（Key Vault に即時登録）
SECRET=$(az ad app credential reset \
  --id "$APP_ID" \
  --display-name "prod-secret-2026" \
  --query password -o tsv)
az keyvault secret set --vault-name kv-fxd-prod \
  --name "GRAPH-CLIENT-SECRET" --value "$SECRET"

# サービス プリンシパル作成
az ad sp create --id "$APP_ID"

# Graph API 権限付与（User.Read）＋管理者同意
az ad app permission add \
  --id "$APP_ID" \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope

az ad app permission admin-consent --id "$APP_ID"

# 3.4.2 完了後にリダイレクト URI を本番用に更新
az ad app update \
  --id "$APP_ID" \
  --web-redirect-uris "https://fxd-platform.example.com/auth/callback"
```

---

#### 3.4.2 カスタムドメイン取得と Azure DNS Zone 設定

##### ドメイン取得

Azure では **App Service ドメイン** を使って Azure Portal 上でドメインの購入・管理・DNS 設定をワンストップで完結できます。  
外部レジストラ（お名前.com 等）からの移管も可能です。詳細な手順は **§3.19 カスタムドメイン・SSL 証明書** を参照してください。

**オプション A：Azure App Service ドメイン（推奨・ポータル完結）**

1. Azure Portal →「リソースの作成」→「App Service ドメイン」を検索・選択
2. ドメイン名を入力して検索 → 取得可能なら購入手続き（年間料金は TLD により異なる）
3. 購入完了と同時に Azure DNS Zone が自動作成される（NS 委任不要）

**オプション B：外部レジストラ（お名前.com 等）+ Azure DNS**

1. 外部レジストラでドメインを取得
2. Azure DNS Zone を作成し、表示された NS レコード 4件 を外部レジストラに設定

> 本ドキュメントでは取得済みドメインを `fxd-platform.example.com` として記載します。

##### Azure DNS Zone 作成

```bash
# DNS ゾーン作成
az network dns zone create \
  --resource-group rg-fxd-platform \
  --name "fxd-platform.example.com"

# ネームサーバー確認（外部レジストラの NS レコードに設定する）
az network dns zone show \
  --resource-group rg-fxd-platform \
  --name "fxd-platform.example.com" \
  --query nameServers
```

> 出力された NS レコード値を外部レジストラに設定します。反映には最大 48 時間かかります。

##### Entra ID テナントへのカスタムドメイン検証

```bash
az ad domain create --domain-name "fxd-platform.example.com"

# 検証用 TXT レコード値を確認
az ad domain show --domain-name "fxd-platform.example.com" \
  --query verificationDnsRecords

# TXT レコードを Azure DNS Zone に登録
az network dns record-set txt add-record \
  --resource-group rg-fxd-platform \
  --zone-name "fxd-platform.example.com" \
  --record-set-name "@" \
  --value "<Entra ID から取得した検証用 TXT レコード値>"

# DNS 伝播後にドメイン検証実行
az ad domain verify --domain-name "fxd-platform.example.com"
```

##### Front Door カスタムドメイン用 DNS レコード設定

> **ルートドメイン（`@`）への CNAME は DNS 仕様上不可**（SOA/NS レコードと共存できないため）。
> Azure DNS の **ALIAS レコード**（A レコード形式）を使用します。

```bash
# Front Door エンドポイントのリソース ID 確認（3.15 で Front Door 作成後に実行）
AFD_ENDPOINT_ID=$(az afd endpoint show \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --endpoint-name fxd-platform \
  --query id -o tsv)

# ルートドメイン（@）→ Front Door への ALIAS レコード
az network dns record-set a create \
  --resource-group rg-fxd-platform \
  --zone-name "fxd-platform.example.com" \
  --name "@" \
  --target-resource "$AFD_ENDPOINT_ID"

# www サブドメインを使う場合は通常の CNAME でも可
# AFD_HOSTNAME=$(az afd endpoint show ... --query hostName -o tsv)
# az network dns record-set cname set-record \
#   --zone-name "fxd-platform.example.com" \
#   --record-set-name "www" --cname "$AFD_HOSTNAME"
```

---

#### 3.4.3 SSL/TLS 証明書

##### オプション A：Azure Front Door マネージド証明書（推奨）

Front Door Standard 以上では `ManagedCertificate` を指定するだけで証明書が自動発行・自動更新されます（追加コスト不要）。詳細は 3.15 を参照してください。

##### オプション B：VM 直接公開時（開発環境・フォールバック）の Let's Encrypt

```bash
# Certbot インストール（VM 上で実行）
sudo apt update && sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d fxd-platform.example.com \
  --non-interactive --agree-tos --email admin@example.com

sudo systemctl status certbot.timer
```

> `nginx/fxd.conf` の `ssl_certificate` パスは Certbot 出力先に合わせてください。

---

### 3.5 Azure Blob Storage（Azure Functions より前に作成する）

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「ストレージ アカウント」を選択
2. 名前（`stfxdprod`）・リージョン（Japan East）・冗長性（LRS）を入力
3. 「詳細」タブ → 「ストレージ アカウント キーへのアクセスを許可する」を**無効化**
4. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet`・ターゲット `blob` を指定
5. 作成後、「コンテナー」メニューから `documents`・`uploads` を作成（パブリック アクセス：プライベート）
6. 「アクセス制御（IAM）」→ VM の Managed Identity に「ストレージ BLOB データ共同作成者」ロールを付与

#### CLI

```bash
az storage account create \
  --name stfxdprod \
  --resource-group rg-fxd-platform \
  --location japaneast \
  --sku Standard_LRS \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2

az storage container create --name documents --account-name stfxdprod --auth-mode login
az storage container create --name uploads   --account-name stfxdprod --auth-mode login

STORAGE_ID=$(az storage account show \
  --name stfxdprod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-stfxdprod-blob \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$STORAGE_ID" \
  --group-ids blob --connection-name pe-conn-stfxdprod-blob \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-stfxdprod-blob \
  --name dzg-stfxdprod-blob \
  --private-dns-zone "privatelink.blob.core.windows.net" \
  --zone-name "privatelink.blob.core.windows.net"

# VM の Managed Identity に Blob 書き込み権限を付与（VM は 3.2 で作成済み）
az role assignment create \
  --assignee "$VM_IDENTITY" \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_ID"
```

#### アプリからの接続（Managed Identity）

```python
from azure.storage.blob import BlobServiceClient
from azure.identity import ManagedIdentityCredential

credential = ManagedIdentityCredential()
client = BlobServiceClient(
    account_url="https://stfxdprod.blob.core.windows.net",
    credential=credential
)
container = client.get_container_client("documents")
with open("sample.pdf", "rb") as f:
    container.upload_blob(name="sample.pdf", data=f, overwrite=True)
```

---

### 3.6 Azure SQL Database

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「SQL データベース」を選択
2. サーバー新規作成：サーバー名（`fxd-platform-sql`）・リージョン（Japan East）・認証方法は「Microsoft Entra 認証のみ」を推奨
3. データベース名（`ai-platform-db`）・コンピューティング層（General Purpose, 2 vCores）を選択
4. 「ネットワーク」タブ → 接続方法「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
5. 作成後、「Microsoft Entra ID」メニューから管理者グループを設定

#### CLI

```bash
az sql server create \
  --name fxd-platform-sql \
  --resource-group rg-fxd-platform \
  --location japaneast \
  --admin-user fxd-admin \
  --admin-password "<複雑なパスワード>"

az sql server update \
  --name fxd-platform-sql --resource-group rg-fxd-platform \
  --set publicNetworkAccess=Disabled

az sql server ad-admin create \
  --resource-group rg-fxd-platform \
  --server-name fxd-platform-sql \
  --display-name "FXD SQL Admin" \
  --object-id "<Entra グループの Object ID>"

az sql db create \
  --resource-group rg-fxd-platform \
  --server fxd-platform-sql \
  --name ai-platform-db \
  --service-objective GP_Gen5_2 \
  --backup-storage-redundancy Local

SQL_SERVER_ID=$(az sql server show \
  --name fxd-platform-sql --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-sql \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$SQL_SERVER_ID" \
  --group-ids sqlServer --connection-name pe-conn-fxd-sql \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-sql \
  --name dzg-fxd-sql \
  --private-dns-zone "privatelink.database.windows.net" \
  --zone-name "privatelink.database.windows.net"
```

#### Managed Identity 接続（セキュリティ強化版）

```python
import struct
from azure.identity import ManagedIdentityCredential
import pyodbc

credential = ManagedIdentityCredential()
token = credential.get_token("https://database.windows.net/.default")
token_bytes = token.token.encode("UTF-16-LE")
token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)

conn_str = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=fxd-platform-sql.database.windows.net;"
    "Database=ai-platform-db;"
    "Encrypt=yes;"
)
conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
```

---

### 3.7 Azure OpenAI Service

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Azure OpenAI」を検索・選択
2. リソースグループ（`rg-fxd-platform`）・リージョン（East US）・名前（`aoai-fxd-prod`）・価格レベル（Standard S0）を入力
3. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
4. 「確認および作成」→「作成」
5. デプロイ完了後、「モデル デプロイ」から GPT-4o・text-embedding-3-large をデプロイ
6. 「キーとエンドポイント」で API キー・エンドポイント URL をコピーして Key Vault に登録
7. 「アクセス制御（IAM）」→ VM の Managed Identity に「Cognitive Services User」ロールを付与

#### CLI

```bash
az cognitiveservices account create \
  --name aoai-fxd-prod \
  --resource-group rg-fxd-platform \
  --kind OpenAI --sku S0 \
  --location eastus

az cognitiveservices account update \
  --name aoai-fxd-prod --resource-group rg-fxd-platform \
  --set properties.publicNetworkAccess=Disabled

AOAI_ID=$(az cognitiveservices account show \
  --name aoai-fxd-prod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-aoai \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$AOAI_ID" \
  --group-ids account --connection-name pe-conn-fxd-aoai \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-aoai \
  --name dzg-fxd-aoai \
  --private-dns-zone "privatelink.openai.azure.com" \
  --zone-name "privatelink.openai.azure.com"

az cognitiveservices account deployment create \
  --name aoai-fxd-prod --resource-group rg-fxd-platform \
  --deployment-name gpt4o-prod \
  --model-name gpt-4o --model-version "2024-11-20" \
  --model-format OpenAI \
  --sku-capacity 40 --sku-name GlobalStandard

# API キー・エンドポイントを Key Vault に登録
AOAI_KEY=$(az cognitiveservices account keys list \
  --name aoai-fxd-prod --resource-group rg-fxd-platform \
  --query key1 -o tsv)
AOAI_ENDPOINT=$(az cognitiveservices account show \
  --name aoai-fxd-prod --resource-group rg-fxd-platform \
  --query properties.endpoint -o tsv)
az keyvault secret set --vault-name kv-fxd-prod --name "AZURE-OPENAI-API-KEY"  --value "$AOAI_KEY"
az keyvault secret set --vault-name kv-fxd-prod --name "AZURE-OPENAI-ENDPOINT" --value "$AOAI_ENDPOINT"

# VM の Managed Identity に Cognitive Services User 権限付与（VM は 3.2 で作成済み）
az role assignment create \
  --assignee "$VM_IDENTITY" \
  --role "Cognitive Services User" \
  --scope "$AOAI_ID"
```

#### アプリからの接続（Key Vault 経由）

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from openai import AzureOpenAI

credential = DefaultAzureCredential()
kv_client = SecretClient(vault_url="https://kv-fxd-prod.vault.azure.net/", credential=credential)

client = AzureOpenAI(
    api_key=kv_client.get_secret("AZURE-OPENAI-API-KEY").value,
    azure_endpoint=kv_client.get_secret("AZURE-OPENAI-ENDPOINT").value,
    api_version="2024-02-01"
)
```

---

### 3.8 Azure AI Search

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Azure AI Search」を選択
2. 名前（`fxd-ai-search`）・リージョン（Japan East）・価格レベル（Basic）を入力
3. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
4. 作成後、「インデックス」メニューから JSON でインデックス定義を登録（日本語アナライザー `ja.microsoft` を設定）
5. 「セマンティック検索」を有効化（Basic プラン以上）
6. 「ID」メニューでシステム割り当て ID を有効化 → Azure OpenAI リソースへの「Cognitive Services OpenAI User」ロールを付与
7. 「アクセス制御（IAM）」→ VM の Managed Identity に「Search Index Data Reader」ロールを付与

#### CLI

```bash
az search service create \
  --name fxd-ai-search --resource-group rg-fxd-platform \
  --sku basic --location japaneast \
  --partition-count 1 --replica-count 1

az search service update \
  --name fxd-ai-search --resource-group rg-fxd-platform \
  --public-access disabled

SEARCH_ID=$(az search service show \
  --name fxd-ai-search --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-search \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$SEARCH_ID" \
  --group-ids searchService --connection-name pe-conn-fxd-search \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-search \
  --name dzg-fxd-search \
  --private-dns-zone "privatelink.search.windows.net" \
  --zone-name "privatelink.search.windows.net"

# VM の Managed Identity に Search Index Data Reader 権限付与
az role assignment create \
  --assignee "$VM_IDENTITY" \
  --role "Search Index Data Reader" \
  --scope "$SEARCH_ID"

# AI Search の Managed Identity → OpenAI への権限付与（OpenAI は 3.7 で作成済み）
SEARCH_IDENTITY=$(az search service show \
  --name fxd-ai-search --resource-group rg-fxd-platform \
  --query identity.principalId -o tsv)
az role assignment create \
  --assignee "$SEARCH_IDENTITY" \
  --role "Cognitive Services OpenAI User" \
  --scope "$AOAI_ID"
```

#### インデックス作成例（日本語対応）

```python
from azure.search.documents.indexes.models import (
    SearchField, SearchFieldDataType
)

index_fields = [
    SearchField(name="id", type=SearchFieldDataType.String, key=True),
    SearchField(name="content", type=SearchFieldDataType.String,
                analyzer_name="ja.microsoft"),
    SearchField(name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True, vector_search_dimensions=3072,
                vector_search_profile_name="hnsw-profile"),
    SearchField(name="source", type=SearchFieldDataType.String, filterable=True),
    SearchField(name="project_id", type=SearchFieldDataType.String, filterable=True),
]
```

---

### 3.9 Azure Document Intelligence

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Document Intelligence」を検索・選択
2. 名前（`docint-fxd-prod`）・リージョン（Japan East）・価格レベル（S0）を入力
3. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
4. 作成後、「キーとエンドポイント」でエンドポイント URL をコピーして Key Vault に登録
5. 「ID」メニューでシステム割り当て ID を有効化 → 「アクセス制御（IAM）」→ VM の Managed Identity に「Cognitive Services User」ロールを付与

#### CLI

```bash
az cognitiveservices account create \
  --name docint-fxd-prod --resource-group rg-fxd-platform \
  --kind FormRecognizer --sku S0 \
  --location japaneast

az cognitiveservices account update \
  --name docint-fxd-prod --resource-group rg-fxd-platform \
  --set properties.publicNetworkAccess=Disabled

DOCINT_ID=$(az cognitiveservices account show \
  --name docint-fxd-prod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-docint \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$DOCINT_ID" \
  --group-ids account --connection-name pe-conn-fxd-docint \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-docint \
  --name dzg-fxd-docint \
  --private-dns-zone "privatelink.cognitiveservices.azure.com" \
  --zone-name "privatelink.cognitiveservices.azure.com"

ENDPOINT=$(az cognitiveservices account show \
  --name docint-fxd-prod --resource-group rg-fxd-platform \
  --query properties.endpoint -o tsv)
az keyvault secret set --vault-name kv-fxd-prod \
  --name "DOCUMENT-INTELLIGENCE-ENDPOINT" --value "$ENDPOINT"

# VM の Managed Identity に Cognitive Services User 権限付与
az role assignment create \
  --assignee "$VM_IDENTITY" \
  --role "Cognitive Services User" \
  --scope "$DOCINT_ID"
```

#### アプリからの接続（Managed Identity）

```python
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.identity import ManagedIdentityCredential

credential = ManagedIdentityCredential()
client = DocumentAnalysisClient(
    endpoint="https://docint-fxd-prod.cognitiveservices.azure.com/",
    credential=credential
)
with open("sample.pdf", "rb") as f:
    poller = client.begin_analyze_document("prebuilt-read", f)
result = poller.result()
for page in result.pages:
    for line in page.lines:
        print(line.content)
```

---

### 3.10 Azure Computer Vision

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Computer Vision」を検索・選択
2. 名前（`cv-fxd-prod`）・リージョン（Japan East）・価格レベル（S1）を入力
3. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
4. 作成後、「キーとエンドポイント」でエンドポイント URL をコピーして Key Vault に登録
5. 「ID」メニューでシステム割り当て ID を有効化 → 「アクセス制御（IAM）」→ VM の Managed Identity に「Cognitive Services User」ロールを付与

#### CLI

```bash
az cognitiveservices account create \
  --name cv-fxd-prod --resource-group rg-fxd-platform \
  --kind ComputerVision --sku S1 \
  --location japaneast

az cognitiveservices account update \
  --name cv-fxd-prod --resource-group rg-fxd-platform \
  --set properties.publicNetworkAccess=Disabled

CV_ID=$(az cognitiveservices account show \
  --name cv-fxd-prod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-cv \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$CV_ID" \
  --group-ids account --connection-name pe-conn-fxd-cv \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-cv \
  --name dzg-fxd-cv \
  --private-dns-zone "privatelink.cognitiveservices.azure.com" \
  --zone-name "privatelink.cognitiveservices.azure.com"

ENDPOINT=$(az cognitiveservices account show \
  --name cv-fxd-prod --resource-group rg-fxd-platform \
  --query properties.endpoint -o tsv)
az keyvault secret set --vault-name kv-fxd-prod \
  --name "COMPUTER-VISION-ENDPOINT" --value "$ENDPOINT"

# VM の Managed Identity に Cognitive Services User 権限付与
az role assignment create \
  --assignee "$VM_IDENTITY" \
  --role "Cognitive Services User" \
  --scope "$CV_ID"
```

#### アプリからの接続（Managed Identity）

```python
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.identity import ManagedIdentityCredential
from msrest.authentication import BasicTokenAuthentication

credential = ManagedIdentityCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default")
client = ComputerVisionClient(
    endpoint="https://cv-fxd-prod.cognitiveservices.azure.com/",
    credentials=BasicTokenAuthentication({"access_token": token.token})
)
```

---

### 3.11 Azure Functions（Blob Storage 作成後に実施）

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「関数アプリ」を選択
2. 名前（`func-fxd-platform`）・ランタイム スタック（Python 3.12）・OS（Linux）・ホスティング プラン（消費量）を選択
3. ストレージ アカウントは既存の `stfxdprod` を指定（3.5 で作成済み）
4. 「ネットワーク」タブ → 「仮想ネットワーク統合を有効にする」をオン → サブネット `functions-subnet` を選択
5. 作成後、「ID」メニュー → システム割り当てマネージド ID を「オン」に設定
6. 「構成」→「アプリケーション設定」で `WEBSITE_TIME_ZONE=Tokyo Standard Time` を追加

#### CLI

```bash
az functionapp create \
  --name func-fxd-platform --resource-group rg-fxd-platform \
  --storage-account stfxdprod \
  --consumption-plan-location japaneast \
  --runtime python --runtime-version 3.12 \
  --functions-version 4 --os-type linux

az functionapp identity assign \
  --name func-fxd-platform --resource-group rg-fxd-platform

az functionapp vnet-integration add \
  --name func-fxd-platform --resource-group rg-fxd-platform \
  --vnet vnet-fxd-prod --subnet functions-subnet

az functionapp config appsettings set \
  --name func-fxd-platform --resource-group rg-fxd-platform \
  --settings WEBSITE_TIME_ZONE="Tokyo Standard Time"
```

---

### 3.12 Azure Cache for Redis

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Azure Cache for Redis」を選択
2. DNS 名（`redis-fxd-prod`）・リージョン（Japan East）・キャッシュ SKU（C1 Standard、1 GB）を入力
3. 「ネットワーク」タブ → 「プライベート エンドポイント」→ サブネット `private-endpoint-subnet` を指定・パブリック アクセスを**無効化**
4. 「詳細設定」タブ：TLS の最低バージョンを「1.2」に設定
5. 作成後、「アクセス キー」をコピーして Key Vault に登録

#### CLI

```bash
az redis create \
  --name redis-fxd-prod --resource-group rg-fxd-platform \
  --location japaneast --sku Standard --vm-size C1 \
  --minimum-tls-version 1.2

REDIS_ID=$(az redis show \
  --name redis-fxd-prod --resource-group rg-fxd-platform \
  --query id -o tsv)

az network private-endpoint create \
  --resource-group rg-fxd-platform --name pe-fxd-redis \
  --vnet-name vnet-fxd-prod --subnet private-endpoint-subnet \
  --private-connection-resource-id "$REDIS_ID" \
  --group-ids redisCache --connection-name pe-conn-fxd-redis \
  --location japaneast

az network private-endpoint dns-zone-group create \
  --resource-group rg-fxd-platform --endpoint-name pe-fxd-redis \
  --name dzg-fxd-redis \
  --private-dns-zone "privatelink.redis.cache.windows.net" \
  --zone-name "privatelink.redis.cache.windows.net"

REDIS_HOST="redis-fxd-prod.redis.cache.windows.net"
REDIS_KEY=$(az redis list-keys \
  --name redis-fxd-prod --resource-group rg-fxd-platform \
  --query primaryKey -o tsv)
az keyvault secret set --vault-name kv-fxd-prod \
  --name "REDIS-CONNECTION-STRING" \
  --value "${REDIS_HOST}:6380,password=${REDIS_KEY},ssl=True"
```

#### アプリからの接続

```python
import redis
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

credential = ManagedIdentityCredential()
kv = SecretClient(vault_url="https://kv-fxd-prod.vault.azure.net/", credential=credential)
conn_str = kv.get_secret("REDIS-CONNECTION-STRING").value

r = redis.from_url(f"rediss://{conn_str}", ssl_cert_reqs=None)
r.set("session:user123", "data", ex=3600)
```

---

### 3.13 Azure Application Insights

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Application Insights」を選択
2. 名前（`appi-fxd-platform`）・リージョン（Japan East）・リソース モード（ワークスペースベース）を選択
3. Log Analytics ワークスペースは新規作成（`log-fxd-platform`）→ ここで作成したワークスペースを 3.14 Azure Monitor でも使用する
4. 作成後、「概要」ページの「接続文字列」をコピーして Key Vault に登録

#### CLI

```bash
# Log Analytics ワークスペース作成（3.14 Azure Monitor でも使用）
az monitor log-analytics workspace create \
  --resource-group rg-fxd-platform \
  --workspace-name log-fxd-platform \
  --location japaneast

# Application Insights 作成（ワークスペースベース）
az monitor app-insights component create \
  --app appi-fxd-platform \
  --location japaneast \
  --resource-group rg-fxd-platform \
  --workspace log-fxd-platform \
  --kind web

# 接続文字列を取得して Key Vault に登録
APPINSIGHTS_CONNSTR=$(az monitor app-insights component show \
  --app appi-fxd-platform \
  --resource-group rg-fxd-platform \
  --query connectionString -o tsv)
az keyvault secret set --vault-name kv-fxd-prod \
  --name "APPLICATIONINSIGHTS-CONNECTION-STRING" \
  --value "$APPINSIGHTS_CONNSTR"
```

---

### 3.14 Azure Monitor

#### ポータル操作
1. Azure Portal → 「モニター」→「アラート」→「アラート ルールの作成」
2. 「スコープ」で監視対象リソース（VM・SQL・Functions 等）を選択
3. 「条件」でメトリクス（CPU 使用率 > 80%、HTTP 5xx エラー数 > 10 等）を設定
4. 「アクション」→「アクション グループの作成」→ 通知先メールアドレス・Teams Webhook を設定
5. 各リソース → 「診断設定」→ Log Analytics ワークスペース（`log-fxd-platform`）に送信するよう設定

#### CLI

```bash
# Log Analytics ワークスペースは 3.13 で作成済み。既存を参照する
WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --resource-group rg-fxd-platform \
  --workspace-name log-fxd-platform \
  --query id -o tsv)

VM_ID=$(az vm show \
  --resource-group rg-fxd-platform \
  --name vm-fxd-prod --query id -o tsv)

az monitor diagnostic-settings create \
  --name diag-vm-fxd \
  --resource "$VM_ID" \
  --workspace "$WORKSPACE_ID" \
  --metrics '[{"category":"AllMetrics","enabled":true}]'

az monitor metrics alert create \
  --name alert-vm-cpu-high \
  --resource-group rg-fxd-platform \
  --scopes "$VM_ID" \
  --condition "avg Percentage CPU > 80" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --description "VM CPU 使用率 80% 超過"
```

---

### 3.15 Azure Front Door Standard + WAF Policy

> **前提：** 3.4 でカスタムドメインと Azure DNS Zone を設定済みであること。ALIAS レコードの追加は Front Door エンドポイント作成後に実施してください（3.4.2 参照）。

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Front Door と CDN プロファイル」→「Azure Front Door」Standard を選択
2. プロファイル名（`afd-fxd-prod`）・エンドポイント名・オリジン（VM のプライベート IP）を設定
3. WAF Policy 新規作成 → モード「検出」で開始・OWASP 3.2 マネージドルールを有効化
4. Front Door エンドポイントの「セキュリティ ポリシー」から WAF Policy をアタッチ
5. 「カスタム ドメイン」→ `fxd-platform.example.com` を追加・証明書タイプ「Front Door マネージド」を選択（SSL 自動発行・自動更新）
6. ログ確認後、WAF Policy を「防止」モードへ移行

> 詳細なコマンドは [セクション 5.3](#53-azure-front-door-waf) を参照。

#### CLI（要点のみ）

```bash
az afd profile create \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --sku Standard_AzureFrontDoor

az afd endpoint create \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --endpoint-name fxd-platform \
  --enabled-state Enabled

# カスタムドメイン追加（Front Door マネージド SSL 証明書で自動発行）
az afd custom-domain create \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --custom-domain-name fxd-platform-custom \
  --host-name "fxd-platform.example.com" \
  --minimum-tls-version TLS12 \
  --certificate-type ManagedCertificate

az network front-door waf-policy create \
  --resource-group rg-fxd-platform \
  --name waf-fxd-prod \
  --sku Standard_AzureFrontDoor \
  --mode Detection

az network front-door waf-policy managed-rules add \
  --policy-name waf-fxd-prod --resource-group rg-fxd-platform \
  --type Microsoft_DefaultRuleSet --version 2.1

# チューニング完了後、Prevention モードへ切り替え
az network front-door waf-policy update \
  --resource-group rg-fxd-platform \
  --name waf-fxd-prod \
  --mode Prevention
```

---

### 3.16 Azure Bastion

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「Azure Bastion」を選択
2. 名前（`bastion-fxd-prod`）・VNet（`vnet-fxd-prod`）を設定（サブネットは `AzureBastionSubnet` が自動選択）
3. パブリック IP アドレス（`pip-bastion-fxd`）を新規作成（Standard SKU）
4. SKU：「Basic」または「Standard」（ファイル転送・コピペも可能）を選択
5. 作成後、VM のページ → 「接続」→「Bastion」タブから SSH 接続

> 詳細な CLI コマンドは [セクション 5.1](#51-azure-bastion) を参照。

#### CLI（要点のみ）

```bash
az network public-ip create \
  --resource-group rg-fxd-platform \
  --name pip-bastion-fxd \
  --sku Standard --location japaneast

az network bastion create \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --public-ip-address pip-bastion-fxd \
  --vnet-name vnet-fxd-prod \
  --location japaneast --sku Basic

az network bastion ssh \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --target-resource-id "<VM のリソース ID>" \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/id_rsa
```

---

### 3.17 Azure VPN Gateway

#### ポータル操作
1. Azure Portal → 「リソースの作成」→「仮想ネットワーク ゲートウェイ」を選択
2. 名前（`vpngw-fxd-prod`）・ゲートウェイの種類「VPN」・VPN の種類「ルート ベース」・SKU（VpnGw1）・VNet（`vnet-fxd-prod`、GatewaySubnet を自動使用）を設定
3. パブリック IP（`pip-vpngw-fxd`）を新規作成（Standard SKU）
4. デプロイに約 **30 分**かかる
5. デプロイ後：「ローカル ネットワーク ゲートウェイ」で社内ルーターの IP・アドレスレンジを登録 → 「接続」リソースを作成して PSK を設定

> 詳細な CLI コマンドは [セクション 5.2](#52-azure-vpn-gateway) を参照。

#### CLI（要点のみ）

```bash
az network public-ip create \
  --resource-group rg-fxd-platform \
  --name pip-vpngw-fxd \
  --sku Standard --location japaneast

az network vnet-gateway create \
  --resource-group rg-fxd-platform \
  --name vpngw-fxd-prod --location japaneast \
  --public-ip-address pip-vpngw-fxd \
  --vnet vnet-fxd-prod \
  --gateway-type Vpn --vpn-type RouteBased \
  --sku VpnGw1 --no-wait

az network local-gateway create \
  --resource-group rg-fxd-platform \
  --name lgw-office \
  --gateway-ip-address <社内ルーターのグローバルIP> \
  --local-address-prefixes 192.168.1.0/24

az network vpn-connection create \
  --resource-group rg-fxd-platform \
  --name conn-office-to-azure \
  --vnet-gateway1 vpngw-fxd-prod \
  --local-gateway2 lgw-office \
  --shared-key "<PSK（Key Vault で管理）>" \
  --connection-type IPsec
```

---

### 3.18 Azure Defender for Cloud

#### ポータル操作
1. Azure Portal → 「Microsoft Defender for Cloud」を開く
2. 「環境設定」→ 対象サブスクリプションを選択 → 「Defender プラン」を開く
3. 保護対象（サーバー・SQL・Storage・Key Vault 等）ごとにプランを「オン」に切り替え
4. 「ワークフローの自動化」でアラート発生時の自動対応（Logic Apps 連携）を設定可能
5. 「セキュリティ スコア」画面で問題点と改善推奨事項を確認・対処

#### CLI

```bash
az security pricing create --name VirtualMachines --tier Standard
az security pricing create --name SqlServers      --tier Standard
az security pricing create --name StorageAccounts --tier Standard
az security pricing create --name KeyVaults       --tier Standard

az security contact create \
  --name "security-contact" \
  --email "<security-team@example.com>" \
  --alert-notifications On \
  --alerts-to-admins On
```

---

### 3.19 カスタムドメイン・SSL 証明書

#### ドメイン取得方法

Azure では **App Service ドメイン** を使うと Azure Portal 上でドメインの購入・管理・DNS 設定をワンストップで完結できる。外部レジストラからの移管も可能。

**オプション A：Azure App Service ドメイン（推奨・ポータル完結）**

1. Azure Portal → 「リソースの作成」→「App Service ドメイン」を検索・選択
2. 希望のドメイン名（例: `fxd-platform.com`）を入力して空き確認
3. 連絡先情報を入力（WHOIS 登録情報）→「作成」
4. 購入後、「DNS ゾーン」が自動作成される（`fxd-platform.com` → Azure DNS ゾーン）
5. DNS ゾーンの A レコードを VM / Front Door のパブリック IP に向ける

**オプション B：外部レジストラ（お名前.com 等）+ Azure DNS**

1. Azure Portal → 「DNS ゾーン」→「作成」→ ドメイン名を入力
2. 作成後に表示された **ネームサーバー（NS レコード）4件** を外部レジストラのネームサーバー設定に登録
3. Azure DNS ゾーン内で A / CNAME レコードを追加

#### SSL 証明書の設定方法

| 方式 | 用途 | 費用 | 手順 |
|------|------|------|------|
| **Front Door マネージド証明書** | 本番推奨 | 無料 | Front Door → カスタム ドメイン追加 → 証明書自動発行 |
| **Let's Encrypt（Certbot）** | VM 直接公開・開発環境 | 無料 | VM 上で `certbot --nginx -d <ドメイン>` |
| **Azure Key Vault + App Service 証明書** | 有料だが管理が容易 | 有料 | App Service 証明書を購入 → Key Vault にインポート → Front Door に紐付け |

#### ポータル操作（Front Door カスタムドメイン）

1. Front Door プロファイル（`afd-fxd-prod`）→「ドメイン」→「ドメインの追加」
2. DNS 管理を「Azure DNS」に設定し、ゾーンからドメインを選択
3. CNAME レコードの検証が完了するとドメインが有効化される
4. 証明書は「マネージド（Front Door）」を選択（自動発行・自動更新）

#### CLI

```bash
# Azure DNS ゾーン作成（App Service ドメイン購入後は自動作成済み）
az network dns zone create \
  --resource-group rg-fxd-platform \
  --name fxd-platform.com

# A レコード追加（Front Door のエンドポイントを向ける場合は CNAME を使う）
FRONTDOOR_HOST="fxd-platform.azurefd.net"
az network dns record-set cname set-record \
  --resource-group rg-fxd-platform \
  --zone-name fxd-platform.com \
  --record-set-name "@" \
  --cname "${FRONTDOOR_HOST}"

# Front Door カスタムドメイン追加
az afd custom-domain create \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --custom-domain-name fxd-platform-custom \
  --host-name fxd-platform.com \
  --certificate-type ManagedCertificate \
  --minimum-tls-version TLS12
```

> **Let's Encrypt（VM 直接公開の場合）：**
> ```bash
> # VM に SSH（Bastion 経由）して実行
> sudo apt install -y certbot python3-certbot-nginx
> sudo certbot --nginx -d fxd-platform.com --non-interactive \
>   --agree-tos --email yamauchi@finx.jp
> sudo certbot renew --dry-run  # 自動更新テスト
> ```

---

## 4. 構築フロー

### 4.1 全体構築ステップ（Azure・セキュリティ強化版）

```
STEP 1：基盤ネットワーク + VM
  └─ リソースグループ作成
  └─ Virtual Network + サブネット設定
       （app-subnet /24、functions-subnet /24、private-endpoint-subnet /24、
         AzureBastionSubnet /26、GatewaySubnet /27）
  └─ プライベート DNS ゾーン一括作成
  └─ NSG 設定（nsg-fxd-vm / nsg-fxd-privateendpoint）
  └─ VM 作成（Ubuntu 22.04、app-subnet、Managed Identity 有効化）
  └─ VM_IDENTITY を取得・記録（以降のロール付与で使用）
  └─ Azure Bastion デプロイ（VM への SSH 接続手段を早期確保）
  └─ Azure VPN Gateway デプロイ（社内接続）

STEP 2：セキュリティ基盤・認証・ドメイン
  └─ Key Vault 作成 → VM identity → 「キーコンテナー シークレット ユーザー」ロール付与
  └─ Blob Storage 作成 → VM identity → 「Storage Blob Data Contributor」ロール付与
  └─ Entra ID アプリ登録（リダイレクト URI はダミー）
  └─ カスタムドメイン取得（Azure App Service ドメイン推奨 or 外部レジストラ → §3.19 参照）
  └─ Azure DNS Zone 作成・NS 委任設定
  └─ Entra ID テナントへのカスタムドメイン検証
  └─ Entra ID アプリのリダイレクト URI を本番 URL に更新

STEP 3：データ基盤
  └─ Azure SQL Database 作成（プライベートエンドポイント）
  └─ Entra 認証設定・テーブル初期化

STEP 4：AI サービス
  └─ Azure OpenAI デプロイ → VM identity → 「Cognitive Services User」ロール付与
  └─ Azure AI Search 作成 → VM identity → 「Search Index Data Reader」ロール付与
                          → Search identity → OpenAI への「Cognitive Services OpenAI User」付与
                          → インデックス設定
  └─ Azure Document Intelligence → VM identity → 「Cognitive Services User」ロール付与
  └─ Azure Computer Vision → VM identity → 「Cognitive Services User」ロール付与
  └─ Key Vault にエンドポイント・API キーを登録

STEP 5：自動化・キャッシュ
  └─ Azure Functions 作成（stfxdprod を使用・functions-subnet VNet 統合）
  └─ Azure Cache for Redis 作成（プライベートエンドポイント）

STEP 6：監視
  └─ Application Insights 作成（Log Analytics ワークスペース含む）
  └─ Azure Monitor アラート設定

STEP 7：フロントエンド保護（WAF）+ ドメイン設定完了
  └─ Azure Front Door Standard プロファイル作成
  └─ カスタムドメイン追加（ManagedCertificate で SSL 自動発行）
  └─ DNS Zone に ALIAS レコード追加（ルートドメイン → Front Door）
  └─ WAF Policy 作成（Detection → Prevention モードに変更）
  └─ OWASP 3.2 ルールセット・Bot Manager ルール有効化

STEP 8：アプリデプロイ
  └─ ② VM設定ガイド に従って環境構築（Python・Node.js・ODBC・Nginx・systemd）
  └─ GitHub Actions CI/CD パイプライン設定
  └─ React ビルド → VM へデプロイ
  └─ FastAPI 起動（systemd サービス化）
  └─ 動作確認・E2E テスト

STEP 9：セキュリティ強化
  └─ Azure Defender for Cloud 有効化
```

### 4.2 環境分離

| 環境 | 用途 | リソースグループ | 備考 |
|------|------|----------------|------|
| development | 開発・デバッグ | rg-fxd-dev | ローカル or 低コスト VM |
| staging | 結合テスト | rg-fxd-stg | 本番同等構成（スケールダウン版） |
| production | 本番 | rg-fxd-prod | セキュリティ強化版フル構成 |

### 4.3 コスト管理

```bash
az consumption budget create \
  --budget-name fxd-monthly-budget \
  --amount 500 \
  --time-grain Monthly \
  --resource-group rg-fxd-platform \
  --notifications '[{"enabled":true,"operator":"GreaterThan","threshold":80,"contactEmails":["<your-email>"]}]'
```

---

## 5. Azure Bastion / VPN Gateway / WAF 設定コマンド

### 5.1 Azure Bastion

```bash
# Bastion 用サブネット作成（既存 VNet に追加する場合）
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name AzureBastionSubnet \
  --address-prefixes 10.0.255.0/26

az network public-ip create \
  --resource-group rg-fxd-platform \
  --name pip-bastion-fxd \
  --sku Standard --location japaneast

az network bastion create \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --public-ip-address pip-bastion-fxd \
  --vnet-name vnet-fxd-prod \
  --location japaneast --sku Basic

az network nsg rule create \
  --resource-group rg-fxd-platform \
  --nsg-name nsg-fxd-vm \
  --name DenySSHFromInternet \
  --priority 1000 --direction Inbound --access Deny \
  --protocol Tcp --destination-port-ranges 22 \
  --source-address-prefixes Internet

az network bastion ssh \
  --resource-group rg-fxd-platform \
  --name bastion-fxd-prod \
  --target-resource-id "/subscriptions/<sub>/resourceGroups/rg-fxd-platform/providers/Microsoft.Compute/virtualMachines/vm-fxd-prod" \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/id_rsa
```

### 5.2 Azure VPN Gateway

```bash
az network vnet subnet create \
  --resource-group rg-fxd-platform \
  --vnet-name vnet-fxd-prod \
  --name GatewaySubnet \
  --address-prefixes 10.0.254.0/27

az network public-ip create \
  --resource-group rg-fxd-platform \
  --name pip-vpngw-fxd \
  --sku Standard --location japaneast

az network vnet-gateway create \
  --resource-group rg-fxd-platform \
  --name vpngw-fxd-prod --location japaneast \
  --public-ip-address pip-vpngw-fxd \
  --vnet vnet-fxd-prod \
  --gateway-type Vpn --vpn-type RouteBased \
  --sku VpnGw1 --no-wait

az network local-gateway create \
  --resource-group rg-fxd-platform \
  --name lgw-office \
  --gateway-ip-address <社内ルーターのグローバルIP> \
  --local-address-prefixes 192.168.1.0/24

az network vpn-connection create \
  --resource-group rg-fxd-platform \
  --name conn-office-to-azure \
  --vnet-gateway1 vpngw-fxd-prod \
  --local-gateway2 lgw-office \
  --shared-key "<事前共有キー（Key Vault で管理）>" \
  --connection-type IPsec

az network vnet-gateway update \
  --resource-group rg-fxd-platform \
  --name vpngw-fxd-prod \
  --client-protocol SSTP IkeV2 \
  --address-prefixes 172.16.0.0/24 \
  --vpn-auth-type Certificate
```

### 5.3 Azure Front Door WAF

```bash
az network front-door waf-policy create \
  --resource-group rg-fxd-platform \
  --name waf-fxd-prod \
  --sku Standard_AzureFrontDoor \
  --mode Prevention

az network front-door waf-policy managed-rules add \
  --policy-name waf-fxd-prod --resource-group rg-fxd-platform \
  --type Microsoft_DefaultRuleSet --version 2.1

az network front-door waf-policy managed-rules add \
  --policy-name waf-fxd-prod --resource-group rg-fxd-platform \
  --type Microsoft_BotManagerRuleSet --version 1.0

az network front-door waf-policy rule create \
  --policy-name waf-fxd-prod --resource-group rg-fxd-platform \
  --name RateLimitRule \
  --priority 100 --rule-type RateLimitRule \
  --action Block \
  --rate-limit-duration OneMin \
  --rate-limit-threshold 100

az afd security-policy create \
  --resource-group rg-fxd-platform \
  --profile-name afd-fxd-prod \
  --security-policy-name sec-policy-fxd \
  --domains "/subscriptions/<sub>/resourceGroups/rg-fxd-platform/providers/Microsoft.Cdn/profiles/afd-fxd-prod/afdEndpoints/fxd-platform" \
  --waf-policy "/subscriptions/<sub>/resourceGroups/rg-fxd-platform/providers/Microsoft.Network/frontDoorWebApplicationFirewallPolicies/waf-fxd-prod"
```

> **WAF チューニングのポイント：**
> - 初期は `Detection` モードで稼働し、ログを Azure Monitor で確認してから `Prevention` モードに切り替える
> - 誤検知（False Positive）が多いルールは `AnomalyScoreThreshold` を調整するか個別に `Exclusion` 設定を追加
> - `/api/auth/login` への Rate Limit は最優先で設定（ブルートフォース防御）

---

*このドキュメントは社内ナレッジとして蓄積するために作成しました。実際の API キー・パスワードは絶対にこのファイルに記載しないでください。*
