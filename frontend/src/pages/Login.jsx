import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Bot, Loader2, User, Shield } from 'lucide-react'

export default function Login() {
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const data = await api.getPublicUsers()
      setUsers(data)
    } catch (error) {
      console.error('Failed to fetch users:', error)
    }
  }

  const handleUserSelect = (user) => {
    setSelectedUser(user)
    setPassword('')
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(selectedUser.email, password)
      navigate('/')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const getRoleIcon = (role) => {
    if (role === 'admin') return <Shield className="h-8 w-8" />
    return <User className="h-8 w-8" />
  }

  const getRoleColor = (role) => {
    if (role === 'admin') return 'bg-red-500'
    return 'bg-blue-500'
  }

  if (!selectedUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <div className="w-full max-w-4xl">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-primary">
                <Bot className="h-10 w-10 text-primary-foreground" />
              </div>
            </div>
            <h1 className="text-4xl font-bold mb-2">Welcome to PONTIS</h1>
            <p className="text-muted-foreground">Select a user to login</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {users.map((user) => (
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
                      <span className="inline-block mt-2 px-3 py-1 text-xs font-medium rounded-full bg-secondary capitalize">
                        {user.role.replace('_', ' ')}
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <Button
            variant="ghost"
            size="sm"
            className="absolute top-4 left-4"
            onClick={() => setSelectedUser(null)}
          >
            ← Back
          </Button>
          <div className="flex justify-center mb-4">
            <div className={`p-4 rounded-full ${getRoleColor(selectedUser.role)} text-white`}>
              {getRoleIcon(selectedUser.role)}
            </div>
          </div>
          <CardTitle className="text-2xl">{selectedUser.full_name}</CardTitle>
          <CardDescription>
            {selectedUser.email}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">
                {error}
              </div>
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
  )
}
