import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn, getScoreColor } from '@/lib/utils'
import {
  DndContext,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, User, Briefcase, Star } from 'lucide-react'

const STAGES = [
  { id: 'uploaded', label: 'Applied', color: 'bg-gray-500' },
  { id: 'shortlisted', label: 'Shortlisted', color: 'bg-purple-500' },
  { id: 'interview_scheduled', label: 'Interview Scheduled', color: 'bg-orange-500' },
  { id: 'interview_rescheduled', label: 'Interview Rescheduled', color: 'bg-yellow-500' },
  { id: 'interviewed', label: 'Interviewed', color: 'bg-cyan-500' },
  { id: 'no_show', label: 'No Show', color: 'bg-pink-500' },
  { id: 'selected', label: 'Selected', color: 'bg-green-500' },
  { id: 'rejected', label: 'Rejected', color: 'bg-red-500' },
]

function CandidateCard({ candidate, isDragging, onCardClick }) {
  return (
    <Card className={cn(
      'cursor-grab active:cursor-grabbing transition-shadow',
      isDragging && 'shadow-xl opacity-90'
    )}
    onClick={() => onCardClick && onCardClick(candidate)}
    >
      <CardContent className="p-3">
        <div className="flex items-start gap-2">
          <GripVertical className="h-4 w-4 text-muted-foreground mt-1 flex-shrink-0" />
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

function SortableCandidateCard({ candidate, onCardClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: candidate.id.toString() })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <CandidateCard candidate={candidate} isDragging={isDragging} onCardClick={onCardClick} />
    </div>
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
        <SortableContext
          items={candidates.map(c => c.id.toString())}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {candidates.map((candidate) => (
              <SortableCandidateCard key={candidate.id} candidate={candidate} onCardClick={onCardClick} />
            ))}
          </div>
        </SortableContext>
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
  const [stages, setStages] = useState({})
  const [loading, setLoading] = useState(true)
  const [activeId, setActiveId] = useState(null)
  const [activeCandidate, setActiveCandidate] = useState(null)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  useEffect(() => {
    const fetchPipeline = async () => {
      try {
        const data = await api.getPipelineStages()
        setStages(data)
      } catch (error) {
        console.error('Failed to fetch pipeline:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchPipeline()
  }, [])

  const findCandidateAndStage = (id) => {
    for (const [stageName, candidates] of Object.entries(stages)) {
      const candidate = candidates.find(c => c.id.toString() === id)
      if (candidate) {
        return { candidate, stage: stageName }
      }
    }
    return { candidate: null, stage: null }
  }

  const handleCardClick = async (candidate) => {
    // Only handle click for candidates in interview_rescheduled stage
    if (candidate.stage === 'interview_rescheduled') {
      try {
        // Move candidate back to shortlisted stage to restart the flow
        await api.updateCandidateStage(candidate.id, 'shortlisted')
        
        // Update local state
        setStages((prev) => {
          const rescheduledCandidates = [...prev.interview_rescheduled]
          const shortlistedCandidates = [...(prev.shortlisted || [])]
          
          // Remove from rescheduled
          const candidateIndex = rescheduledCandidates.findIndex(c => c.id === candidate.id)
          if (candidateIndex > -1) {
            const [movedCandidate] = rescheduledCandidates.splice(candidateIndex, 1)
            movedCandidate.stage = 'shortlisted'
            
            // Add to shortlisted
            shortlistedCandidates.push(movedCandidate)
          }
          
          return {
            ...prev,
            interview_rescheduled: rescheduledCandidates,
            shortlisted: shortlistedCandidates,
          }
        })
      } catch (error) {
        console.error('Failed to move candidate:', error)
      }
    }
  }

  const handleDragStart = (event) => {
    const { active } = event
    setActiveId(active.id)
    const { candidate } = findCandidateAndStage(active.id)
    setActiveCandidate(candidate)
  }

  const handleDragOver = (event) => {
    const { active, over } = event
    if (!over) return

    const activeId = active.id
    const overId = over.id

    const { stage: activeStage } = findCandidateAndStage(activeId)
    const { stage: overStage } = findCandidateAndStage(overId)

    // Check if we're dropping on a stage column
    const overIsStage = STAGES.some(s => s.id === overId)
    const targetStage = overIsStage ? overId : overStage

    if (activeStage && targetStage && activeStage !== targetStage) {
      setStages((prev) => {
        const activeItems = [...prev[activeStage]]
        const overItems = [...(prev[targetStage] || [])]

        const activeIndex = activeItems.findIndex(c => c.id.toString() === activeId)
        const [movedItem] = activeItems.splice(activeIndex, 1)

        return {
          ...prev,
          [activeStage]: activeItems,
          [targetStage]: [...overItems, movedItem],
        }
      })
    }
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveId(null)
    setActiveCandidate(null)

    if (!over) return

    const activeId = active.id
    const { stage: finalStage } = findCandidateAndStage(activeId)

    if (finalStage) {
      try {
        await api.updateCandidateStage(parseInt(activeId), finalStage)
      } catch (error) {
        console.error('Failed to update stage:', error)
        // Optionally refresh the pipeline on error
      }
    }
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
        <p className="text-muted-foreground">Drag and drop candidates between stages</p>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
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

        <DragOverlay>
          {activeCandidate ? (
            <div className="w-72">
              <CandidateCard candidate={activeCandidate} isDragging />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
