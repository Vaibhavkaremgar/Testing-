import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, User, Shield, ShieldCheck, ArrowLeft, Building2 } from 'lucide-react'

const STEPS = { SELECT: 'select', AGENCY_USERS: 'agency_users', PASSWORD: 'password' }

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
  const [step, setStep] = useState(STEPS.SELECT)
  const [superAdmin, setSuperAdmin] = useState(null)
  const [agencies, setAgencies] = useState([])
  const [selectedAgency, setSelectedAgency] = useState(null)
  const [agencyUsers, setAgencyUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetchingUsers, setFetchingUsers] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    api.getLoginScreen().then(data => {
      setSuperAdmin(data.super_admin)
      setAgencies(data.agencies)
    }).catch(console.error)
  }, [])

  const handleSuperAdminSelect = () => {
    setSelectedUser(superAdmin)
    setPassword('')
    setError('')
    setStep(STEPS.PASSWORD)
  }

  const handleAgencySelect = async (agency) => {
    setSelectedAgency(agency)
    setError('')
    setFetchingUsers(true)
    try {
      const users = await api.getUsersByAgency(agency.id)
      setAgencyUsers(users)
    } catch {
      setAgencyUsers([])
    } finally {
      setFetchingUsers(false)
    }
    setStep(STEPS.AGENCY_USERS)
  }

  const handleUserSelect = (user) => {
    setSelectedUser(user)
    setPassword('')
    setError('')
    setStep(STEPS.PASSWORD)
  }

  const handleBack = () => {
    setError('')
    setPassword('')
    if (step === STEPS.PASSWORD && selectedUser?.role !== 'super_admin') {
      setStep(STEPS.AGENCY_USERS)
    } else {
      setStep(STEPS.SELECT)
      setSelectedAgency(null)
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

  // ── Step 1: Select super admin or agency ─────────────────────────────────
  if (step === STEPS.SELECT) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <div className="w-full max-w-3xl">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-2">Welcome to PONTIS</h1>
            <p className="text-muted-foreground">Select your organization to continue</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Super Admin card */}
            {superAdmin && (
              <Card
                className="cursor-pointer hover:shadow-lg transition-all hover:scale-105 border-2 hover:border-purple-400"
                onClick={handleSuperAdminSelect}
              >
                <CardContent className="pt-6">
                  <div className="flex flex-col items-center text-center space-y-3">
                    <div className="p-4 rounded-full bg-purple-600 text-white">
                      <ShieldCheck className="h-7 w-7" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">{superAdmin.full_name}</h3>
                      <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary">
                        Super Admin
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Agency cards */}
            {agencies.map((agency) => (
              <Card
                key={agency.id}
                className="cursor-pointer hover:shadow-lg transition-all hover:scale-105 border-2 hover:border-blue-400"
                onClick={() => handleAgencySelect(agency)}
              >
                <CardContent className="pt-6">
                  <div className="flex flex-col items-center text-center space-y-3">
                    <div className="p-4 rounded-full bg-blue-500 text-white">
                      <Building2 className="h-7 w-7" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">{agency.name}</h3>
                      <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary">
                        Agency
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

  // ── Step 2: Agency users (admin + team members) ───────────────────────────
  if (step === STEPS.AGENCY_USERS) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <div className="w-full max-w-3xl">
          <button onClick={handleBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          <div className="text-center mb-8">
            <div className="inline-flex p-4 rounded-full bg-blue-500 text-white mb-3">
              <Building2 className="h-7 w-7" />
            </div>
            <h2 className="text-2xl font-bold">{selectedAgency.name}</h2>
            <p className="text-muted-foreground text-sm mt-1">Select who you want to login as</p>
          </div>

          {fetchingUsers ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : agencyUsers.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">No users found for this agency.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agencyUsers.map((user) => (
                <Card
                  key={user.id}
                  className="cursor-pointer hover:shadow-lg transition-all hover:scale-105"
                  onClick={() => handleUserSelect(user)}
                >
                  <CardContent className="pt-6">
                    <div className="flex flex-col items-center text-center space-y-3">
                      <div className={`p-4 rounded-full ${getRoleColor(user.role)} text-white`}>
                        {getRoleIcon(user.role)}
                      </div>
                      <div>
                        <h3 className="font-semibold text-lg">{user.full_name}</h3>
                        <p className="text-sm text-muted-foreground">{user.email}</p>
                        <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary">
                          {getRoleLabel(user.role)}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Step 3: Password entry ────────────────────────────────────────────────
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
