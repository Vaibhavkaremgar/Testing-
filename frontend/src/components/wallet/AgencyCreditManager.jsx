import { useEffect, useState } from 'react'
import api from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function AgencyCreditManager({
  title = 'Add Credits to Agency',
  description = 'Select an agency and add credits to its admin wallet.',
  preselectedAgencyId = '',
  compact = false,
  onCreditsAdded,
  showHistoryTable = false,
}) {
  const [agencies, setAgencies] = useState([])
  const [selectedAgency, setSelectedAgency] = useState(preselectedAgencyId || '')
  const [creditAmount, setCreditAmount] = useState('')
  const [note, setNote] = useState('Credits added by super admin')
  const [agencyWallet, setAgencyWallet] = useState(null)
  const [creditHistory, setCreditHistory] = useState([])
  const [loadingAgencies, setLoadingAgencies] = useState(true)
  const [loadingWallet, setLoadingWallet] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    fetchAgencies()
  }, [])

  useEffect(() => {
    setSelectedAgency(preselectedAgencyId || '')
  }, [preselectedAgencyId])

  useEffect(() => {
    if (!selectedAgency) {
      setAgencyWallet(null)
      return
    }
    if (!showHistoryTable) {
      fetchAgencyWallet(selectedAgency)
    }
  }, [selectedAgency, showHistoryTable])

  useEffect(() => {
    if (showHistoryTable) {
      fetchCreditHistory()
    }
  }, [showHistoryTable])

  async function fetchAgencies() {
    setLoadingAgencies(true)
    try {
      const response = await api.getAgencies()
      setAgencies(Array.isArray(response) ? response : [])
    } catch (err) {
      setError('Failed to load agencies')
    } finally {
      setLoadingAgencies(false)
    }
  }

  async function fetchAgencyWallet(agencyId) {
    setLoadingWallet(true)
    try {
      const response = await api.get(`/wallet/agency-admin/${agencyId}`)
      setAgencyWallet(response)
      setError('')
    } catch (err) {
      setAgencyWallet(null)
      setError(err.message || 'Failed to load agency wallet')
    } finally {
      setLoadingWallet(false)
    }
  }

  async function fetchCreditHistory() {
    setLoadingHistory(true)
    try {
      const response = await api.get('/wallet/agency-admin-credit-history')
      setCreditHistory(Array.isArray(response) ? response : [])
      setError('')
    } catch (err) {
      setCreditHistory([])
      setError(err.message || 'Failed to load credit history')
    } finally {
      setLoadingHistory(false)
    }
  }

  function flash(type, message) {
    if (type === 'success') {
      setSuccess(message)
      setError('')
    } else {
      setError(message)
      setSuccess('')
    }
    window.clearTimeout(window.__agencyCreditFlashTimeout)
    window.__agencyCreditFlashTimeout = window.setTimeout(() => {
      setSuccess('')
      setError('')
    }, 3000)
  }

  async function handleSubmit(e) {
    e.preventDefault()

    if (!selectedAgency) {
      flash('error', 'Please select an agency')
      return
    }

    if (!creditAmount || Number(creditAmount) <= 0) {
      flash('error', 'Please enter a valid credit amount')
      return
    }

    setSaving(true)
    try {
      const response = await api.post('/wallet/add-credits', {
        agency_id: selectedAgency,
        amount: Number(creditAmount),
        description: note?.trim() || 'Credits added by super admin',
      })

      flash('success', `Added ${creditAmount} credits to ${response.agency_name || 'the agency'} admin wallet`)
      setCreditAmount('')
      setNote('Credits added by super admin')
      if (showHistoryTable) {
        await fetchCreditHistory()
      } else {
        await fetchAgencyWallet(selectedAgency)
      }
      onCreditsAdded?.(response)
    } catch (err) {
      flash('error', err.message || 'Failed to add credits')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Agency</Label>
            <select
              className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={selectedAgency}
              onChange={(e) => setSelectedAgency(e.target.value)}
              disabled={loadingAgencies}
            >
              <option value="">Select an agency</option>
              {agencies.map((agency) => (
                <option key={agency.id} value={agency.id}>
                  {agency.name}
                </option>
              ))}
            </select>
          </div>

          <div className={compact ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 md:grid-cols-2 gap-4'}>
            <div>
              <Label>Credits to Add</Label>
              <Input
                type="number"
                min="1"
                step="1"
                className="mt-2"
                placeholder="Enter credits"
                value={creditAmount}
                onChange={(e) => setCreditAmount(e.target.value)}
              />
            </div>

            <div>
              <Label>Description</Label>
              <Input
                type="text"
                className="mt-2"
                placeholder="Credits added by super admin"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" disabled={saving || loadingAgencies} className="w-full">
            {saving ? 'Adding Credits...' : 'Add Credits'}
          </Button>
        </form>

        {showHistoryTable ? (
          <div className="overflow-hidden rounded-xl border">
            <div className="border-b bg-muted/30 px-4 py-3">
              <h3 className="text-sm font-semibold">Credit History</h3>
              <p className="text-xs text-muted-foreground">All agency admin credit transactions</p>
            </div>

            {loadingHistory ? (
              <div className="px-4 py-6 text-sm text-muted-foreground">Loading credit history...</div>
            ) : creditHistory.length === 0 ? (
              <div className="px-4 py-6 text-sm text-muted-foreground">No credit transactions found yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/20">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Date</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Agency Name</th>
                      <th className="px-4 py-3 text-left font-medium text-muted-foreground">Credits Added</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {creditHistory.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/20">
                        <td className="px-4 py-3">{new Date(item.created_at).toLocaleDateString()}</td>
                        <td className="px-4 py-3 font-medium">{item.agency_name}</td>
                        <td className="px-4 py-3">{item.amount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : selectedAgency && (
          <div className="rounded-xl border bg-muted/20 p-4">
            {loadingWallet ? (
              <div className="text-sm text-muted-foreground">Loading agency wallet...</div>
            ) : agencyWallet?.admin ? (
              <div className={compact ? 'space-y-3' : 'grid grid-cols-1 md:grid-cols-2 gap-4'}>
                <div>
                  <p className="text-sm font-medium">{agencyWallet.agency?.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Admin: {agencyWallet.admin.full_name} ({agencyWallet.admin.email})
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium">{agencyWallet.admin.wallet_balance} credits</p>
                  <p className="text-xs text-muted-foreground">Current admin wallet balance</p>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No agency admin wallet found for this agency.</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
