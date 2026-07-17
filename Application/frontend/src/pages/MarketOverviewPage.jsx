import { useState } from 'react'
import {
  Box, Typography, Card, CardContent, Grid, FormControl, InputLabel,
  Select, MenuItem, Chip, LinearProgress, Alert, Stack,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import {
  fetchMacroLatest, fetchSentimentLatest, fetchSupplyDemandLatest,
} from '../api/client'

const ASSET_LABELS = {
  equity_jp: '🇯🇵 日本株',
  crypto:    '₿ 暗号資産',
}

const MACRO_LABELS = {
  fed_funds_rate:   { label: 'FF金利', unit: '%' },
  us10y_yield:      { label: '米10年債利回り', unit: '%' },
  us2y_yield:       { label: '米2年債利回り', unit: '%' },
  us_yield_spread:  { label: '米長短金利差 (10Y-2Y)', unit: '%' },
  us_cpi:           { label: '米CPI', unit: '' },
  us_unemployment:  { label: '米失業率', unit: '%' },
  usdjpy:           { label: 'ドル円', unit: '円' },
}

const SUPPLY_DEMAND_LABELS = {
  foreign_net_ratio:   '外国人売買動向',
  margin_ratio:        '信用倍率',
  short_selling_ratio: '空売り比率',
}

function MetricCard({ title, value, unit, dateUtc, empty }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ pb: '12px !important' }}>
        <Typography variant="caption" color="text.secondary">{title}</Typography>
        {empty ? (
          <Typography variant="body2" color="text.disabled" sx={{ mt: 0.5 }}>未取得</Typography>
        ) : (
          <>
            <Typography variant="h5" fontWeight={700}>
              {value}{unit}
            </Typography>
            {dateUtc && (
              <Typography variant="caption" color="text.secondary">
                {dateUtc.slice(0, 10)} 時点
              </Typography>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function VixGauge({ vix }) {
  if (!vix) {
    return <Alert severity="info">VIXデータがありません。管理パネルから「マクロデータ更新」を実行してください。</Alert>
  }
  const value = vix.value
  const level = value >= 30 ? '高警戒' : value >= 20 ? 'やや警戒' : '平常'
  const color = value >= 30 ? 'error' : value >= 20 ? 'warning' : 'success'
  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h4" fontWeight={700}>{value?.toFixed(1)}</Typography>
        <Chip label={level} color={color} size="small" />
      </Stack>
      <LinearProgress
        variant="determinate"
        value={Math.min(100, (value / 50) * 100)}
        color={color}
        sx={{ height: 8, borderRadius: 4 }}
      />
      <Typography variant="caption" color="text.secondary">
        {vix.date_utc?.slice(0, 10)} 時点 (VIX指数, 目安: 20以上=やや警戒 / 30以上=高警戒)
      </Typography>
    </Box>
  )
}

function FearGreedGauge({ fearGreed }) {
  if (!fearGreed) {
    return <Alert severity="info">Fear&amp;Greed Indexデータがありません。管理パネルから「センチメント更新」を実行してください。</Alert>
  }
  const value = fearGreed.value
  const label = value <= 25 ? '極度の恐怖' : value <= 45 ? '恐怖' : value <= 55 ? '中立' : value <= 75 ? '強欲' : '極度の強欲'
  const color = value <= 25 ? 'error' : value <= 45 ? 'warning' : value <= 55 ? 'default' : value <= 75 ? 'success' : 'success'
  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h4" fontWeight={700}>{value?.toFixed(0)}</Typography>
        <Chip label={label} color={color === 'default' ? undefined : color} size="small" />
      </Stack>
      <LinearProgress variant="determinate" value={value} sx={{ height: 8, borderRadius: 4 }} />
      <Typography variant="caption" color="text.secondary">
        {fearGreed.date_utc?.slice(0, 10)} 時点 (0=極度の恐怖 〜 100=極度の強欲)
      </Typography>
    </Box>
  )
}

export default function MarketOverviewPage() {
  const [assetClass, setAssetClass] = useState('equity_jp')

  const { data: macro } = useQuery({
    queryKey: ['macroLatest'],
    queryFn: fetchMacroLatest,
    refetchInterval: 60_000,
  })

  const { data: sentiment } = useQuery({
    queryKey: ['sentimentLatest', assetClass],
    queryFn: () => fetchSentimentLatest(assetClass),
    refetchInterval: 60_000,
  })

  const { data: supplyDemand } = useQuery({
    queryKey: ['supplyDemandLatest'],
    queryFn: fetchSupplyDemandLatest,
    enabled: assetClass === 'equity_jp',
    refetchInterval: 60_000,
  })

  const macroEntries = Object.entries(MACRO_LABELS)
  const hasAnyMacro = macro && Object.keys(macro).length > 0
  const hasAnySupplyDemand = supplyDemand && Object.keys(supplyDemand).length > 0

  return (
    <Box>
      <Typography variant="h5" gutterBottom>マクロ・センチメント</Typography>

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
        </CardContent>
      </Card>

      {/* マクロ指標 */}
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>マクロ指標 (FRED)</Typography>
      {!hasAnyMacro && (
        <Alert severity="info" sx={{ mb: 2 }}>
          マクロデータがありません。FRED_API_KEY を設定の上、管理パネルから「マクロデータ更新」を実行してください。
        </Alert>
      )}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {macroEntries.map(([key, meta]) => {
          const entry = macro?.[key]
          return (
            <Grid item xs={6} sm={4} md={3} key={key}>
              <MetricCard
                title={meta.label}
                value={entry ? entry.value?.toFixed(2) : null}
                unit={meta.unit}
                dateUtc={entry?.date_utc}
                empty={!entry}
              />
            </Grid>
          )
        })}
      </Grid>

      {/* センチメント */}
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>センチメント</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                {assetClass === 'equity_jp' ? 'VIX指数 (恐怖指数)' : 'Fear & Greed Index (暗号資産)'}
              </Typography>
              {assetClass === 'equity_jp'
                ? <VixGauge vix={sentiment?.vix} />
                : <FearGreedGauge fearGreed={sentiment?.fear_greed} />}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 需給 (日本株のみ) */}
      {assetClass === 'equity_jp' && (
        <>
          <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>需給 (JPX統計)</Typography>
          {!hasAnySupplyDemand && (
            <Alert severity="info" sx={{ mb: 2 }}>
              需給データがありません。管理パネルから「需給データ更新」を実行してください
              （JPXのページ構成によっては自動取得に失敗することがあります。詳細は
              Application/backend/data/jpx_manual/README.md を参照）。
            </Alert>
          )}
          <Grid container spacing={2}>
            {Object.entries(SUPPLY_DEMAND_LABELS).map(([key, label]) => {
              const entry = supplyDemand?.[key]
              return (
                <Grid item xs={12} sm={4} key={key}>
                  <MetricCard
                    title={label}
                    value={entry ? entry.value?.toFixed(2) : null}
                    unit=""
                    dateUtc={entry?.date_utc}
                    empty={!entry}
                  />
                </Grid>
              )
            })}
          </Grid>
        </>
      )}
    </Box>
  )
}
