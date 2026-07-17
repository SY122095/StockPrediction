import { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  Box, Drawer, AppBar, Toolbar, Typography, List, ListItemButton,
  ListItemIcon, ListItemText, Divider, Chip,
} from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import PublicIcon from '@mui/icons-material/Public'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/client'

const DRAWER_WIDTH = 220

const NAV_ITEMS = [
  { path: '/dashboard', label: '予測ランキング',     icon: <DashboardIcon /> },
  { path: '/chart',     label: '株価チャート',       icon: <ShowChartIcon /> },
  { path: '/market',    label: 'マクロ・センチメント', icon: <PublicIcon /> },
  { path: '/admin',     label: '管理',               icon: <AdminPanelSettingsIcon /> },
]

export default function Layout() {
  const location = useLocation()
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
  })

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* サイドバー */}
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            bgcolor: 'primary.dark',
            color: 'white',
          },
        }}
      >
        <Box sx={{ p: 2, pt: 3 }}>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 700 }}>
            📈 株価予測
          </Typography>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
            v0.1.0 プロトタイプ
          </Typography>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.2)', mb: 1 }} />

        <List dense>
          {NAV_ITEMS.map(({ path, label, icon }) => (
            <ListItemButton
              key={path}
              component={NavLink}
              to={path}
              selected={location.pathname === path}
              sx={{
                mx: 1, borderRadius: 2, mb: 0.5,
                color: 'rgba(255,255,255,0.85)',
                '&.active, &.Mui-selected': {
                  bgcolor: 'rgba(255,255,255,0.15)',
                  color: 'white',
                },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: 36 }}>{icon}</ListItemIcon>
              <ListItemText primary={label} primaryTypographyProps={{ fontSize: 14 }} />
            </ListItemButton>
          ))}
        </List>

        <Box sx={{ position: 'absolute', bottom: 16, left: 0, right: 0, px: 2 }}>
          <Chip
            size="small"
            label={health ? '● API 稼働中' : '○ API 停止'}
            sx={{
              bgcolor: health ? 'rgba(44,160,44,0.3)' : 'rgba(214,39,40,0.3)',
              color: 'white',
              fontSize: 11,
            }}
          />
        </Box>
      </Drawer>

      {/* メインコンテンツ */}
      <Box component="main" sx={{ flexGrow: 1, bgcolor: 'background.default', p: 3 }}>
        <Outlet />
      </Box>
    </Box>
  )
}
