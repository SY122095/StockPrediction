import axios from 'axios'

// Vite proxy: /api/* → http://localhost:8000/*
const api = axios.create({ baseURL: '/api/v1', timeout: 120_000 })

// ---- 銘柄 ----
export const fetchInstruments = (assetClass) =>
  api.get('/stocks', { params: { asset_class: assetClass } }).then((r) => r.data)

export const fetchOHLCV = (symbol, days = 90) =>
  api.get(`/stocks/${symbol}/ohlcv`, { params: { days } }).then((r) => r.data)

export const fetchSummary = (symbol) =>
  api.get(`/stocks/${symbol}/summary`).then((r) => r.data)

// ---- 予測 ----
export const fetchRanking = ({ assetClass, target, topN }) =>
  api
    .get('/predictions/ranking', { params: { asset_class: assetClass, target, top_n: topN } })
    .then((r) => r.data)

export const fetchPredictionHistory = (symbol, target) =>
  api.get(`/predictions/${symbol}`, { params: { target } }).then((r) => r.data)

// ---- 管理 (baseURL が /api/v1 なので /admin/... で /api/v1/admin/... になる) ----
export const adminRefresh = (start = '2022-01-01') =>
  api.post('/admin/refresh', null, { params: { start } }).then((r) => r.data)

export const adminTrain = ({ assetClass, target, nSplits = 5 }) =>
  api
    .post('/admin/train', null, {
      params: { asset_class: assetClass, target, n_splits: nSplits },
    })
    .then((r) => r.data)

export const adminPredict = ({ assetClass, target }) =>
  api
    .post('/admin/predict', null, { params: { asset_class: assetClass, target } })
    .then((r) => r.data)

// ---- ヘルスチェック ----
export const fetchHealth = () =>
  axios.get('/health').then((r) => r.data)

// ---- マクロ ----
export const fetchMacroLatest = () =>
  api.get('/macro/latest').then((r) => r.data)

export const fetchMacroSeries = (seriesId, days = 365) =>
  api.get('/macro/series', { params: { series_id: seriesId, days } }).then((r) => r.data)

// ---- センチメント ----
export const fetchSentimentLatest = (assetClass) =>
  api.get('/sentiment/latest', { params: { asset_class: assetClass } }).then((r) => r.data)

export const fetchSentimentHistory = (indexName, days = 180) =>
  api.get('/sentiment/history', { params: { index_name: indexName, days } }).then((r) => r.data)

// ---- 決算イベント ----
export const fetchUpcomingEarnings = (assetClass = 'equity_jp', withinDays = 14) =>
  api
    .get('/events/earnings/upcoming', { params: { asset_class: assetClass, within_days: withinDays } })
    .then((r) => r.data)

// ---- 需給 (JPX) ----
export const fetchSupplyDemandLatest = (market = 'TSE_ALL') =>
  api.get('/supply-demand/latest', { params: { market } }).then((r) => r.data)

export const fetchSupplyDemandHistory = (metricName, days = 180) =>
  api.get('/supply-demand/history', { params: { metric_name: metricName, days } }).then((r) => r.data)

// ---- 管理: ステータス・追加データ更新 ----
export const fetchAdminStatus = () =>
  api.get('/admin/status').then((r) => r.data)

export const adminRefreshMacro = (start = '2022-01-01') =>
  api.post('/admin/refresh-macro', null, { params: { start } }).then((r) => r.data)

export const adminRefreshSentiment = () =>
  api.post('/admin/refresh-sentiment').then((r) => r.data)

export const adminRefreshEvents = (assetClass = 'equity_jp') =>
  api.post('/admin/refresh-events', null, { params: { asset_class: assetClass } }).then((r) => r.data)

export const adminRefreshSupplyDemand = () =>
  api.post('/admin/refresh-supply-demand').then((r) => r.data)

// ---- 急騰候補スクリーニング (広いユニバース、コア予測パイプラインとは独立) ----
export const fetchScreeningRanking = ({ scoreType = 'composite', marketSegment, topN = 50 }) =>
  api
    .get('/screening/ranking', {
      params: { score_type: scoreType, market_segment: marketSegment || undefined, top_n: topN },
    })
    .then((r) => r.data)

export const adminRefreshUniverse = () =>
  api.post('/admin/refresh-universe').then((r) => r.data)

export const adminRefreshEquityBroad = (start = '2024-05-01') =>
  api.post('/admin/refresh-equity-broad', null, { params: { start } }).then((r) => r.data)

export const adminRunScreening = () =>
  api.post('/admin/run-screening').then((r) => r.data)
