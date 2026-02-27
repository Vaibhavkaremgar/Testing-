import { useState, useEffect } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Users, Edit, Trash2, Search, UserPlus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function AdminUsers() {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [filteredUsers, setFilteredUsers] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [editData, setEditData] = useState({
    full_name: '',
    email: '',
    role: '',
    is_active: true
  })

  useEffect(() => {
    if (user?.role !== 'admin') {
      alert('Access denied. Admin only.')
      return
    }
    fetchUsers()
  }, [user])

  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredUsers(users)
    } else {
      const query = searchQuery.toLowerCase()
      setFilteredUsers(
        users.filter(
          (u) =>
            u.full_name.toLowerCase().includes(query) ||
            u.email.toLowerCase().includes(query) ||
            u.role.toLowerCase().includes(query)
        )
      )
    }
  }, [searchQuery, users])

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const data = await api.getAllUsers()
      setUsers(data)
      setFilteredUsers(data)
    } catch (error) {
      alert(error.message || 'Failed to fetch users')
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = (user) => {
    setSelectedUser(user)
    setEditData({
      full_name: user.full_name,
      email: user.email,
      role: user.role,
      is_active: user.is_active
    })
    setEditDialogOpen(true)
  }

  const handleUpdate = async () => {
    if (!selectedUser) return

    try {
      await api.updateUser(selectedUser.id, editData)
      alert('User updated successfully!')
      setEditDialogOpen(false)
      fetchUsers()
    } catch (error) {
      alert(error.message || 'Failed to update user')
    }
  }

  const handleDelete = async (userId, userName) => {
    if (!confirm(`Are you sure you want to delete ${userName}?`)) return

    try {
      await api.deleteUser(userId)
      alert('User deleted successfully!')
      fetchUsers()
    } catch (error) {
      alert(error.message || 'Failed to delete user')
    }
  }

  const getRoleBadgeVariant = (role) => {
    switch (role) {
      case 'admin':
        return 'destructive'
      case 'recruiter':
        return 'default'
      case 'hiring_manager':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  if (user?.role !== 'admin') {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-muted-foreground">Access denied. Admin only.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-muted-foreground">Manage system users and permissions</p>
        </div>
        <Button>
          <UserPlus className="h-4 w-4 mr-2" />
          Add User
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{users.length}</div>
            <p className="text-xs text-muted-foreground">Total Users</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{users.filter(u => u.role === 'admin').length}</div>
            <p className="text-xs text-muted-foreground">Admins</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{users.filter(u => u.role === 'recruiter').length}</div>
            <p className="text-xs text-muted-foreground">Recruiters</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{users.filter(u => u.is_active).length}</div>
            <p className="text-xs text-muted-foreground">Active Users</p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users by name, email, or role..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            All Users ({filteredUsers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-center py-8 text-muted-foreground">Loading users...</p>
          ) : filteredUsers.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No users found</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 font-medium">Name</th>
                    <th className="text-left py-3 px-4 font-medium">Email</th>
                    <th className="text-left py-3 px-4 font-medium">Role</th>
                    <th className="text-left py-3 px-4 font-medium">Department</th>
                    <th className="text-left py-3 px-4 font-medium">Status</th>
                    <th className="text-left py-3 px-4 font-medium">Joined</th>
                    <th className="text-right py-3 px-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          {u.avatar_url ? (
                            <img
                              src={u.avatar_url}
                              alt={u.full_name}
                              className="w-8 h-8 rounded-full object-cover"
                            />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                              <span className="text-xs font-medium text-primary">
                                {u.full_name.charAt(0).toUpperCase()}
                              </span>
                            </div>
                          )}
                          <span className="font-medium">{u.full_name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">{u.email}</td>
                      <td className="py-3 px-4">
                        <Badge variant={getRoleBadgeVariant(u.role)} className="capitalize">
                          {u.role.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {u.department || '-'}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={u.is_active ? 'default' : 'secondary'}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(u)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          {u.id !== user.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(u.id, u.full_name)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>Update user information and permissions</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Full Name</Label>
              <Input
                value={editData.full_name}
                onChange={(e) => setEditData({ ...editData, full_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                value={editData.email}
                onChange={(e) => setEditData({ ...editData, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={editData.role} onValueChange={(value) => setEditData({ ...editData, role: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="recruiter">Recruiter</SelectItem>
                  <SelectItem value="hiring_manager">Hiring Manager</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={editData.is_active}
                onChange={(e) => setEditData({ ...editData, is_active: e.target.checked })}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="is_active">Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
