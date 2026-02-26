import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import ErrorBoundary from '@/components/ErrorBoundary'
import { Toaster } from '@/hooks/use-toast'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Resumes from '@/pages/Resumes'
import Pipeline from '@/pages/Pipeline'
import Interviews from '@/pages/Interviews'
import Analytics from '@/pages/Analytics'
import TimeToHire from '@/pages/TimeToHire'
import Jobs from '@/pages/Jobs'
import Clients from '@/pages/Clients'
import Communications from '@/pages/Communications'
import Settings from '@/pages/Settings'

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <DashboardLayout>{children}</DashboardLayout>
}

function App() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/resumes"
          element={
            <ProtectedRoute>
              <Resumes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipeline"
          element={
            <ProtectedRoute>
              <Pipeline />
            </ProtectedRoute>
          }
        />
        <Route
          path="/interviews"
          element={
            <ProtectedRoute>
              <Interviews />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute>
              <Analytics />
            </ProtectedRoute>
          }
        />
        <Route
          path="/time-to-hire"
          element={
            <ProtectedRoute>
              <TimeToHire />
            </ProtectedRoute>
          }
        />
        <Route
          path="/jobs"
          element={
            <ProtectedRoute>
              <Jobs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/clients"
          element={
            <ProtectedRoute>
              <Clients />
            </ProtectedRoute>
          }
        />
        <Route
          path="/communications"
          element={
            <ProtectedRoute>
              <Communications />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </ErrorBoundary>
  )
}

export default App
