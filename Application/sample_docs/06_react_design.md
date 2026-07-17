# ⑥ React（MUI）設計ガイド

作成日：2026-06-02  
バージョン：React 19 / TypeScript 5.9 / MUI 7 / Vite

---

## 目次

1. [カラーシステム・デザイントークン](#1-カラーシステムデザイントークン)
2. [セキュリティ設計（修正案に基づく）](#2-セキュリティ設計)
3. [状態管理設計](#3-状態管理設計)
4. [API 通信設計（SSE 対応）](#4-api-通信設計)
5. [コンポーネント設計](#5-コンポーネント設計)
6. [高速化・パフォーマンス設計](#6-高速化パフォーマンス設計)
7. [テスト設計](#7-テスト設計)
8. [新規アプリ追加手順](#8-新規アプリ追加手順)

---

## 1. カラーシステム・デザイントークン

### 1.1 コーポレートカラー（既存コード準拠）

```typescript
// frontend/src/theme/corporateColors.ts（既存・変更なし）
export const corporateColors = {
  primary: {
    main: '#F57C00',    // オレンジ（メイン）
    light: '#FFB74D',
    dark: '#E65100',
  },
  secondary: {
    main: '#616161',    // グレー
  },
  background: {
    default: '#F4F6F8', // 画面全体の薄いグレー
    paper: '#FFFFFF',   // カード背景
  },
};
```

### 1.2 MUI テーマ設定（統一版）

```typescript
// frontend/src/theme/muiTheme.ts（修正版）
import { createTheme } from "@mui/material/styles";
import { corporateColors } from "./corporateColors";

export const theme = createTheme({
  palette: {
    primary: corporateColors.primary,
    secondary: corporateColors.secondary,
    background: corporateColors.background,
    error: {
      main: '#D32F2F',
    },
    warning: {
      main: '#F57C00',
    },
    success: {
      main: '#388E3C',
    },
  },
  typography: {
    fontFamily: [
      '"Noto Sans JP"',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: { fontSize: '2rem', fontWeight: 700 },
    h2: { fontSize: '1.5rem', fontWeight: 600 },
    h3: { fontSize: '1.25rem', fontWeight: 600 },
    body1: { fontSize: '0.875rem' },
  },
  components: {
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
        size: 'small',
      },
    },
  },
});
```

### 1.3 カラーコード一覧

| 用途 | カラーコード | 変数名 |
|------|------------|--------|
| プライマリ（オレンジ） | `#F57C00` | `primary.main` |
| プライマリライト | `#FFB74D` | `primary.light` |
| プライマリダーク | `#E65100` | `primary.dark` |
| セカンダリ（グレー） | `#616161` | `secondary.main` |
| 背景（全体） | `#F4F6F8` | `background.default` |
| 背景（カード） | `#FFFFFF` | `background.paper` |
| エラー | `#D32F2F` | `error.main` |
| 成功 | `#388E3C` | `success.main` |
| テキスト（主） | `#212121` | `text.primary` |
| テキスト（副） | `#757575` | `text.secondary` |

---

## 2. セキュリティ設計

### 2.1 JWT を localStorage から Cookie へ移行（C-2, H-2 対応）

```typescript
// frontend/src/auth/AuthContext.tsx（修正版）
// Cookie は httpOnly のため JS からは直接読めない
// axiosに withCredentials を設定するだけで自動送信される

import axios from "axios";

// グローバル設定（main.tsx または axiosInstance.ts）
axios.defaults.withCredentials = true;  // Cookie を自動送信
```

```typescript
// frontend/src/auth/axiosInstance.ts（新規追加）
import axios from "axios";

const api = axios.create({
  withCredentials: true,  // httpOnly Cookie を自動送信
  headers: {
    "Content-Type": "application/json",
  },
});

// 401 レスポンス時にログインページへリダイレクト
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 2.2 SSE の認証（C-2 対応）：URL クエリパラメータからの脱却

```typescript
// 修正前（危険）：トークンが URL に露出
// const eventSource = new EventSource(`/api/chat-stream?token=${token}`);

// 修正後：@microsoft/fetch-event-source を使用
// npm install @microsoft/fetch-event-source

import { fetchEventSource } from "@microsoft/fetch-event-source";

const startStream = async (message: string) => {
  await fetchEventSource("/api/project-agent/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",  // Cookie を送信
    body: JSON.stringify({ message }),
    onmessage(ev) {
      const data = JSON.parse(ev.data);
      if (data.type === "chunk") {
        setOutput((prev) => prev + data.content);
      }
      if (data.type === "done") {
        setStreaming(false);
      }
    },
    onerror(err) {
      console.error("SSE error:", err);
      setStreaming(false);
    },
    signal: abortController.signal,  // キャンセル対応
  });
};
```

### 2.3 XSS 対策（C-4 対応）：DOMPurify + react-markdown

```typescript
// npm install dompurify react-markdown remark-gfm
// npm install -D @types/dompurify

// 修正前（危険）
// <Box dangerouslySetInnerHTML={{ __html: marked.parse(content) }} />

// 修正後：react-markdown を使用（dangerouslySetInnerHTML 不要）
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const MarkdownRenderer = ({ content }: { content: string }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      // コードブロックのスタイリング
      code({ node, inline, className, children, ...props }) {
        return inline ? (
          <code
            style={{
              background: "#f4f4f4",
              padding: "2px 4px",
              borderRadius: 4,
            }}
            {...props}
          >
            {children}
          </code>
        ) : (
          <pre style={{ background: "#f4f4f4", padding: 16, borderRadius: 8 }}>
            <code {...props}>{children}</code>
          </pre>
        );
      },
    }}
  >
    {content}
  </ReactMarkdown>
);
```

### 2.4 認証状態管理（M-1 対応）：Zustand による一元管理

```typescript
// frontend/src/auth/useAuthStore.ts
import { create } from "zustand";

interface User {
  id: number;
  email: string;
  username: string;
  user_level: number;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: true }),
  clearAuth: () => set({ user: null, isAuthenticated: false }),
}));
```

```typescript
// frontend/src/auth/useAuth.ts（修正版）
import { useAuthStore } from "./useAuthStore";
import api from "./axiosInstance";

export const useAuth = () => {
  const { user, isAuthenticated, setUser, clearAuth } = useAuthStore();

  const login = async (email: string, password: string) => {
    const res = await api.post("/api/auth/login", { email, password });
    setUser(res.data.user);  // Cookie はバックエンドが自動設定
  };

  const logout = async () => {
    await api.post("/api/auth/logout");
    clearAuth();
  };

  const fetchCurrentUser = async () => {
    try {
      const res = await api.get("/api/auth/me");
      setUser(res.data);
    } catch {
      clearAuth();
    }
  };

  return { user, isAuthenticated, login, logout, fetchCurrentUser };
};
```

---

## 3. 状態管理設計

### 3.1 サーバー状態管理：TanStack Query

```bash
npm install @tanstack/react-query
```

```typescript
// frontend/src/main.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5分間キャッシュ
      retry: 1,
    },
  },
});

