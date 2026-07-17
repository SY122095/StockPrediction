import { useState, useEffect, useMemo } from 'react'
import {
  Box, Typography, Card, CardContent, Grid, FormControl,
  InputLabel, Select, MenuItem, CircularProgress, Alert, Divider,
  Stack,
} from '@mui/material'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { fetchInstruments, fetchOHLCV, fetchSummary } from '../api/client'

const PERIOD_OPTIONS = [
  { value: 30,  label: '1ヶ月' },
  { value: 90,  label: '3ヶ月' },
  { value: 180, label: '6ヶ月' },
  { value: 365, label: '1年' },
]

function rollingMean(data, key, n) {
  return data.map((d, i) => {
    if (i < n - 1) return { ...d, [`sma${n}`]: null }
    const avg = data.slice(i - n + 1, i + 1).reduce((s, x) => s + (x[key] ?? 0), 0) / n
    return { ...d, [`sma${n}`]: parseFloat(avg.toFixed(2)) }
  })
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function SummaryCard({ label, value, color }) {
  return (
    <Box sx={{ textAlign: 'center' }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h6" fontWeight={700} color={color || 'text.primary'}>{value}</Typography>
    </Box>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <Card sx={{ p: 1.5, minWidth: 120 }}>
      <Typography variant="caption" display="block" mb={0.5} fontWeight={600}>{label}</Typography>
      {payload.map((p) => (
        <Box key={p.name} sx={{ color: p.color, fontSize: 12 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : '-'}
        </Box>
      ))}
    </Card>
  )
}

export default function ChartPage() {
  const [assetClass, setAssetClass] = useState('equity_jp')
  const [symbol, setSymbol]         = useState('')
  const [days, setDays]             = useState(90)

  const { data: instruments = [] } = useQuery({
    queryKey: ['instruments', assetClass],
    queryFn: () => fetchInstruments(assetClass),
  })

  // assetClass が変わったとき、または初回ロード時に先頭銘柄をセット
  useEffect(() => {
    if (instruments.length > 0) {
      setSymbol(instruments[0].symbol)
    }
  }, [assetClass, instruments.length > 0])

  const effectiveSymbol = symbol || instruments[0]?.symbol

  const { data: ohlcv = [], isLoading: loadingOHLCV } = useQuery({
    queryKey: ['ohlcv', effectiveSymbol, days],
    queryFn: () => fetchOHLCV(effectiveSymbol, days),
    enabled: !!effectiveSymbol,
  })

  const { data: summary } = useQuery({
    queryKey: ['summary', effectiveSymbol],
    queryFn: () => fetchSummary(effectiveSymbol),
    enabled: !!effectiveSymbol,
  })

  const chartData = useMemo(() => {
    if (!ohlcv.length) return []
    const base = ohlcv.map((d) => ({
      date:   formatDate(d.date_utc),
      close:  d.close,
      volume: d.volume ? Math.round(d.volume) : 0,
    }))
    return rollingMean(rollingMean(base, 'close', 25), 'close', 75)
  }, [ohlcv])

  const currentName = instruments.find((i) => i.symbol === effectiveSymbol)?.name
  const unit = assetClass === 'equity_jp' ? '円' : 'USD'
  const tickInterval = Math.max(1, Math.floor(chartData.length / 8))

  return (
    <Box>
      <Typography variant="h5" gutterBottom>株価チャート</Typography>

      {/* フィルター */}
      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>アセットクラス</InputLabel>
            <Select
              value={assetClass}
              label="アセットクラス"
              onChange={(e) => { setAssetClass(e.target.value); setSymbol('') }}
            >
              <MenuItem value="equity_jp">🇯🇵 日本株</MenuItem>
              <MenuItem value="crypto">₿ 暗号資産</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>銘柄</InputLabel>
            <Select
              value={effectiveSymbol || ''}
              label="銘柄"
              onChange={(e) => setSymbol(e.target.value)}
            >
              {instruments.map((i) => (
                <MenuItem key={i.symbol} value={i.symbol}>
                  {i.symbol}　{i.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>期間</InputLabel>
            <Select value={days} label="期間" onChange={(e) => setDays(e.target.value)}>
              {PERIOD_OPTIONS.map(({ value, label }) => (
                <MenuItem key={value} value={value}>{label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </CardContent>
      </Card>

      {loadingOHLCV && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {!loadingOHLCV && ohlcv.length === 0 && effectiveSymbol && (
        <Alert severity="info">
          データがありません。管理ページから「データ更新」を実行してください。
        </Alert>
      )}

      {chartData.length > 0 && (
        <Grid container spacing={2}>
          {/* サマリーカード */}
          {summary && (
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Stack direction="row" spacing={3} flexWrap="wrap" alignItems="center">
                    <Box>
                      <Typography variant="h6" fontWeight={700}>{effectiveSymbol}</Typography>
                      <Typography variant="body2" color="text.secondary">{currentName}</Typography>
                    </Box>
                    <Divider orientation="vertical" flexItem />
                    <SummaryCard
                      label="最新終値"
                      value={
                        summary.latest_close != null
                          ? `${unit === '円' ? '¥' : '$'}${summary.latest_close.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                          : '-'
                      }
                    />
                    <SummaryCard
                      label="前日比"
                      value={
                        summary.ret_1d != null
                          ? `${summary.ret_1d >= 0 ? '+' : ''}${(summary.ret_1d * 100).toFixed(2)}%`
                          : '-'
                      }
                      color={summary.ret_1d >= 0 ? 'success.main' : 'error.main'}
                    />
                    <SummaryCard
                      label="5日騰落率"
                      value={
                        summary.ret_5d != null
                          ? `${summary.ret_5d >= 0 ? '+' : ''}${(summary.ret_5d * 100).toFixed(2)}%`
                          : '-'
                      }
                      color={summary.ret_5d >= 0 ? 'success.main' : 'error.main'}
                    />
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* 株価チャート */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>
                  {effectiveSymbol} 終値チャート（SMA 25 / SMA 75）
                </Typography>
                <ResponsiveContainer width="100%" height={380}>
                  <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      interval={tickInterval}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      tickFormatter={(v) => v.toLocaleString()}
                      tick={{ fontSize: 11 }}
                      width={72}
                      label={{ value: unit, angle: -90, position: 'insideLeft', offset: 12, fontSize: 11 }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend verticalAlign="top" height={28} />
                    <Line type="monotone" dataKey="close"  name="終値"  stroke="#1f77b4" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="sma25"  name="SMA25" stroke="#ff7f0e" strokeWidth={1.2} dot={false} strokeDasharray="4 2" />
                    <Line type="monotone" dataKey="sma75"  name="SMA75" stroke="#2171b5" strokeWidth={1.2} dot={false} strokeDasharray="6 3" />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* 出来高 */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>出来高</Typography>
                <ResponsiveContainer width="100%" height={130}>
                  <ComposedChart data={chartData} margin={{ top: 0, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={tickInterval} />
                    <YAxis
                      tickFormatter={(v) =>
                        v >= 1_000_000 ? `${(v / 1_000_000).toFixed(0)}M` : `${(v / 1000).toFixed(0)}K`
                      }
                      tick={{ fontSize: 10 }}
                      width={56}
                    />
                    <Tooltip formatter={(v) => [v.toLocaleString(), '出来高']} />
                    <Bar dataKey="volume" fill="#aec6cf" name="出来高" />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  )
}
