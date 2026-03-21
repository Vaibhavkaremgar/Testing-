import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, User, Shield, ShieldCheck, ArrowLeft, Users } from 'lucide-react'

// STEP 1: tenant selection (super_admin + admins)
// STEP 2a: super_admin → password directly
// STEP 2b: agency admin → choose "Login as Admin" or pick a team member
// STEP 3: team member selected → password entry

const STEPS = { TENANT: 'tenant', ADMIN_CHOICE: 'admin_choice', PASSWORD: 'password' }

const getRoleIcon = (role) => {
  if (role === 'super_admin') return <ShieldCheck className="h-7 w-7" />
  if (role === 'admin') return <Shield className="h-7 w-7" />
  return <User className="h-7 w-7" />
}

const getRoleColor = (role) => {
  if (role === 'super_admin') return 'bg-purple-600'
  if (role === 'admin') return 'bg-red-500'
  if (role === 'hiring_manager') return 'bg-green-500'
  if (role === 'recruiter') return 'bg-blue-500'
  return 'bg-gray-500'
}

const getRoleLabel = (role) => role.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

export default function Login() {
  const [step, setStep] = useState(STEPS.TENANT)
  const [tenants, setTenants] = useState([])
  const [agencyUsers, setAgencyUsers] = useState([])
  const [selectedAdmin, setSelectedAdmin] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetchingUsers, setFetchingUsers] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    api.getPublicUsers().then(setTenants).catch(console.error)
  }, [])

  const handleTenantSelect = async (tenant) => {
    setSelectedAdmin(tenant)
    setError('')
    if (tenant.role === 'super_admin') {
      setSelectedUser(tenant)
      setStep(STEPS.PASSWORD)
    } else {
      // agency admin — fetch their team
      setFetchingUsers(true)
      try {
        const users = await api.getUsersByAgency(tenant.agency_id)
        setAgencyUsers(users)
      } catch {
        setAgencyUsers([])
      } finally {
        setFetchingUsers(false)
      }
      setStep(STEPS.ADMIN_CHOICE)
    }
  }

  const handleLoginAsAdmin = () => {
    setSelectedUser(selectedAdmin)
    setPassword('')
    setError('')
    setStep(STEPS.PASSWORD)
  }

  const handleTeamMemberSelect = (user) => {
    setSelectedUser(user)
    setPassword('')
    setError('')
    setStep(STEPS.PASSWORD)
  }

  const handleBack = () => {
    setError('')
    setPassword('')
    if (step === STEPS.PASSWORD && selectedAdmin?.role !== 'super_admin') {
      setStep(STEPS.ADMIN_CHOICE)
    } else {
      setStep(STEPS.TENANT)
      setSelectedAdmin(null)
      setSelectedUser(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const userData = await login(selectedUser.email, password)
      navigate(userData.role === 'super_admin' ? '/super-admin' : '/')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  // ── Step 1: Tenant Selection ──────────────────────────────────────────────
  if (step === STEPS.TENANT) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <div className="w-full max-w-3xl">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-2">Welcome to PONTIS</h1>
            <p className="text-muted-foreground">Select your organization to continue</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tenants.map((tenant) => (
              <Card
                key={tenant.id}
                className="cursor-pointer hover:shadow-lg transition-all hover:scale-105"
                onClick={() => handleTenantSelect(tenant)}
              >
                <CardContent className="pt-6">
                  <div className="flex flex-col items-center text-center space-y-3">
                    <div className={`p-4 rounded-full ${getRoleColor(tenant.role)} text-white`}>
                      {getRoleIcon(tenant.role)}
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">{tenant.full_name}</h3>
                      <p className="text-sm text-muted-foreground">{tenant.email}</p>
                      <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary">
                        {getRoleLabel(tenant.role)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ── Step 2b: Agency Admin Choice ─────────────────────────────────────────
  if (step === STEPS.ADMIN_CHOICE) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <div className="w-full max-w-3xl">
          <button onClick={handleBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          <div className="text-center mb-8">
            <div className={`inline-flex p-4 rounded-full ${getRoleColor(selectedAdmin.role)} text-white mb-3`}>
              <Shield className="h-7 w-7" />
            </div>
            <h2 className="text-2xl font-bold">{selectedAdmin.full_name}</h2>
            <p className="text-muted-foreground text-sm mt-1">How would you like to continue?</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {/* Login as Admin */}
            <Card className="cursor-pointer hover:shadow-lg transition-all hover:scale-105 border-2 hover:border-red-400" onClick={handleLoginAsAdmin}>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center space-y-3">
                  <div className="p-4 rounded-full bg-red-500 text-white">
                    <Shield className="h-7 w-7" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">Login as Admin</h3>
                    <p className="text-sm text-muted-foreground mt-1">Access the admin dashboard</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Team member count card (decorative) */}
            <Card className="border-2 border-dashed border-gray-200 bg-gray-50 dark:bg-gray-800">
              <CardContent className="pt-6">
                <div className="flex flex-col items-center text-center space-y-3">
                  <div className="p-4 rounded-full bg-blue-100 text-blue-600">
                    <Users className="h-7 w-7" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">Team Members</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {fetchingUsers ? 'Loading...' : `${agencyUsers.length} member${agencyUsers.length !== 1 ? 's' : ''} in your agency`}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Team members */}
          {!fetchingUsers && agencyUsers.length > 0 && (
            <>
              <p className="text-sm font-medium text-muted-foreground mb-3">Or select a team member:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agencyUsers.map((user) => (
                  <Card
                    key={user.id}
                    className="cursor-pointer hover:shadow-lg transition-all hover:scale-105"
                    onClick={() => handleTeamMemberSelect(user)}
                  >
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center text-center space-y-3">
                        <div className={`p-3 rounded-full ${getRoleColor(user.role)} text-white`}>
                          {getRoleIcon(user.role)}
                        </div>
                        <div>
                          <h3 className="font-semibold">{user.full_name}</h3>
                          <p className="text-xs text-muted-foreground">{user.email}</p>
                          <span className="inline-block mt-2 px-2 py-1 text-xs font-medium rounded-full bg-secondary">
                            {getRoleLabel(user.role)}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}

          {!fetchingUsers && agencyUsers.length === 0 && (
            <p className="text-center text-sm text-muted-foreground">No team members found for this agency.</p>
          )}
        </div>
      </div>
    )
  }

  // ── Step 3: Password Entry ────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <div className="w-full max-w-md">
        <button onClick={handleBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <Card>
          <CardContent className="pt-8 pb-6 px-6">
            <div className="flex flex-col items-center text-center mb-6">
              <div className={`p-4 rounded-full ${getRoleColor(selectedUser.role)} text-white mb-3`}>
                {getRoleIcon(selectedUser.role)}
              </div>
              <h2 className="text-xl font-bold">{selectedUser.full_name}</h2>
              <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
              <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary">
                {getRoleLabel(selectedUser.role)}
              </span>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
              )}
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Sign In
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
