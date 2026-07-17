import { useState } from 'react'
import {
  Box, Typography, Card, CardContent, Grid, FormControl, InputLabel,
  Select, MenuItem, Slider, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Paper, CircularProgress, Alert,
} from '@mui/material'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { fetchRanking, fetchUpcomingEarnings } from '../api/client'

const TARGET_LABELS = {
  fwd_ret_5d:  '5日先リターン',
  fwd_ret_1d:  '1日先リターン',
  fwd_ret_20d: '20日先リターン',
}

const ASSET_LABELS = {
  equity_jp: '🇯🇵 日本株',
  crypto:    '₿ 暗号資産',
}

function StatCard({ title, value, sub, color }) {
  return (
    <Card>
      <CardContent sx={{ pb: '12px !important' }}>
        <Typography variant="caption" color="text.secondary">{title}</Typography>
        <Typography variant="h5" fontWeight={700} color={color || 'text.primary'}>
          {value}
        </Typography>
        {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
      </CardContent>
    </Card>
  )
}

function ReturnLabel({ value }) {
  const pct = (value * 100).toFixed(2)
  const color = value >= 0 ? 'success.main' : 'error.main'
  return <Typography variant="body2" color={color} fontWeight={600}>{value >= 0 ? `+${pct}%` : `${pct}%`}</Typography>
}

export default function DashboardPage() {
  const [assetClass, setAssetClass] = useState('equity_jp')
  const [target, setTarget]         = useState('fwd_ret_5d')
  const [topN, setTopN]             = useState(20)

  const { data, isLoading, error } = useQuery({
    queryKey: ['ranking', assetClass, target, topN],
    queryFn: () => fetchRanking({ assetClass, target, topN }),
    refetchInterval: 60_000,
  })

  const { data: upcomingEarnings } = useQuery({
    queryKey: ['upcomingEarnings', assetClass],
    queryFn: () => fetchUpcomingEarnings(assetClass, 14),
    enabled: assetClass === 'equity_jp',
    retry: false,
  })
  const earningsSoonSymbols = new Set((upcomingEarnings ?? []).map((e) => e.symbol))

  const rankings = data?.rankings ?? []
  const avgRet   = rankings.length ? rankings.reduce((s, r) => s + r.predicted_return, 0) / rankings.length : 0
  const posRate  = rankings.length ? rankings.filter((r) => r.predicted_return > 0).length / rankings.length : 0

  const chartData = [...rankings]
    .sort((a, b) => a.predicted_return - b.predicted_return)
    .map((r) => ({ symbol: r.symbol, pct: parseFloat((r.predicted_return * 100).toFixed(2)) }))

  return (
    <Box>
      <Typography variant="h5" gutterBottom>予測ランキング</Typography>

      {/* フィルター */}
      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>アセットクラス</InputLabel>
            <Select value={assetClass} label="アセットクラス" onChange={(e) => setAssetClass(e.target.value)}>
              {Object.entries(ASSET_LABELS).map(([v, l]) => (
                <MenuItem key={v} value={v}>{l}</MenuItem>
              ))}
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

          <Box sx={{ minWidth: 160 }}>
            <Typography variant="caption" color="text.secondary">
              表示件数: {topN}
            </Typography>
            <Slider
              size="small" value={topN} min={5} max={30} step={5}
              onChange={(_, v) => setTopN(v)} marks
            />
          </Box>

          {data?.as_of_date && (
            <Chip
              size="small"
              label={`基準日: ${data.as_of_date.slice(0, 10)}`}
              variant="outlined"
            />
          )}
        </CardContent>
      </Card>

      {isLoading && <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>}

      {error && <Alert severity="error" sx={{ mb: 2 }}>データ取得に失敗しました。バックエンドAPIが起動しているか確認してください。</Alert>}

      {!isLoading && !error && rankings.length === 0 && (
        <Alert severity="info">
          予測データがありません。「管理」ページから「データ更新 → 学習＋予測」を実行してください。
        </Alert>
      )}

      {rankings.length > 0 && (
        <Grid container spacing={2}>
          {/* KPI */}
          <Grid item xs={6} sm={3}>
            <StatCard title="対象銘柄" value={rankings.length} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard
              title="平均予測リターン"
              value={`${avgRet >= 0 ? '+' : ''}${(avgRet * 100).toFixed(2)}%`}
              color={avgRet >= 0 ? 'success.main' : 'error.main'}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard title="上昇予測割合" value={`${(posRate * 100).toFixed(0)}%`} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard
              title="1位予測リターン"
              value={`${rankings[0].predicted_return >= 0 ? '+' : ''}${(rankings[0].predicted_return * 100).toFixed(2)}%`}
              color={rankings[0].predicted_return >= 0 ? 'success.main' : 'error.main'}
              sub={rankings[0].symbol}
            />
          </Grid>

          {/* テーブル */}
          <Grid item xs={12} md={5}>
            <Card>
              <CardContent sx={{ p: 1 }}>
                <Typography variant="subtitle2" sx={{ px: 1, py: 0.5 }}>ランキング表</Typography>
                <TableContainer sx={{ maxHeight: 500 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell align="center" sx={{ width: 40 }}>順位</TableCell>
                        <TableCell>銘柄コード</TableCell>
                        <TableCell>銘柄名</TableCell>
                        <TableCell align="right">予測リターン</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rankings.map((r) => (
                        <TableRow key={r.symbol} hover>
                          <TableCell align="center">
                            <Chip
                              label={r.rank}
                              size="small"
                              color={r.rank <= 3 ? 'primary' : 'default'}
                              variant={r.rank <= 3 ? 'filled' : 'outlined'}
                            />
                          </TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                            {r.symbol}
                            {earningsSoonSymbols.has(r.symbol) && (
                              <Chip
                                label="決算間近"
                                size="small"
                                color="warning"
                                variant="outlined"
                                sx={{ ml: 0.5, height: 18, fontSize: 10 }}
                              />
                            )}
                          </TableCell>
                          <TableCell sx={{ fontSize: 12 }}>{r.name || '-'}</TableCell>
                          <TableCell align="right">
                            <ReturnLabel value={r.predicted_return} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* バーチャート */}
          <Grid item xs={12} md={7}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>予測リターン分布</Typography>
                <ResponsiveContainer width="100%" height={Math.max(400, chartData.length * 22)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis
                      type="number"
                      tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}%`}
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis
                      dataKey="symbol"
                      type="category"
                      width={90}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip
                      formatter={(v) => [`${v > 0 ? '+' : ''}${v}%`, '予測リターン']}
                    />
                    <ReferenceLine x={0} stroke="#333" />
                    <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                      {chartData.map((d) => (
                        <Cell key={d.symbol} fill={d.pct >= 0 ? '#2ca02c' : '#d62728'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  )
}
