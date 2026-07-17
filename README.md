# 📈 株価予測システム (Kabu Yosoku System)

日本株・暗号資産を対象に、テクニカル・マクロ・センチメント・需給・イベント(決算)データを組み合わせて
LightGBM でリターンを予測する研究用プロトタイプです。データ分析フェーズ (`Analytics/`) と
Web アプリフェーズ (`Application/`) の2部構成になっています。

> ⚠️ **本プロジェクトは研究・学習目的のプロトタイプです。投資助言ではありません。**
> 予測結果の精度は保証されず、実際の値動きと異なる場合があります。投資判断は自己責任で行ってください。

---

## 特徴

- **マルチアセット対応**: 日本株 (東証主要銘柄) / 暗号資産 (BTC/ETH等) を同一パイプラインで予測
- **多面的な特徴量**:
  - テクニカル指標 (SMA/EMA/RSI/MACD/ボリンジャーバンド/出来高/ボラティリティ)
  - マクロ経済指標 (FRED: 政策金利・長短金利差・CPI・失業率・為替)
  - センチメント (VIX, 暗号資産 Fear & Greed Index)
  - イベント特徴量 (決算発表への近接度・EPSサプライズ = PEAD)
  - 需給指標 (JPX統計: 外国人売買動向・信用倍率・空売り比率)
- **リーク防止設計**: マクロ/イベント/需給データはすべて公表ラグを考慮して1日ラグでマージ
- **ウォークフォワード検証**: `TimeSeriesSplit` による時系列を考慮したモデル評価 (Rank IC)
- **無料データソース優先**: 主要データソースはすべて無料枠で利用可能。APIキー未設定でも
  該当データソースのみスキップされ、システム全体は動作し続ける設計 (graceful degradation)
- **FastAPI + React**: REST API バックエンドと MUI ベースの管理・可視化 UI

---

## アーキテクチャ

```
StockPrediction/
├── Analytics/              # データ分析フェーズ (Jupyter notebook)
│   ├── configs/             # 設定 (銘柄・特徴量・モデルパラメータ)
│   ├── funcs/                # 再利用可能な関数群 (データ取得・特徴量・モデル)
│   ├── notebooks/            # 01_data → 11_eda → 21_hypothesis → 31_viz → 41_model → 51_inference
│   ├── data/ processed_data/ results/   # (Git管理外)
│
├── Application/             # Webアプリフェーズ
│   ├── backend/              # FastAPI + SQLAlchemy + LightGBM
│   │   ├── core/               # 設定・DB接続
│   │   ├── lib/                 # 外部データソースアダプタ・特徴量・学習/推論
│   │   ├── models/              # DBモデル・スキーマ
│   │   ├── routers/             # REST APIエンドポイント
│   │   └── services/            # データ更新・学習・予測のオーケストレーション
│   └── frontend/             # React (Vite) + MUI + react-query
│       └── src/pages/           # 予測ランキング / チャート / マクロ・センチメント / 管理
│
└── start.ps1                # セットアップ・起動用 PowerShell スクリプト
```

### データソース

