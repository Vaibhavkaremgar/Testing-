import { useState, useEffect } from 'react'
import api from '@/lib/api'
import AgencyCreditManager from '@/components/wallet/AgencyCreditManager'

const CURRENCY_SYMBOLS = { USD: '$', INR: '₹' }

export default function Pricing() {
  const [agencies, setAgencies] = useState([])
  const [discounts, setDiscounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [form, setForm] = useState({
    agency_id: '',
    discount_type: 'percentage',
    discount_value: '',
    currency: 'USD',
  })

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    try {
      const [agencyRes, discountRes] = await Promise.all([
        api.get('/pricing/agencies'),
        api.get('/pricing/discounts'),
      ])
      setAgencies(Array.isArray(agencyRes) ? agencyRes : [])
      setDiscounts(Array.isArray(discountRes) ? discountRes : [])
    } catch (e) {
      setError('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  function flash(type, msg) {
    if (type === 'success') { setSuccess(msg); setError('') }
    else { setError(msg); setSuccess('') }
    setTimeout(() => { setSuccess(''); setError('') }, 3000)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.agency_id) return flash('error', 'Please select an agency')
    if (!form.discount_value || Number(form.discount_value) <= 0) return flash('error', 'Enter a valid discount value')
    setSaving(true)
    try {
      await api.post('/pricing/discounts', {
        ...form,
        discount_value: Number(form.discount_value),
      })
      flash('success', 'Discount saved successfully')
      setForm({ agency_id: '', discount_type: 'percentage', discount_value: '', currency: 'USD' })
      fetchData()
    } catch (e) {
      flash('error', e.response?.data?.detail || 'Failed to save discount')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(agencyId) {
    setDeleting(agencyId)
    try {
      await api.delete(`/pricing/discounts/${agencyId}`)
      flash('success', 'Discount removed')
      fetchData()
    } catch (e) {
      flash('error', 'Failed to remove discount')
    } finally {
      setDeleting(null)
    }
  }

  function handleEdit(discount) {
    setForm({
      agency_id: discount.agency_id,
      discount_type: discount.discount_type,
      discount_value: String(discount.discount_value),
      currency: discount.currency || 'USD',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function formatDiscount(d) {
    const sym = CURRENCY_SYMBOLS[d.currency] || d.currency
    return d.discount_type === 'percentage'
      ? `${d.discount_value}% off`
      : `${sym}${d.discount_value} off`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Pricing & Discounts</h1>
        <p className="text-muted-foreground text-sm mt-1">Assign discounts to agencies for credit purchases</p>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>}
      {success && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm">{success}</div>}

      <AgencyCreditManager
        title="Add Credits"
        description="Superadmin can add credits directly to an agency admin wallet."
        showHistoryTable
      />

      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <h2 className="text-base font-semibold mb-4">
          {form.agency_id && discounts.find(d => d.agency_id === form.agency_id) ? 'Update Discount' : 'Assign Discount'}
        </h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium mb-1">Agency</label>
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background"
              value={form.agency_id}
              onChange={e => setForm(f => ({ ...f, agency_id: e.target.value }))}
            >
              <option value="">Select agency...</option>
              {agencies.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Discount Type</label>
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background"
              value={form.discount_type}
              onChange={e => setForm(f => ({ ...f, discount_type: e.target.value }))}
            >
              <option value="percentage">Percentage (%)</option>
              <option value="amount">Fixed Amount</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {form.discount_type === 'percentage' ? 'Discount (%)' : 'Discount Amount'}
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                min="0"
                max={form.discount_type === 'percentage' ? 100 : undefined}
                step="0.01"
                placeholder={form.discount_type === 'percentage' ? 'e.g. 10' : 'e.g. 50'}
                className="flex-1 border rounded-lg px-3 py-2 text-sm bg-background"
                value={form.discount_value}
                onChange={e => setForm(f => ({ ...f, discount_value: e.target.value }))}
              />
              {form.discount_type === 'amount' && (
                <select
                  className="border rounded-lg px-3 py-2 text-sm bg-background"
                  value={form.currency}
                  onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                >
                  <option value="USD">USD ($)</option>
                  <option value="INR">INR (₹)</option>
                </select>
              )}
            </div>
          </div>

          <div className="sm:col-span-2 flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="bg-primary text-primary-foreground px-6 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Discount'}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-card border rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="text-base font-semibold">Active Discounts</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{discounts.length} discount{discounts.length !== 1 ? 's' : ''} assigned</p>
        </div>

        {discounts.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground text-sm">
            No discounts assigned yet
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-muted-foreground">Agency</th>
                <th className="text-left px-6 py-3 font-medium text-muted-foreground">Discount</th>
                <th className="text-left px-6 py-3 font-medium text-muted-foreground">Type</th>
                <th className="text-left px-6 py-3 font-medium text-muted-foreground">Last Updated</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {discounts.map(d => (
                <tr key={d.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-4 font-medium">{d.agency_name}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 px-2.5 py-0.5 rounded-full text-xs font-medium">
                      {formatDiscount(d)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted-foreground capitalize">{d.discount_type}</td>
                  <td className="px-6 py-4 text-muted-foreground">
                    {d.updated_at
                      ? new Date(d.updated_at).toLocaleDateString()
                      : new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => handleEdit(d)}
                        className="text-xs text-primary hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(d.agency_id)}
                        disabled={deleting === d.agency_id}
                        className="text-xs text-red-500 hover:underline disabled:opacity-50"
                      >
                        {deleting === d.agency_id ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
