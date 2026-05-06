import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import JobRedirect from '@/components/JobRedirect'
import ErrorBoundary from '@/components/ErrorBoundary'
import { Toaster } from '@/hooks/use-toast'

const Login = lazy(() => import('@/pages/Login'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Resumes = lazy(() => import('@/pages/Resumes'))
const Pipeline = lazy(() => import('@/pages/Pipeline'))
const Interviews = lazy(() => import('@/pages/Interviews'))
const Analytics = lazy(() => import('@/pages/Analytics'))
const Jobs = lazy(() => import('@/pages/Jobs'))
const Clients = lazy(() => import('@/pages/Clients'))
const Communications = lazy(() => import('@/pages/Communications'))
const EmailTemplates = lazy(() => import('@/pages/EmailTemplates'))
const Settings = lazy(() => import('@/pages/Settings'))
const Profile = lazy(() => import('@/pages/Profile'))
const AdminUsers = lazy(() => import('@/pages/AdminUsers'))
const Wallet = lazy(() => import('@/pages/Wallet'))
const SuperAdminDashboard = lazy(() => import('@/pages/SuperAdminDashboard'))
const Agencies = lazy(() => import('@/pages/Agencies'))
const Pricing = lazy(() => import('@/pages/Pricing'))
const SuperAdminDataPage = lazy(() => import('@/pages/SuperAdminDataPage'))

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  )
}

function getDefaultRouteForUser(user) {
  if (user?.role === 'super_admin') return '/super-admin'
  if (user?.role === 'admin') return '/'
  return '/resumes'
}

function ProtectedRoute({ children, superAdminOnly = false, userOnly = false, adminOnly = false }) {
  const { isAuthenticated, loading, user } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (superAdminOnly && user?.role !== 'super_admin') return <Navigate to={getDefaultRouteForUser(user)} replace />
  if (adminOnly && user?.role !== 'admin') return <Navigate to={getDefaultRouteForUser(user)} replace />
  if (userOnly && (user?.role === 'super_admin' || user?.role === 'admin')) return <Navigate to={getDefaultRouteForUser(user)} replace />

  return <DashboardLayout>{children}</DashboardLayout>
}

function App() {
  const { isAuthenticated, loading, user } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={isAuthenticated ? <Navigate to={getDefaultRouteForUser(user)} replace /> : <Login />} />
          <Route path="/jobs/*" element={<JobRedirect />} />

          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/resumes" element={<ProtectedRoute><Resumes /></ProtectedRoute>} />
          <Route path="/my-assignments" element={<ProtectedRoute><Resumes /></ProtectedRoute>} />
          <Route path="/pipeline" element={<ProtectedRoute><Pipeline /></ProtectedRoute>} />
          <Route path="/interviews" element={<ProtectedRoute><Interviews /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute adminOnly><Analytics /></ProtectedRoute>} />
          <Route path="/jobs" element={<ProtectedRoute><Jobs /></ProtectedRoute>} />
          <Route path="/clients" element={<ProtectedRoute><Clients /></ProtectedRoute>} />
          <Route path="/communications" element={<ProtectedRoute><Communications /></ProtectedRoute>} />
          <Route path="/email-templates" element={<ProtectedRoute userOnly><EmailTemplates /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute><AdminUsers /></ProtectedRoute>} />
          <Route path="/wallet" element={<ProtectedRoute><Wallet /></ProtectedRoute>} />

          <Route path="/super-admin" element={<ProtectedRoute superAdminOnly><SuperAdminDashboard /></ProtectedRoute>} />
          <Route path="/super-admin/agencies" element={<ProtectedRoute superAdminOnly><Agencies /></ProtectedRoute>} />
          <Route path="/super-admin/jobs" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Jobs} /></ProtectedRoute>} />
          <Route path="/super-admin/candidates" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Pipeline} /></ProtectedRoute>} />
          <Route path="/super-admin/interviews" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Interviews} /></ProtectedRoute>} />
          <Route path="/super-admin/clients" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Clients} /></ProtectedRoute>} />
          <Route path="/super-admin/users" element={<ProtectedRoute superAdminOnly><AdminUsers /></ProtectedRoute>} />
          <Route path="/super-admin/pricing" element={<ProtectedRoute superAdminOnly><Pricing /></ProtectedRoute>} />
          <Route path="/super-admin/settings" element={<ProtectedRoute superAdminOnly><Settings /></ProtectedRoute>} />

          <Route
            path="*"
            element={<Navigate to={isAuthenticated ? getDefaultRouteForUser(user) : '/login'} replace />}
          />
        </Routes>
      </Suspense>
      <Toaster />
    </ErrorBoundary>
  )
}

export default App
