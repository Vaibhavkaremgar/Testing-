import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn, getScoreColor } from '@/lib/utils'
import { Briefcase, Star, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DndContext, DragOverlay, closestCorners, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { useToast } from '@/hooks/use-toast'

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

function CandidateCard({ candidate, onCardClick, isDragging }) {

  return (
    <Card 
      className={cn(
        "transition-shadow cursor-grab active:cursor-grabbing",
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

const STAGE_SHOW_MORE_STEP = 20

function StageColumn({ stage, candidates, onCardClick, isOver }) {
  const isShortlisted = stage.id === 'SHORTLISTED'
  const [visibleCount, setVisibleCount] = useState(10)
  const visible = candidates.slice(0, visibleCount)

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
          {visible.map((candidate) => (
            <div
              key={candidate.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.effectAllowed = 'move'
                e.dataTransfer.setData('candidateId', candidate.id)
                e.dataTransfer.setData('fromStage', stage.id)
              }}
            >
              <CandidateCard 
                candidate={candidate} 
                onCardClick={onCardClick} 
              />
            </div>
          ))}
        </div>
        {candidates.length === 0 && (
          <div className="flex items-center justify-center h-24 text-muted-foreground text-sm">
            No candidates
          </div>
        )}
        {visibleCount < candidates.length && (
          <button
            className="w-full mt-2 py-1.5 text-xs text-primary hover:underline"
            onClick={() => setVisibleCount(v => v + STAGE_SHOW_MORE_STEP)}
          >
            Show More ({candidates.length - visibleCount} remaining)
          </button>
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
  const [dragOverStage, setDragOverStage] = useState(null)
  const [lastMove, setLastMove] = useState(null)
  const { toast } = useToast()

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

  const handleDrop = async (e, toStage) => {
    e.preventDefault()
    setDragOverStage(null)
    
    const candidateId = e.dataTransfer.getData('candidateId')
    const fromStage = e.dataTransfer.getData('fromStage')
    
    if (!candidateId || fromStage === toStage) return
    
    try {
      await api.updateCandidateStage(candidateId, toStage)
      
      // Store move for undo
      const candidate = stages[fromStage]?.find(c => c.id === candidateId)
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
        
        return {
          ...prev,
          [fromStage]: prev[fromStage].filter(c => c.id !== candidateId),
          [toStage]: [...(prev[toStage] || []), { ...candidate, stage: toStage }]
        }
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
        
        return {
          ...prev,
          [lastMove.toStage]: prev[lastMove.toStage].filter(c => c.id !== lastMove.candidateId),
          [lastMove.fromStage]: [...(prev[lastMove.fromStage] || []), { ...candidate, stage: lastMove.fromStage }]
        }
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

  if (loading) {
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
                candidates={stages[stage.id] || []}
                onCardClick={handleCardClick}
                isOver={dragOverStage === stage.id}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
