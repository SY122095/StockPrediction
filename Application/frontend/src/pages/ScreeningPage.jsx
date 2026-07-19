import { useState } from 'react'
import {
  Box, Typography, Card, CardContent, Grid, FormControl, InputLabel,
  Select, MenuItem, Slider, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, CircularProgress, Alert,
} from '@mui/material'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { fetchScreeningRanking } from '../api/client'

const SCORE_TYPE_LABELS = {
  composite:    '総合スコア',
  volume_spike: '出来高スパイク',
  momentum_5d:  '5日モメンタム',
  breakout_20d: '20日高値ブレイク',
}

const MARKET_SEGMENT_LABELS = {
  '':         'すべて',
  Prime:      'プライム',
  Standard:   'スタンダード',
  Growth:     'グロース',
}

export default function ScreeningPage() {
  const [scoreType, setScoreType]         = useState('composite')
  const [marketSegment, setMarketSegment] = useState('')
  const [topN, setTopN]                   = useState(30)

  const { data, isLoading, error } = useQuery({
    queryKey: ['screeningRanking', scoreType, marketSegment, topN],
    queryFn: () => fetchScreeningRanking({ scoreType, marketSegment, topN }),
    refetchInterval: 60_000,
  })

  const rankings = data?.rankings ?? []
  const chartData = [...rankings]
    .sort((a, b) => a.value - b.value)
    .map((r) => ({ symbol: r.symbol, value: parseFloat(r.value?.toFixed(4)) }))

  return (
    <Box>
      <Typography variant="h5" gutterBottom>急騰候補スクリーニング</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        東証全上場銘柄(流動性フィルタ通過分)を対象に、出来高スパイク・モメンタム・高値ブレイクの
        ルールベース指標でランキングします。LightGBM予測(予測ランキングページ)とは独立した仕組みです。
      </Typography>

      {/* フィルター */}
      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>スコア種別</InputLabel>
            <Select value={scoreType} label="スコア種別" onChange={(e) => setScoreType(e.target.value)}>
              {Object.entries(SCORE_TYPE_LABELS).map(([v, l]) => (
                <MenuItem key={v} value={v}>{l}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>市場区分</InputLabel>
            <Select value={marketSegment} label="市場区分" onChange={(e) => setMarketSegment(e.target.value)}>
              {Object.entries(MARKET_SEGMENT_LABELS).map(([v, l]) => (
                <MenuItem key={v} value={v}>{l}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box sx={{ minWidth: 160 }}>
            <Typography variant="caption" color="text.secondary">
              表示件数: {topN}
            </Typography>
            <Slider
              size="small" value={topN} min={10} max={100} step={10}
              onChange={(_, v) => setTopN(v)} marks
            />
          </Box>

          {data?.as_of_date && (
            <Chip size="small" label={`基準日: ${data.as_of_date.slice(0, 10)}`} variant="outlined" />
          )}
        </CardContent>
      </Card>

      {isLoading && <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}><CircularProgress /></Box>}

      {error && <Alert severity="error" sx={{ mb: 2 }}>データ取得に失敗しました。バックエンドAPIが起動しているか確認してください。</Alert>}

      {!isLoading && !error && rankings.length === 0 && (
        <Alert severity="info">
          スクリーニングデータがありません。「管理」ページから「銘柄マスタ更新 → 広域株価取得 → スクリーニング実行」
          を順に実行してください。
        </Alert>
      )}

      {rankings.length > 0 && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={5}>
            <Card>
              <CardContent sx={{ p: 1 }}>
                <Typography variant="subtitle2" sx={{ px: 1, py: 0.5 }}>
                  {SCORE_TYPE_LABELS[scoreType]} ランキング表
                </Typography>
                <TableContainer sx={{ maxHeight: 600 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell align="center" sx={{ width: 40 }}>順位</TableCell>
                        <TableCell>銘柄コード</TableCell>
                        <TableCell>銘柄名</TableCell>
                        <TableCell>市場区分</TableCell>
                        <TableCell align="right">スコア</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rankings.map((r) => (
                        <TableRow key={r.symbol} hover>
                          <TableCell align="center">
                            <Chip
                              label={r.rank} size="small"
                              color={r.rank <= 3 ? 'primary' : 'default'}
                              variant={r.rank <= 3 ? 'filled' : 'outlined'}
                            />
                          </TableCell>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: 13 }}>{r.symbol}</TableCell>
                          <TableCell sx={{ fontSize: 12 }}>{r.name || '-'}</TableCell>
                          <TableCell sx={{ fontSize: 12 }}>{r.market_segment || '-'}</TableCell>
                          <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                            {r.value?.toFixed(4)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={7}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" gutterBottom>スコア分布</Typography>
                <ResponsiveContainer width="100%" height={Math.max(400, chartData.length * 22)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="symbol" type="category" width={90} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [v, SCORE_TYPE_LABELS[scoreType]]} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {chartData.map((d) => (
                        <Cell key={d.symbol} fill={d.value >= 0 ? '#2ca02c' : '#d62728'} />
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
