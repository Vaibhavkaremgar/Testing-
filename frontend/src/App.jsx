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
import Jobs from '@/pages/Jobs'
import Clients from '@/pages/Clients'
import Communications from '@/pages/Communications'
import EmailTemplates from '@/pages/EmailTemplates'
import Settings from '@/pages/Settings'
import Profile from '@/pages/Profile'
import AdminUsers from '@/pages/AdminUsers'
import Wallet from '@/pages/Wallet'
import SuperAdminDashboard from '@/pages/SuperAdminDashboard'
import Agencies from '@/pages/Agencies'
import Pricing from '@/pages/Pricing'
import SuperAdminDataPage from '@/pages/SuperAdminDataPage'

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
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to={getDefaultRouteForUser(user)} replace /> : <Login />} />

        {/* Regular routes */}
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

        {/* Super Admin routes */}
        <Route path="/super-admin" element={<ProtectedRoute superAdminOnly><SuperAdminDashboard /></ProtectedRoute>} />
        <Route path="/super-admin/agencies" element={<ProtectedRoute superAdminOnly><Agencies /></ProtectedRoute>} />
        <Route path="/super-admin/jobs" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Jobs} /></ProtectedRoute>} />
        <Route path="/super-admin/candidates" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Pipeline} /></ProtectedRoute>} />
        <Route path="/super-admin/interviews" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Interviews} /></ProtectedRoute>} />
        <Route path="/super-admin/clients" element={<ProtectedRoute superAdminOnly><SuperAdminDataPage PageComponent={Clients} /></ProtectedRoute>} />
        <Route path="/super-admin/users" element={<ProtectedRoute superAdminOnly><AdminUsers /></ProtectedRoute>} />
        <Route path="/super-admin/pricing" element={<ProtectedRoute superAdminOnly><Pricing /></ProtectedRoute>} />
        <Route path="/super-admin/settings" element={<ProtectedRoute superAdminOnly><Settings /></ProtectedRoute>} />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
      <Toaster />
    </ErrorBoundary>
  )
}

export default App