| カテゴリ | ソース | 認証 |
|---|---|---|
| 株価 (日本株/暗号資産) | [yfinance](https://pypi.org/project/yfinance/) | 不要 |
| マクロ経済指標 | [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | 要APIキー (無料) |
| センチメント (株式) | yfinance `^VIX` | 不要 |
| センチメント (暗号資産) | [alternative.me Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/) | 不要 |
| 決算イベント / PEAD | [J-Quants API](https://jpx-jquants.com/) | 要APIキー (無料プランあり) |
| 需給 (投資部門別売買・信用残高・空売り比率) | JPX統計ページ (Excel/CSV) | 不要 (取得失敗時はローカル手動配置ファイルへフォールバック) |

FRED / J-Quants のAPIキーが未設定でも、該当データソースのみが自動的にスキップされ、
テクニカル指標のみでシステムは通常通り動作します。

---

## セットアップ

### 前提

- Python **3.12** 系 (3.13以降は主要ライブラリの対応が不十分な場合があるため非推奨)
- Node.js 18以上 (フロントエンド用)
- Windows PowerShell (`start.ps1` を使う場合)

### クイックスタート (Windows / PowerShell)

```powershell
# 1. 仮想環境作成 + 依存ライブラリ一括インストール (Analytics + Application/backend)
.\start.ps1 -Command setup

# 2. DB初期化 + 初期データ取得 (yfinance)
.\start.ps1 -Command init

# 3. バックエンド + フロントエンド起動
.\start.ps1 -Command all

# 4. モデル学習 → 予測実行
.\start.ps1 -Command train
.\start.ps1 -Command predict

# 5. ブラウザで開く (http://localhost:3000)
.\start.ps1 -Command open
```

その他のコマンド一覧は `.\start.ps1` (引数なし) で確認できます。

### 手動セットアップ (OS非依存)

```bash
# Python仮想環境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r Application/backend/requirements.txt
pip install -r Analytics/requirements.txt

# バックエンド起動
cd Application/backend
cp .env.example .env    # 必要に応じて FRED_API_KEY / JQUANTS_API_KEY を設定
python init_db.py
uvicorn main:app --reload

# フロントエンド起動 (別ターミナル)
cd Application/frontend
npm install
npm run dev
```

### 追加データソースのAPIキー取得

- **FRED**: https://fredaccount.stlouisfed.org/apikeys （メール登録のみ、即時発行）
- **J-Quants**: https://jpx-jquants.com/ （無料プランあり、要登録）

取得後、`Application/backend/.env` (および `Analytics/.env`) の `dummy_replace_me` を実際のキーに置き換えてください。

---

## API概要

FastAPI起動時に自動生成される Swagger UI (`http://localhost:8000/docs`) で全エンドポイントを確認できます。

| エンドポイント | 内容 |
|---|---|
| `GET /api/v1/stocks` | 銘柄一覧 |
| `GET /api/v1/stocks/{symbol}/ohlcv` | 株価時系列 |
| `GET /api/v1/predictions/ranking` | 予測ランキング |
| `GET /api/v1/macro/latest` | マクロ指標スナップショット |
| `GET /api/v1/sentiment/latest` | センチメント指標 (VIX / Fear&Greed) |
| `GET /api/v1/events/earnings/upcoming` | 決算発表が近い銘柄一覧 |
| `GET /api/v1/supply-demand/latest` | 需給指標 (外国人売買・信用倍率・空売り比率) |
| `POST /api/v1/admin/refresh` | 全データソース一括更新 |
| `POST /api/v1/admin/train` / `predict` | モデル学習 / 予測実行 |

---

## 技術スタック

**Analytics**: pandas, scikit-learn, LightGBM/XGBoost/CatBoost, statsmodels, Prophet, JupyterLab

**Backend**: FastAPI, SQLAlchemy, SQLite, LightGBM, pandas, yfinance, requests, BeautifulSoup4

**Frontend**: React 19, Vite, MUI, TanStack Query, Recharts

---

## ロードマップ

- [x] Phase 1: 日本株・暗号資産のテクニカル指標ベース予測 (yfinance)
- [x] Phase 1.5: マクロ・センチメント・決算イベント (PEAD)・需給データの追加
- [ ] Phase 2: EDINET連携によるファンダメンタル分析、TDnet適時開示イベント、ニュースセンチメント
- [ ] Phase 3: FX・コモディティ・米国株への対象拡大

---

## ライセンス・免責事項

本リポジトリは個人の学習・研究目的で公開しています。J-Quants等のデータ提供元の利用規約
(生データの再配布禁止等) に従い、取得したデータそのものの再配布は行わないでください。

本システムが出力する予測・ランキングは投資助言ではなく、その正確性・完全性を保証するものでは
ありません。本システムの利用により生じたいかなる損害についても、作者は責任を負いません。
