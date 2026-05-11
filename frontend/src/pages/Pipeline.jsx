import { useState, useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import ExpandableList from '@/components/ExpandableList'
import { api } from '@/lib/api'
import { cn, getScoreColor } from '@/lib/utils'
import { Briefcase, Star, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/use-toast'

const STAGES = [
  { id: 'REVIEW', label: 'In Review', color: 'bg-amber-500' },
  { id: 'SHORTLISTED', label: 'Shortlisted', color: 'bg-green-500' },
  { id: 'RESUME_REJECTED', label: 'Resume Rejected', color: 'bg-red-400' },
  { id: 'INTERVIEW_SCHEDULED', label: 'Interview Scheduled', color: 'bg-blue-500' },
  { id: 'INTERVIEW_RESCHEDULED', label: 'Interview Rescheduled', color: 'bg-yellow-500' },
  { id: 'INTERVIEWED', label: 'Interview', color: 'bg-purple-500' },
  //{ id: 'INTERVIEW_FAILED', label: 'Interview Failed', color: 'bg-rose-500' },
  { id: 'NO_SHOW', label: 'No Show', color: 'bg-orange-500' },
  { id: 'COMPLETED', label: 'Completed', color: 'bg-indigo-500' },
  { id: 'SELECTED', label: 'Selected', color: 'bg-emerald-500' },
  { id: 'REJECTED', label: 'Rejected', color: 'bg-red-600' },
]

function getEffectiveInterviewStatus(interview) {
  const normalizedStatus = String(interview?.status || '').toLowerCase()
  if (
    normalizedStatus === 'completed' ||
    interview?.has_recording ||
    interview?.transcript ||
    interview?.ai_summary ||
    interview?.interview_score !== null && interview?.interview_score !== undefined && interview?.interview_score !== ''
  ) {
    return 'completed'
  }

  return normalizedStatus || 'pending'
}

function buildPipelineStages(baseStages = {}, interviews = []) {
  const nextStages = Object.fromEntries(
    STAGES.map((stage) => [stage.id, []])
  )
  const candidateById = new Map()
  const stageSetByCandidate = new Map()
  const interviewDisplayStages = new Set(['INTERVIEW_SCHEDULED', 'INTERVIEW_RESCHEDULED', 'INTERVIEWED'])

  const latestInterviewsByCandidate = new Map()
  ;(interviews || []).forEach((interview) => {
    if (!interview?.candidate_id) return
    const candidateKey = String(interview.candidate_id)
    const previousInterview = latestInterviewsByCandidate.get(candidateKey)
    const previousDate = previousInterview?.scheduled_at || previousInterview?.created_at || ''
    const currentDate = interview?.scheduled_at || interview?.created_at || ''
    if (!previousInterview || new Date(currentDate) > new Date(previousDate)) {
      latestInterviewsByCandidate.set(candidateKey, interview)
    }
  })

  const countCandidateFields = (candidate) => ([
    candidate?.name,
    candidate?.company_name,
    candidate?.current_role,
    candidate?.current_company,
    candidate?.job_title,
    candidate?.resume_score,
  ].filter((value) => value !== null && value !== undefined && value !== '').length)

  const hasMeaningfulInterviewCardDetails = (candidate) => (
    candidate?.company_name
    || candidate?.current_role
    || candidate?.current_company
    || candidate?.job_title
    || candidate?.resume_score !== null && candidate?.resume_score !== undefined && candidate?.resume_score !== ''
  )

  Object.entries(baseStages || {}).forEach(([stageId, candidates]) => {
    ;(candidates || []).forEach((candidate) => {
      const candidateId = String(candidate.id)
      const previousCandidate = candidateById.get(candidateId)
      if (!previousCandidate || countCandidateFields(candidate) >= countCandidateFields(previousCandidate)) {
        candidateById.set(candidateId, candidate)
      }
      if (!stageSetByCandidate.has(candidateId)) {
        stageSetByCandidate.set(candidateId, new Set())
      }
      stageSetByCandidate.get(candidateId).add(stageId)
    })
  })

  candidateById.forEach((candidate, candidateId) => {
    const stageSet = stageSetByCandidate.get(candidateId) || new Set()
    const latestInterview = latestInterviewsByCandidate.get(candidateId)
    const effectiveInterviewStatus = getEffectiveInterviewStatus(latestInterview)
    let resolvedStage = [...stageSet][0] || candidate.stage || candidate.display_stage

    if (effectiveInterviewStatus === 'completed' && resolvedStage !== 'SELECTED' && resolvedStage !== 'REJECTED') {
      resolvedStage = 'COMPLETED'
    } else if (latestInterview) {
      const interviewStatus = String(latestInterview.status || '').toLowerCase()
      if (interviewStatus === 'scheduled') {
        resolvedStage = stageSet.has('INTERVIEWED') ? 'INTERVIEWED' : 'INTERVIEW_SCHEDULED'
      } else if (interviewStatus === 'rescheduled') {
        resolvedStage = 'INTERVIEW_RESCHEDULED'
      }
    }

    if (!nextStages[resolvedStage]) {
      nextStages[resolvedStage] = []
    }
    if (interviewDisplayStages.has(resolvedStage) && !hasMeaningfulInterviewCardDetails(candidate)) {
      return
    }
    nextStages[resolvedStage].push({ ...candidate, stage: resolvedStage, display_stage: resolvedStage })
  })

  return nextStages
}

function CandidateCard({
  candidate,
  onApprove,
  onCardClick,
  onReject,
  actionLoading = null,
  draggable = true,
  isDragging
}) {
  return (
    <Card 
      className={cn(
        "transition-shadow",
        draggable && "cursor-grab active:cursor-grabbing",
        isDragging && "opacity-50"
      )} 
      onClick={() => onCardClick && onCardClick(candidate)}
    >
      <CardContent className="p-3">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">{candidate.name}</p>
            {candidate.company_name && (
              <p className="text-xs text-primary font-medium truncate mt-1">{candidate.company_name}</p>
            )}
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

function StageColumn({ stage, candidates, onApprove, onCardClick, onReject, actionLoading, isOver }) {
  const isDerivedStage = stage.id === 'COMPLETED'

  return (
    <div className="flex flex-col w-72 flex-shrink-0">
      <div className="flex items-center gap-2 mb-3">
        <div className={cn('w-3 h-3 rounded-full', stage.color)} />
        <h3 className="font-semibold text-sm">{stage.label}</h3>
        <Badge variant="secondary" className="ml-auto">
          {candidates.length}
        </Badge>
      </div>
      <div 
        className={cn(
          "flex-1 bg-muted/50 rounded-xl p-2 min-h-[500px] transition-colors",
          isOver && "bg-primary/10 ring-2 ring-primary"
        )}
      >
        <div className="space-y-2">
          <ExpandableList
            items={candidates}
            initialCount={5}
            controlsClassName="pt-1"
            renderItem={(candidate) => (
              <div
                key={candidate.id}
                draggable={!isDerivedStage}
                onDragStart={(e) => {
                  if (isDerivedStage) return
                  e.dataTransfer.effectAllowed = 'move'
                  e.dataTransfer.setData('candidateId', candidate.id)
                  e.dataTransfer.setData('fromStage', stage.id)
                }}
              >
                <CandidateCard
                  candidate={candidate}
                  onApprove={onApprove}
                  onCardClick={onCardClick}
                  onReject={onReject}
                  actionLoading={actionLoading}
                  draggable={!isDerivedStage}
                />
              </div>
            )}
          />
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

export default function Pipeline({ superAdminAgencyId = null }) {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const selectedJobId = searchParams.get('job_id')
  const [stages, setStages] = useState({})
  const [dragOverStage, setDragOverStage] = useState(null)
  const [lastMove, setLastMove] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const pipelineQuery = useQuery({
    queryKey: ['pipeline-stages', selectedClient, selectedJobId, superAdminAgencyId],
    queryFn: async () => {
      const params = {}
      if (selectedClient) params.client = selectedClient
      if (selectedJobId) params.job_id = selectedJobId
      if (superAdminAgencyId) params.agency_id = superAdminAgencyId
      return api.getPipelineStages(params)
    },
  })

  const interviewsQuery = useQuery({
    queryKey: ['pipeline-interviews', selectedClient, selectedJobId, superAdminAgencyId],
    queryFn: async () => {
      const params = {}
      if (selectedClient) params.client = selectedClient
      if (selectedJobId) params.job_id = selectedJobId
      if (superAdminAgencyId) params.agency_id = superAdminAgencyId
      return api.getInterviews(params, { includeDefaultLimit: false })
    },
  })

  useEffect(() => {
    if (pipelineQuery.data) {
      setStages(pipelineQuery.data)
    }
  }, [pipelineQuery.data])

  const displayStages = useMemo(
    () => buildPipelineStages(stages, interviewsQuery.data || []),
    [interviewsQuery.data, stages]
  )

  const handleCardClick = async (candidate) => {
    // No special click handling needed
  }

  const handleCompletedDecision = async (candidate, nextStage) => {
    const loadingKey = `${nextStage === 'SELECTED' ? 'approve' : 'reject'}-${candidate.id}`
    setActionLoading(loadingKey)
    try {
      await api.updateCandidateStage(candidate.id, nextStage)
      setStages((prev) => {
        const sanitizedStages = Object.fromEntries(
          Object.entries(prev).map(([stageId, items]) => [
            stageId,
            (items || []).filter((item) => String(item.id) !== String(candidate.id)),
          ])
        )
        const nextStages = {
          ...sanitizedStages,
          [nextStage]: [...(sanitizedStages[nextStage] || []), { ...candidate, stage: nextStage, display_stage: nextStage }],
        }
        queryClient.setQueryData(['pipeline-stages', selectedClient, selectedJobId, superAdminAgencyId], nextStages)
        return nextStages
      })
      toast({
        title: 'Success',
        description: `Candidate moved to ${nextStage === 'SELECTED' ? 'Selected' : 'Rejected'}.`,
      })
    } catch (error) {
      console.error(`Failed to move candidate to ${nextStage}:`, error)
      toast({
        title: 'Error',
        description: 'Failed to update candidate stage',
        variant: 'destructive',
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleDrop = async (e, toStage) => {
    e.preventDefault()
    setDragOverStage(null)

    if (toStage === 'COMPLETED') return
    
    const candidateId = e.dataTransfer.getData('candidateId')
    const fromStage = e.dataTransfer.getData('fromStage')
    
    if (!candidateId || fromStage === toStage) return
    
    try {
      await api.updateCandidateStage(candidateId, toStage)
      
      // Store move for undo
      const candidate = displayStages[fromStage]?.find(c => c.id === candidateId)
      setLastMove({
        candidateId: candidateId,
        candidateName: candidate?.name,
        fromStage,
        toStage
      })
      
      // Update local state
      setStages(prev => {
        const candidate = prev[fromStage]?.find(c => c.id === candidateId)
        if (!candidate) return prev
        
        const nextStages = {
          ...prev,
          [fromStage]: prev[fromStage].filter(c => c.id !== candidateId),
          [toStage]: [...(prev[toStage] || []), { ...candidate, stage: toStage }]
        }
        queryClient.setQueryData(['pipeline-stages', selectedClient, selectedJobId, superAdminAgencyId], nextStages)
        return nextStages
      })
      
      toast({
        title: 'Success',
        description: 'Candidate stage updated successfully',
      })
    } catch (error) {
      console.error('Failed to update stage:', error)
      toast({
        title: 'Error',
        description: 'Failed to update candidate stage',
        variant: 'destructive',
      })
    }
  }

  const handleUndo = async () => {
    if (!lastMove) return
    
    try {
      await api.updateCandidateStage(lastMove.candidateId, lastMove.fromStage)
      
      // Update local state
      setStages(prev => {
        const candidate = prev[lastMove.toStage]?.find(c => c.id === lastMove.candidateId)
        if (!candidate) return prev
        
        const nextStages = {
          ...prev,
          [lastMove.toStage]: prev[lastMove.toStage].filter(c => c.id !== lastMove.candidateId),
          [lastMove.fromStage]: [...(prev[lastMove.fromStage] || []), { ...candidate, stage: lastMove.fromStage }]
        }
        queryClient.setQueryData(['pipeline-stages', selectedClient, selectedJobId, superAdminAgencyId], nextStages)
        return nextStages
      })
      
      toast({
        title: 'Undone',
        description: `Moved ${lastMove.candidateName} back to previous stage`,
      })
      
      setLastMove(null)
    } catch (error) {
      console.error('Failed to undo:', error)
      toast({
        title: 'Error',
        description: 'Failed to undo move',
        variant: 'destructive',
      })
    }
  }

  const handleDragOver = (e, stageId) => {
    e.preventDefault()
    setDragOverStage(stageId)
  }

  const handleDragLeave = () => {
    setDragOverStage(null)
  }

  if (pipelineQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Candidate Pipeline</h1>
          <p className="text-muted-foreground">View candidates by stage</p>
        </div>
        {lastMove && (
          <Button
            onClick={handleUndo}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            <Undo2 className="h-4 w-4" />
            Undo Last Move
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-x-auto pb-4">
        <div className="flex gap-4 h-full min-w-max">
          {STAGES.map((stage) => (
            <div
              key={stage.id}
              onDrop={(e) => handleDrop(e, stage.id)}
              onDragOver={(e) => handleDragOver(e, stage.id)}
              onDragLeave={handleDragLeave}
            >
              <StageColumn
                stage={stage}
                candidates={displayStages[stage.id] || []}
                onApprove={(candidate) => handleCompletedDecision(candidate, 'SELECTED')}
                onCardClick={handleCardClick}
                onReject={(candidate) => handleCompletedDecision(candidate, 'REJECTED')}
                actionLoading={actionLoading}
                isOver={dragOverStage === stage.id}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
