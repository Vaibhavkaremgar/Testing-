import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Building2 } from 'lucide-react'

/**
 * Wraps any existing page with a Super Admin agency filter bar.
 * The selected agency_id is passed as a prop to the wrapped page.
 */
export default function SuperAdminDataPage({ PageComponent, title }) {
  const [agencies, setAgencies] = useState([])
  const [selectedAgency, setSelectedAgency] = useState('')

  useEffect(() => {
    api.getAgencies().then(setAgencies).catch(console.error)
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Agency filter bar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b bg-muted/30">
        <Building2 className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium text-muted-foreground">Viewing as:</span>
        <select
          className="border rounded-lg px-3 py-1.5 text-sm bg-background"
          value={selectedAgency}
          onChange={(e) => setSelectedAgency(e.target.value)}
        >
          <option value="">All Agencies</option>
          {agencies.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        {selectedAgency && (
          <span className="text-xs text-muted-foreground">
            — {agencies.find(a => String(a.id) === String(selectedAgency))?.name}
          </span>
        )}
      </div>

      {/* Render the actual page, passing agency_id filter */}
      <div className="flex-1 overflow-auto">
        <PageComponent superAdminAgencyId={selectedAgency || null} />
      </div>
    </div>
  )
}
