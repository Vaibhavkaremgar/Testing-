import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn, getScoreColor } from '@/lib/utils'
import { Briefcase, Star } from 'lucide-react'

const STAGES = [
  { id: 'SHORTLISTED', label: 'Shortlisted', color: 'bg-green-500' },
  { id: 'RESUME_REJECTED', label: 'Resume Rejected', color: 'bg-red-400' },
  { id: 'INTERVIEW_SCHEDULED', label: 'Interview Scheduled', color: 'bg-blue-500' },
  { id: 'INTERVIEW_RESCHEDULED', label: 'Interview Rescheduled', color: 'bg-yellow-500' },
  { id: 'INTERVIEWED', label: 'Interview', color: 'bg-purple-500' },
  { id: 'NO_SHOW', label: 'No Show', color: 'bg-orange-500' },
  { id: 'SELECTED', label: 'Selected', color: 'bg-emerald-500' },
  { id: 'REJECTED', label: 'Rejected', color: 'bg-red-600' },
]

function CandidateCard({ candidate, onCardClick }) {
  return (
    <Card className="transition-shadow" onClick={() => onCardClick && onCardClick(candidate)}>
      <CardContent className="p-3">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">{candidate.name}</p>
            {candidate.current_role && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                <Briefcase className="h-3 w-3" />
                <span className="truncate">{candidate.current_role}</span>
              </div>
            )}
            {candidate.current_company && (
              <p className="text-xs text-muted-foreground truncate">{candidate.current_company}</p>
            )}
            <div className="flex items-center justify-between mt-2">
              {candidate.job_title && (
                <Badge variant="outline" className="text-xs truncate max-w-[100px]">
                  {candidate.job_title}
                </Badge>
              )}
              {candidate.resume_score && (
                <div className="flex items-center gap-1">
                  <Star className="h-3 w-3 text-yellow-500" />
                  <span className={cn('text-xs font-semibold', getScoreColor(candidate.resume_score))}>
                    {candidate.resume_score}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function StageColumn({ stage, candidates, onCardClick }) {
  return (
    <div className="flex flex-col w-72 flex-shrink-0">
      <div className="flex items-center gap-2 mb-3">
        <div className={cn('w-3 h-3 rounded-full', stage.color)} />
        <h3 className="font-semibold text-sm">{stage.label}</h3>
        <Badge variant="secondary" className="ml-auto">
          {candidates.length}
        </Badge>
      </div>
      <div className="flex-1 bg-muted/50 rounded-xl p-2 min-h-[500px]">
        <div className="space-y-2">
          {candidates.map((candidate) => (
            <CandidateCard key={candidate.id} candidate={candidate} onCardClick={onCardClick} />
          ))}
        </div>
        {candidates.length === 0 && (
          <div className="flex items-center justify-center h-24 text-muted-foreground text-sm">
            No candidates
          </div>
        )}
      </div>
    </div>
  )
}

export default function Pipeline() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [stages, setStages] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPipeline = async () => {
      try {
        const params = {}
        if (selectedClient) params.client = selectedClient
        const data = await api.getPipelineStages(params)
        setStages(data)
      } catch (error) {
        console.error('Failed to fetch pipeline:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchPipeline()
  }, [selectedClient])

  const handleCardClick = async (candidate) => {
    // No special click handling needed
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Candidate Pipeline</h1>
        <p className="text-muted-foreground">View candidates by stage</p>
      </div>

      <div className="flex-1 overflow-x-auto pb-4">
        <div className="flex gap-4 h-full min-w-max">
          {STAGES.map((stage) => (
            <StageColumn
              key={stage.id}
              stage={stage}
              candidates={stages[stage.id] || []}
              onCardClick={handleCardClick}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