root.render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
```

```typescript
// 使用例：案件一覧取得
import { useQuery } from "@tanstack/react-query";
import api from "@/auth/axiosInstance";

export const useProjects = (keyword?: string) =>
  useQuery({
    queryKey: ["projects", keyword],
    queryFn: async () => {
      const res = await api.get("/api/project-agent/projects", {
        params: { keyword },
      });
      return res.data;
    },
  });
```

### 3.2 フォームバリデーション：React Hook Form + Zod

```bash
npm install react-hook-form zod @hookform/resolvers
```

```typescript
// 使用例：ログインフォーム
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().email("有効なメールアドレスを入力してください"),
  password: z.string().min(8, "8文字以上で入力してください"),
});

type LoginFormData = z.infer<typeof loginSchema>;

const LoginForm = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    await login(data.email, data.password);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextField
        {...register("email")}
        error={!!errors.email}
        helperText={errors.email?.message}
        label="メールアドレス"
      />
      ...
    </form>
  );
};
```

---

## 4. API 通信設計

### 4.1 API クライアント設定

```typescript
// frontend/src/lib/api.ts
import axios from "axios";

const api = axios.create({
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 4.2 SSE フック（チャット用）

```typescript
// frontend/src/hooks/useSSEChat.ts
import { useState, useRef, useCallback } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export const useSSEChat = (endpoint: string) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (message: string) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    setIsStreaming(true);

    abortRef.current = new AbortController();

    await fetchEventSource(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ message }),
      signal: abortRef.current.signal,
      onmessage(ev) {
        const data = JSON.parse(ev.data);
        if (data.type === "chunk") {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1].content += data.content;
            return updated;
          });
        }
        if (data.type === "done") {
          setIsStreaming(false);
        }
      },
      onerror() {
        setIsStreaming(false);
      },
    });
  }, [endpoint]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, send, stop };
};
```

---

## 5. コンポーネント設計

### 5.1 ディレクトリ構成

```
frontend/src/apps/appXX_<name>/
├── pages/
│   └── MainPage.tsx     # ページコンポーネント
├── components/
│   ├── InputArea.tsx    # 入力エリア
│   ├── OutputArea.tsx   # 出力エリア
│   └── Sidebar.tsx      # サイドバー（必要に応じて）
├── hooks/
│   └── useAppXX.ts      # アプリ固有のカスタムフック
└── types.ts             # 型定義
```

### 5.2 DataGrid による表示（M-5 対応）

```typescript
// components/CustomerTable.tsx
import { DataGrid, GridColDef } from "@mui/x-data-grid";

interface CustomerTableProps {
  rows: Record<string, unknown>[];
  columns: string[];
}

export const CustomerTable = ({ rows, columns }: CustomerTableProps) => {
  const colDefs: GridColDef[] = columns.map((col) => ({
    field: col,
    headerName: col,
    flex: 1,
    minWidth: 120,
  }));

  return (
    <DataGrid
      rows={rows.map((r, i) => ({ id: i, ...r }))}
      columns={colDefs}
      autoHeight
      pageSizeOptions={[10, 25, 50]}
      initialState={{
        pagination: { paginationModel: { pageSize: 10 } },
      }}
      sx={{
        borderRadius: 2,
        "& .MuiDataGrid-columnHeaders": {
          backgroundColor: "primary.main",
          color: "white",
        },
      }}
    />
  );
};
```

### 5.3 共通レイアウトコンポーネント

```typescript
// frontend/src/apps/base/AppLayout.tsx
import { Box, AppBar, Toolbar, Typography, IconButton } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useNavigate } from "react-router-dom";

interface AppLayoutProps {
  title: string;
  children: React.ReactNode;
}

export const AppLayout = ({ title, children }: AppLayoutProps) => {
  const navigate = useNavigate();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" color="primary">
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate(-1)}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 700 }}>
            {title}
          </Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flex: 1, p: 3, bgcolor: "background.default" }}>
        {children}
      </Box>
    </Box>
  );
};
```

---

## 6. 高速化・パフォーマンス設計

### 6.1 コード分割（React.lazy）

```typescript
// frontend/src/App.tsx
import React, { Suspense, lazy } from "react";
import { CircularProgress, Box } from "@mui/material";

const App701 = lazy(() => import("./apps/app701_business_assistant/pages/Top"));
const App12 = lazy(() => import("./apps/app12_project_management/pages/Top"));

const Loading = () => (
  <Box display="flex" justifyContent="center" mt={10}>
    <CircularProgress color="primary" />
  </Box>
);

// ルーター内で Suspense でラップ
<Suspense fallback={<Loading />}>
  <App701 />
</Suspense>
```

### 6.2 メモ化

```typescript
// 重い計算は useMemo で
const processedData = useMemo(
  () => rows.map((r) => ({ ...r, displayName: r.name.toUpperCase() })),
  [rows]
);

// コールバックは useCallback で
const handleSubmit = useCallback(async (message: string) => {
  await send(message);
}, [send]);

// コンポーネントは React.memo で
const MessageItem = React.memo(({ message }: { message: Message }) => (
  <Box>{message.content}</Box>
));
```

### 6.3 vite.config.ts（本番ビルド最適化）

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-mui": ["@mui/material", "@mui/icons-material"],
          "vendor-query": ["@tanstack/react-query"],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
});
```

---

## 7. テスト設計

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

```typescript
// tests/MarkdownRenderer.test.tsx
import { render, screen } from "@testing-library/react";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";

test("renders markdown content safely", () => {
  render(<MarkdownRenderer content="**太字テスト**" />);
  expect(screen.getByText("太字テスト")).toBeInTheDocument();
});

test("does not render script tags", () => {
  render(<MarkdownRenderer content="<script>alert('xss')</script>" />);
  expect(document.querySelector("script")).toBeNull();
});
```

---

## 8. 新規アプリ追加手順

テンプレートは `templates/react_app/` を参照。  
詳細は **⑦ 新規アプリケーション開発手順** を参照。

### 必要なパッケージ追加

```bash
# セキュリティ関連
npm install @microsoft/fetch-event-source react-markdown remark-gfm

# 状態管理
npm install zustand @tanstack/react-query

# フォームバリデーション
npm install react-hook-form zod @hookform/resolvers

# テスト
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom

# 型定義
npm install -D @types/dompurify
```
