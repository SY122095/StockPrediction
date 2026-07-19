import { useState } from 'react'
import {
  Box, Typography, Card, CardContent, Grid, Button, FormControl,
  InputLabel, Select, MenuItem, Alert, CircularProgress, Divider,
  Stack, Chip,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import ModelTrainingIcon from '@mui/icons-material/ModelTraining'
import AutoGraphIcon from '@mui/icons-material/AutoGraph'
import PublicIcon from '@mui/icons-material/Public'
import MoodIcon from '@mui/icons-material/Mood'
import EventIcon from '@mui/icons-material/Event'
import BarChartIcon from '@mui/icons-material/BarChart'
import ListAltIcon from '@mui/icons-material/ListAlt'
import CloudDownloadIcon from '@mui/icons-material/CloudDownload'
import WhatshotIcon from '@mui/icons-material/Whatshot'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  adminRefresh, adminTrain, adminPredict, fetchHealth, fetchAdminStatus,
  adminRefreshMacro, adminRefreshSentiment, adminRefreshEvents, adminRefreshSupplyDemand,
  adminRefreshUniverse, adminRefreshEquityBroad, adminRunScreening,
} from '../api/client'

const TARGET_LABELS = {
  fwd_ret_5d: '5日先リターン',
  fwd_ret_1d: '1日先リターン',
  fwd_ret_20d: '20日先リターン',
}

function ResultAlert({ result }) {
  if (!result) return null
  const isOk = result.status === 'ok'
  return (
    <Alert severity={isOk ? 'success' : 'error'} sx={{ mt: 1 }}>
      {isOk ? '✓ 完了' : '✗ エラー'}：{JSON.stringify(result, null, 2)}
    </Alert>
  )
}

