import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { User, Shield, Users as UsersIcon } from 'lucide-react'

export default function UserSelect() {
  const [users, setUsers] = useState([])
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
    navigate('/login', { state: { selectedUser: user } })
  }

  const getRoleIcon = (role) => {
    if (role === 'admin') return <Shield className="h-8 w-8" />
    return <User className="h-8 w-8" />
  }

  const getRoleColor = (role) => {
    if (role === 'admin') return 'bg-red-500'
    return 'bg-blue-500'
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <div className="w-full max-w-4xl">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2">Select User</h1>
          <p className="text-muted-foreground">Choose a user to login</p>
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
