import { useEffect, useState } from 'react'
import { Building2 } from 'lucide-react'
import { api } from '@/lib/api'

/**
 * Wraps any existing page with a Super Admin agency filter bar.
 * The selected agency_id is passed as a prop to the wrapped page.
 */
export default function SuperAdminDataPage({ PageComponent }) {
  const [agencies, setAgencies] = useState([])
  const [selectedAgency, setSelectedAgency] = useState('')

  useEffect(() => {
    api.getAgencies().then(setAgencies).catch(console.error)
  }, [])

  const selectedAgencyName = agencies.find((agency) => String(agency.id) === String(selectedAgency))?.name

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b bg-muted/30 px-6 py-3">
        <Building2 className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium text-muted-foreground">Viewing as:</span>
        <select
          className="rounded-lg border bg-background px-3 py-1.5 text-sm"
          value={selectedAgency}
          onChange={(event) => setSelectedAgency(event.target.value)}
        >
          <option value="">All Agencies</option>
          {agencies.map((agency) => (
            <option key={agency.id} value={agency.id}>
              {agency.name}
            </option>
          ))}
        </select>
        {selectedAgency && selectedAgencyName && (
          <span className="text-xs text-muted-foreground">- {selectedAgencyName}</span>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        <PageComponent superAdminAgencyId={selectedAgency || null} />
      </div>
    </div>
  )
}
