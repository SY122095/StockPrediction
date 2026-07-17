import { createTheme } from '@mui/material/styles'

const theme = createTheme({
  palette: {
    primary: {
      main: '#F57C00',   // コーポレートオレンジ
      light: '#FFB74D',
      dark: '#E65100',
      contrastText: '#fff',
    },
    secondary: {
      main: '#546E7A',
    },
    background: {
      default: '#F5F5F5',
      paper: '#FFFFFF',
    },
    success: { main: '#2ca02c' },
    error:   { main: '#d62728' },
  },
  typography: {
    fontFamily: ['"Noto Sans JP"', 'sans-serif'].join(','),
    h5: { fontWeight: 700 },
    h6: { fontWeight: 600 },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: { borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 8, textTransform: 'none', fontWeight: 600 },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: { backgroundColor: '#FFF3E0' },
      },
    },
  },
})

export default theme