export default function AdminPage() {
  const [assetClass, setAssetClass] = useState('equity_jp')
  const [target, setTarget]         = useState('fwd_ret_5d')
  const [dataStart, setDataStart]   = useState('2022-01-01')

  const [refreshResult, setRefreshResult] = useState(null)
  const [trainResult,   setTrainResult]   = useState(null)
  const [predictResult, setPredictResult] = useState(null)

  const [macroResult,        setMacroResult]        = useState(null)
  const [sentimentResult,    setSentimentResult]    = useState(null)
  const [eventsResult,       setEventsResult]       = useState(null)
  const [supplyDemandResult, setSupplyDemandResult] = useState(null)

  const [universeResult,     setUniverseResult]     = useState(null)
  const [equityBroadResult,  setEquityBroadResult]  = useState(null)
  const [screeningResult,    setScreeningResult]    = useState(null)

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
    retry: false,
  })

  const { data: adminStatus } = useQuery({
    queryKey: ['adminStatus'],
    queryFn: fetchAdminStatus,
    retry: false,
  })

  const refreshMutation = useMutation({
    mutationFn: () => adminRefresh(dataStart),
    onSuccess: (data) => setRefreshResult(data),
    onError: (e) => setRefreshResult({ status: 'error', message: e.message }),
  })

  const trainMutation = useMutation({
    mutationFn: () => adminTrain({ assetClass, target }),
    onSuccess: (data) => setTrainResult(data),
    onError: (e) => setTrainResult({ status: 'error', message: e.message }),
  })

  const predictMutation = useMutation({
    mutationFn: () => adminPredict({ assetClass, target }),
    onSuccess: (data) => setPredictResult(data),
    onError: (e) => setPredictResult({ status: 'error', message: e.message }),
  })

  const macroMutation = useMutation({
    mutationFn: () => adminRefreshMacro(dataStart),
    onSuccess: (data) => setMacroResult(data),
    onError: (e) => setMacroResult({ status: 'error', message: e.message }),
  })

  const sentimentMutation = useMutation({
    mutationFn: () => adminRefreshSentiment(),
    onSuccess: (data) => setSentimentResult(data),
    onError: (e) => setSentimentResult({ status: 'error', message: e.message }),
  })

  const eventsMutation = useMutation({
    mutationFn: () => adminRefreshEvents(assetClass),
    onSuccess: (data) => setEventsResult(data),
    onError: (e) => setEventsResult({ status: 'error', message: e.message }),
  })

  const supplyDemandMutation = useMutation({
    mutationFn: () => adminRefreshSupplyDemand(),
    onSuccess: (data) => setSupplyDemandResult(data),
    onError: (e) => setSupplyDemandResult({ status: 'error', message: e.message }),
  })

  const universeMutation = useMutation({
    mutationFn: () => adminRefreshUniverse(),
    onSuccess: (data) => setUniverseResult(data),
    onError: (e) => setUniverseResult({ status: 'error', message: e.message }),
  })

  const equityBroadMutation = useMutation({
    mutationFn: () => adminRefreshEquityBroad(),
    onSuccess: (data) => setEquityBroadResult(data),
    onError: (e) => setEquityBroadResult({ status: 'error', message: e.message }),
  })

  const screeningMutation = useMutation({
    mutationFn: () => adminRunScreening(),
    onSuccess: (data) => setScreeningResult(data),
    onError: (e) => setScreeningResult({ status: 'error', message: e.message }),
  })

  const anyLoading = [
    refreshMutation, trainMutation, predictMutation,
    macroMutation, sentimentMutation, eventsMutation, supplyDemandMutation,
    universeMutation, equityBroadMutation, screeningMutation,
  ].some((m) => m.isPending)

  return (
    <Box>
      <Typography variant="h5" gutterBottom>管理パネル</Typography>

      {/* システムステータス */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>システムステータス</Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap">
            <Chip
              label={health ? '● FastAPI: 稼働中' : '○ FastAPI: 停止'}
              color={health ? 'success' : 'error'}
              variant="outlined"
              size="small"
            />
            <Chip label="SQLite: ローカル DB" variant="outlined" size="small" />
            <Chip label="yfinance: フリープラン" variant="outlined" size="small" />
            <Chip label="LightGBM: ローカル学習" variant="outlined" size="small" />
            <Chip
              label={`FRED: ${adminStatus?.fred_configured ? '設定済み' : '未設定 (ダミーキー)'}`}
              color={adminStatus?.fred_configured ? 'success' : 'default'}
              variant="outlined"
              size="small"
            />
            <Chip
              label={`J-Quants: ${adminStatus?.jquants_configured ? '設定済み' : '未設定 (ダミーキー)'}`}
              color={adminStatus?.jquants_configured ? 'success' : 'default'}
              variant="outlined"
              size="small"
            />
          </Stack>
        </CardContent>
      </Card>

      {/* フィルター設定 */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>設定</Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>アセットクラス</InputLabel>
              <Select value={assetClass} label="アセットクラス" onChange={(e) => setAssetClass(e.target.value)}>
                <MenuItem value="equity_jp">🇯🇵 日本株</MenuItem>
                <MenuItem value="crypto">₿ 暗号資産</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>予測ターゲット</InputLabel>
              <Select value={target} label="予測ターゲット" onChange={(e) => setTarget(e.target.value)}>
                {Object.entries(TARGET_LABELS).map(([v, l]) => (
                  <MenuItem key={v} value={v}>{l}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>データ取得開始日</InputLabel>
              <Select value={dataStart} label="データ取得開始日" onChange={(e) => setDataStart(e.target.value)}>
                <MenuItem value="2020-01-01">2020年〜</MenuItem>
                <MenuItem value="2021-01-01">2021年〜</MenuItem>
                <MenuItem value="2022-01-01">2022年〜（推奨）</MenuItem>
                <MenuItem value="2023-01-01">2023年〜</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </CardContent>
      </Card>

      {/* 操作ボタン */}
      <Grid container spacing={2}>

        {/* Step 1: データ更新 */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                Step 1: データ更新
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                yfinance から JP 株式・暗号資産の OHLCV データをダウンロードし、SQLite DB に保存します。
                初回は 5〜10 分かかる場合があります。
              </Typography>
              <Button
                variant="contained"
                startIcon={refreshMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
                onClick={() => { setRefreshResult(null); refreshMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {refreshMutation.isPending ? '更新中...' : 'データ更新'}
              </Button>
              <ResultAlert result={refreshResult} />
            </CardContent>
          </Card>
        </Grid>

        {/* Step 2: モデル学習 */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                Step 2: モデル学習
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                LightGBM のウォークフォワード学習を実行します。
                DB の OHLCV データからテクニカル特徴量を作成して学習します。
                5〜15 分程度かかります。
              </Typography>
              <Button
                variant="contained"
                color="secondary"
                startIcon={trainMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <ModelTrainingIcon />}
                onClick={() => { setTrainResult(null); trainMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {trainMutation.isPending ? '学習中...' : '学習実行'}
              </Button>
              {trainResult?.mean_rank_ic && (
                <Alert severity="success" sx={{ mt: 1 }}>
                  平均 RankIC: {trainResult.mean_rank_ic.toFixed(4)} （目標: 0.03 以上）
                </Alert>
              )}
              {trainResult?.status === 'error' && <ResultAlert result={trainResult} />}
            </CardContent>
          </Card>
        </Grid>

        {/* Step 3: 予測実行 */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                Step 3: 予測実行
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                学習済みモデルで最新日の全銘柄を予測し、ランキングを DB に保存します。
                予測結果は「予測ランキング」ページで確認できます。
              </Typography>
              <Button
                variant="contained"
                color="success"
                startIcon={predictMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <AutoGraphIcon />}
                onClick={() => { setPredictResult(null); predictMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {predictMutation.isPending ? '予測中...' : '予測実行'}
              </Button>
              {predictResult?.predictions_saved > 0 && (
                <Alert severity="success" sx={{ mt: 1 }}>
                  {predictResult.predictions_saved} 銘柄の予測を保存しました
                </Alert>
              )}
              {predictResult?.status === 'error' && <ResultAlert result={predictResult} />}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 追加データソース更新 */}
      <Typography variant="subtitle1" fontWeight={700} sx={{ mt: 4, mb: 1 }}>
        追加データソース更新（マクロ・センチメント・イベント・需給）
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        FRED / J-Quants は .env の APIキーが未設定（ダミー値）の場合、該当ソースのみ 0件でスキップされます。
        VIX (yfinance) と Fear&amp;Greed Index (alternative.me) はキー不要のため常に更新可能です。
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>マクロ更新</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                FRED金利/CPI・yfinance VIX を取得します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={macroMutation.isPending ? <CircularProgress size={16} /> : <PublicIcon />}
                onClick={() => { setMacroResult(null); macroMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {macroMutation.isPending ? '更新中...' : 'マクロデータ更新'}
              </Button>
              <ResultAlert result={macroResult} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>センチメント更新</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                暗号資産の Fear&amp;Greed Index を取得します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={sentimentMutation.isPending ? <CircularProgress size={16} /> : <MoodIcon />}
                onClick={() => { setSentimentResult(null); sentimentMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {sentimentMutation.isPending ? '更新中...' : 'センチメント更新'}
              </Button>
              <ResultAlert result={sentimentResult} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>決算イベント更新</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                J-Quants から決算発表日・EPSサプライズ (PEAD用) を取得します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={eventsMutation.isPending ? <CircularProgress size={16} /> : <EventIcon />}
                onClick={() => { setEventsResult(null); eventsMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {eventsMutation.isPending ? '更新中...' : '決算イベント更新'}
              </Button>
              <ResultAlert result={eventsResult} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>需給データ更新</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                JPX統計 (外国人売買・信用残高・空売り比率) を取得します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={supplyDemandMutation.isPending ? <CircularProgress size={16} /> : <BarChartIcon />}
                onClick={() => { setSupplyDemandResult(null); supplyDemandMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {supplyDemandMutation.isPending ? '更新中...' : '需給データ更新'}
              </Button>
              <ResultAlert result={supplyDemandResult} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 急騰候補スクリーニング (広いユニバース、コア予測パイプラインとは独立) */}
      <Typography variant="subtitle1" fontWeight={700} sx={{ mt: 4, mb: 1 }}>
        急騰候補スクリーニング（広いユニバース）
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        東証全上場銘柄を対象に、時価総額ではなく流動性(売買代金)のみで足切りしたうえで
        ルールベースのスコアでランキングします。上のコア30銘柄の学習/予測とは完全に独立しています。
        <strong>①銘柄マスタ更新 → ②広域株価取得 → ③スクリーニング実行</strong> の順に実行してください。
        ②はJ-Quantsのレート制限(約5req/分)のため、期間によっては数十分〜数時間かかります。
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>① 銘柄マスタ更新</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                J-Quantsから東証上場銘柄一覧(市場区分・業種)を取得します。数秒で完了します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={universeMutation.isPending ? <CircularProgress size={16} /> : <ListAltIcon />}
                onClick={() => { setUniverseResult(null); universeMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {universeMutation.isPending ? '更新中...' : '銘柄マスタ更新'}
              </Button>
              <ResultAlert result={universeResult} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>② 広域株価取得</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                J-Quantsで全銘柄の株価を日付範囲一括取得します。レート制限のため時間がかかります。
              </Typography>
              <Button
                variant="outlined"
                startIcon={equityBroadMutation.isPending ? <CircularProgress size={16} /> : <CloudDownloadIcon />}
                onClick={() => { setEquityBroadResult(null); equityBroadMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {equityBroadMutation.isPending ? '取得中... (時間がかかります)' : '広域株価取得'}
              </Button>
              <ResultAlert result={equityBroadResult} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>③ スクリーニング実行</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                流動性フィルタ + 急騰スコアを計算し、ランキングを保存します。
              </Typography>
              <Button
                variant="outlined"
                startIcon={screeningMutation.isPending ? <CircularProgress size={16} /> : <WhatshotIcon />}
                onClick={() => { setScreeningResult(null); screeningMutation.mutate() }}
                disabled={anyLoading}
                fullWidth
              >
                {screeningMutation.isPending ? '計算中...' : 'スクリーニング実行'}
              </Button>
              <ResultAlert result={screeningResult} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 注意事項 */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>免責事項</Typography>
          <Typography variant="body2" color="text.secondary">
            本システムは研究・学習目的のプロトタイプです。
            モデルの予測精度は保証されず、実際の株価・資産価格の変動と異なる場合があります。
            投資判断には使用しないでください。すべての投資行動は自己責任で行ってください。
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
