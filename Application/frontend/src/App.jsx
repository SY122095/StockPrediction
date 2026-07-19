import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ChartPage from './pages/ChartPage'
import MarketOverviewPage from './pages/MarketOverviewPage'
import ScreeningPage from './pages/ScreeningPage'
import AdminPage from './pages/AdminPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="chart" element={<ChartPage />} />
        <Route path="market" element={<MarketOverviewPage />} />
        <Route path="screening" element={<ScreeningPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
    </Routes>
  )
}
