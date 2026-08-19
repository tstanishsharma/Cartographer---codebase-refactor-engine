/**
 * Cartographer — Root App Component
 *
 * Sets up React Router v6 with all 11 pages and lazy loading.
 * Wraps routes in the Layout component for consistent shell.
 */

import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from '@components/layout/Layout'
import { useAuthStore } from '@store/authStore'

// Lazy load all pages for code splitting
const Auth          = lazy(() => import('@pages/Auth'))
const Dashboard     = lazy(() => import('@pages/Dashboard'))
const Repositories  = lazy(() => import('@pages/Repositories'))
const RepositoryGraph = lazy(() => import('@pages/RepositoryGraph'))
const RepositoryExplorer = lazy(() => import('@pages/RepositoryExplorer'))
const Chat          = lazy(() => import('@pages/Chat'))
const RefactorRuns  = lazy(() => import('@pages/RefactorRuns'))
const AgentTrace    = lazy(() => import('@pages/AgentTrace'))
const BlastRadius   = lazy(() => import('@pages/BlastRadius'))
const DiffViewer    = lazy(() => import('@pages/DiffViewer'))
const TestResults   = lazy(() => import('@pages/TestResults'))
const Settings      = lazy(() => import('@pages/Settings'))

// Page loading skeleton
function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )
}

// Auth guard
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/auth" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public */}
          <Route path="/auth" element={<Auth />} />

          {/* Protected — wrapped in app shell Layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="repositories" element={<Repositories />} />
            <Route path="graph" element={<RepositoryGraph />} />
            <Route path="explorer" element={<RepositoryExplorer />} />
            <Route path="chat" element={<Chat />} />
            <Route path="chat/:sessionId" element={<Chat />} />
            <Route path="runs" element={<RefactorRuns />} />
            <Route path="agents" element={<AgentTrace />} />
            <Route path="blast-radius" element={<BlastRadius />} />
            <Route path="diff" element={<DiffViewer />} />
            <Route path="tests" element={<TestResults />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          {/* 404 */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
