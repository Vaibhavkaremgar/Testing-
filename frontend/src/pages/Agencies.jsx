import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Plus, Pencil, Trash2, X, Check } from 'lucide-react'

const emptyForm = {
  name: '', slug: '', is_active: true,
  admin_full_name: '', admin_email: '', admin_password: ''
}

const emptyEditForm = { name: '', slug: '', is_active: true }

export default function Agencies() {
  const [agencies, setAgencies] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { fetchAgencies() }, [])

  const fetchAgencies = async () => {
    setLoading(true)
    try {
      const data = await api.getAgencies()
      setAgencies(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setError('')
    setShowForm(true)
  }

  const openEdit = (agency) => {
    setEditingId(agency.id)
    setForm({ name: agency.name, slug: agency.slug, is_active: agency.is_active })
    setError('')
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.name.trim() || !form.slug.trim()) {
      setError('Agency name and slug are required')
      return
    }
    if (!editingId) {
      if (!form.admin_full_name.trim() || !form.admin_email.trim() || !form.admin_password.trim()) {
        setError('Admin name, email and password are required')
        return
      }
    }
    setSaving(true)
    setError('')
    try {
      if (editingId) {
        await api.updateAgency(editingId, { name: form.name, slug: form.slug, is_active: form.is_active })
      } else {
        await api.createAgency(form)
      }
      setShowForm(false)
      fetchAgencies()
    } catch (err) {
      setError(err.message || 'Failed to save agency')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this agency? This cannot be undone.')) return
    try {
      await api.deleteAgency(id)
      fetchAgencies()
    } catch (err) {
      alert(err.message || 'Failed to delete agency')
    }
  }

  const autoSlug = (name) => name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agencies</h1>
          <p className="text-muted-foreground text-sm mt-1">Manage all agencies on the platform</p>
        </div>
        <Button onClick={openCreate} className="gap-2">
          <Plus className="h-4 w-4" /> New Agency
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{editingId ? 'Edit Agency' : 'Create Agency'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {error && <p className="text-sm text-destructive">{error}</p>}

            {/* Agency Details */}
            <div>
              <p className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Agency Details</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Agency Name</label>
                  <Input
                    placeholder="e.g. Acme Recruitment"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value, slug: autoSlug(e.target.value) })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Slug</label>
                  <Input
                    placeholder="e.g. acme-recruitment"
                    value={form.slug}
                    onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2 mt-3">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="h-4 w-4"
                />
                <label htmlFor="is_active" className="text-sm">Active</label>
              </div>
            </div>

            {/* Admin User Details — only on create */}
            {!editingId && (
              <div>
                <p className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Admin User</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Full Name</label>
                    <Input
                      placeholder="e.g. John Smith"
                      value={form.admin_full_name}
                      onChange={(e) => setForm({ ...form, admin_full_name: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Email</label>
                    <Input
                      type="email"
                      placeholder="e.g. admin@acme.com"
                      value={form.admin_email}
                      onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Password</label>
                    <Input
                      type="password"
                      placeholder="••••••••"
                      value={form.admin_password}
                      onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={saving} className="gap-2">
                <Check className="h-4 w-4" /> {saving ? 'Saving...' : 'Save'}
              </Button>
              <Button variant="outline" onClick={() => setShowForm(false)} className="gap-2">
                <X className="h-4 w-4" /> Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Agencies Table */}
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <p className="text-center text-muted-foreground py-8">Loading...</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2 font-medium">Name</th>
                  <th className="text-left py-2 font-medium">Slug</th>
                  <th className="text-left py-2 font-medium">Status</th>
                  <th className="text-right py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {agencies.map((agency) => (
                  <tr key={agency.id} className="border-b last:border-0 hover:bg-muted/50">
                    <td className="py-3 font-medium">{agency.name}</td>
                    <td className="py-3 text-muted-foreground">{agency.slug}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${agency.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {agency.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => openEdit(agency)} className="gap-1">
                          <Pencil className="h-3 w-3" /> Edit
                        </Button>
                        <Button size="sm" variant="destructive" onClick={() => handleDelete(agency.id)} className="gap-1">
                          <Trash2 className="h-3 w-3" /> Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {agencies.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-muted-foreground">No agencies yet. Create one to get started.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
