import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import InterviewRecordingPlayer from '@/components/interviews/InterviewRecordingPlayer'
import { api } from '@/lib/api'
import { cn, formatDateTime, getScoreColor } from '@/lib/utils'
import { useToast } from '@/hooks/use-toast'
import {
  Video, Calendar, Clock, User, FileText, Brain, Star, Send, X, CheckCircle, RotateCcw, Plus, ExternalLink, ChevronDown
} from 'lucide-react'

const DEFAULT_LIST_LIMIT = 20
const INTERVIEW_REJECTION_SCORE_THRESHOLD = 6

function getNumericInterviewScore(interview) {
  const rawScore = interview?.interview_score
  if (rawScore === null || rawScore === undefined || rawScore === '') return null
  const numericScore = Number(rawScore)
  return Number.isFinite(numericScore) ? numericScore : null
}

function getEffectiveInterviewStatus(interview) {
  const normalizedStatus = (interview?.status || '').toLowerCase()
  if (
    normalizedStatus === 'completed' ||
    interview?.has_recording ||
    getNumericInterviewScore(interview) !== null ||
    interview?.transcript ||
    interview?.ai_summary
  ) {
    return 'completed'
  }

  return normalizedStatus || 'pending'
}

function getInterviewResultMeta(interview, candidateStage) {
  const normalizedCandidateStage = String(candidateStage || '').toUpperCase()
  if (normalizedCandidateStage === 'SELECTED') {
    return {
      label: 'Selected',
      badgeClass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    }
  }

  if (normalizedCandidateStage === 'REJECTED') {
    return {
      label: 'Rejected',
      badgeClass: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    }
  }

  const interviewScore = getNumericInterviewScore(interview)
  if (getEffectiveInterviewStatus(interview) === 'completed' && interviewScore !== null) {
    if (interviewScore >= INTERVIEW_REJECTION_SCORE_THRESHOLD) {
      return {
        label: 'Selected',
        badgeClass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      }
    }

    return {
      label: 'Rejected',
      badgeClass: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    }
  }

  return {
    label: getEffectiveInterviewStatus(interview).replace('_', ' '),
    badgeClass: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300',
  }
}

export default function Interviews({ superAdminAgencyId = null }) {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [interviews, setInterviews] = useState([])
  const [selectedInterview, setSelectedInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [visibleCount, setVisibleCount] = useState(20)
  const SHOW_MORE_STEP = 20
  const [candidates, setCandidates] = useState([])
  const [jobs, setJobs] = useState([])
  const [selectedJobFilter, setSelectedJobFilter] = useState('all')
  const [decisionLoading, setDecisionLoading] = useState(null)
  const [approveModalOpen, setApproveModalOpen] = useState(false)
  const { toast } = useToast()
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    email: '',
    candidateId: '',
    jobId: '',
    jobTitle: '',
    slot: '',
    interviewType: 'General',
    scheduledAt: '',
    durationMinutes: 60,
    resumeText: '',
    jdText: '',
    meetingLink: '',
    predefinedQuestions: ''
  })

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        const params = {}
        if (selectedClient) params.client = selectedClient
        if (superAdminAgencyId) params.agency_id = superAdminAgencyId
        const interviewsData = (await api.getInterviews({ ...params, limit: DEFAULT_LIST_LIMIT, offset: 0 })) || []
        
        setInterviews(interviewsData)
        if (interviewsData.length > 0) {
          setSelectedInterview(interviewsData[0])
        }
      } catch (error) {
        console.error('Failed to fetch interviews:', error)
      } finally {
        setLoading(false)
      }
    }
    
    const fetchCandidates = async () => {
      try {
        const params = { limit: DEFAULT_LIST_LIMIT, offset: 0 }
        if (superAdminAgencyId) params.agency_id = superAdminAgencyId
        const data = await api.getCandidates(params)
        setCandidates(data)
      } catch (error) {
        console.error('Failed to fetch candidates:', error)
      }
    }
    
    const fetchJobs = async () => {
      try {
        const params = { limit: DEFAULT_LIST_LIMIT, offset: 0 }
        if (superAdminAgencyId) params.agency_id = superAdminAgencyId
        const data = await api.getJobs(params)
        setJobs(data)
      } catch (error) {
        console.error('Failed to fetch jobs:', error)
      }
    }
    
    fetchInterviews()
    fetchCandidates()
    fetchJobs()
  }, [selectedClient, superAdminAgencyId])

  const activeJobs = useMemo(
    () => (jobs || []).filter((job) => job.is_active),
    [jobs]
  )

  const candidateJobMap = useMemo(() => {
    const map = new Map()
    ;(candidates || []).forEach((candidate) => {
      map.set(String(candidate.id), candidate.job_id ? String(candidate.job_id) : '')
    })
    return map
  }, [candidates])

  const candidateStageMap = useMemo(() => {
    const map = new Map()
    ;(candidates || []).forEach((candidate) => {
      map.set(String(candidate.id), candidate.stage || '')
    })
    return map
  }, [candidates])

  const jobFilteredInterviews = useMemo(() => {
    if (selectedJobFilter === 'all') return interviews

    return interviews.filter((interview) => (
      candidateJobMap.get(String(interview.candidate_id)) === selectedJobFilter
    ))
  }, [candidateJobMap, interviews, selectedJobFilter])

  const filteredInterviews = jobFilteredInterviews

  useEffect(() => {
    if (filteredInterviews.length === 0) {
      setSelectedInterview(null)
      return
    }

    const selectedStillVisible = filteredInterviews.some((interview) => interview.id === selectedInterview?.id)
    if (!selectedStillVisible) {
      setSelectedInterview(filteredInterviews[0])
    }
  }, [filteredInterviews, selectedInterview])

  useEffect(() => {
    setVisibleCount(20)
  }, [selectedJobFilter])

  const handleScheduleInterview = async () => {
    try {
      if (!scheduleForm.email) {
        alert('Please select a candidate first');
        return;
      }
      if (!scheduleForm.candidateId) {
        alert('Please select a candidate first');
        return;
      }
      if (!scheduleForm.meetingLink) {
        alert('Please enter a meeting link');
        return;
      }
      if (!scheduleForm.scheduledAt) {
        alert('Please select interview date and time');
        return;
      }

      const createdInterview = await api.createInterview({
        candidate_id: scheduleForm.candidateId,
        interview_type: scheduleForm.interviewType || 'General',
        scheduled_at: new Date(scheduleForm.scheduledAt).toISOString(),
        duration_minutes: Number(scheduleForm.durationMinutes) || 60,
        meeting_link: scheduleForm.meetingLink,
      })
      setInterviews((prev) => [createdInterview, ...prev])
      toast({
        title: 'Interview Scheduled',
        description: `Interview created for ${scheduleForm.name}.`,
      })
      setShowScheduleModal(false);
      setScheduleForm({
        name: '',
        email: '',
        candidateId: '',
        jobId: '',
        jobTitle: '',
        slot: '',
        interviewType: 'General',
        scheduledAt: '',
        durationMinutes: 60,
        resumeText: '',
        jdText: '',
        meetingLink: '',
        predefinedQuestions: ''
      });
    } catch (error) {
      console.error('Failed to schedule interview:', error)
      alert(error.message || 'Failed to schedule interview')
    }
  }

  const isDecisionReady = selectedInterview && getEffectiveInterviewStatus(selectedInterview) === 'completed'
  const selectedInterviewStage = selectedInterview
    ? candidateStageMap.get(String(selectedInterview.candidate_id))
    : ''
  const selectedInterviewResultMeta = selectedInterview
    ? getInterviewResultMeta(selectedInterview, selectedInterviewStage)
    : null
  const isDecisionFinalized = selectedInterviewResultMeta?.label === 'Selected' || selectedInterviewResultMeta?.label === 'Rejected'
  const handleApprove = async () => {
    if (!selectedInterview) return;
    if (!isDecisionReady) {
      toast({
        title: 'Interview Not Completed',
        description: 'Complete the interview first, then approve or reject the candidate.',
        variant: 'destructive',
      })
      return
    }
    setDecisionLoading('approve')
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'SELECTED');
      setCandidates((prev) => prev.map((candidate) => (
        String(candidate.id) === String(selectedInterview.candidate_id)
          ? { ...candidate, stage: 'SELECTED' }
          : candidate
      )))
      setApproveModalOpen(false)
      toast({
        title: 'Candidate Selected',
        description: 'Candidate moved to Selected and the selection email was queued.',
      })
    } catch (error) {
      console.error('Failed to approve candidate:', error);
      toast({
        title: 'Failed to Select Candidate',
        description: error.message || 'Could not queue the selection email.',
        variant: 'destructive',
      })
    } finally {
      setDecisionLoading(null)
    }
  }

  const openApproveModal = () => {
    if (!selectedInterview) return
    if (!isDecisionReady) {
      toast({
        title: 'Interview Not Completed',
        description: 'Complete the interview first, then approve or reject the candidate.',
        variant: 'destructive',
      })
      return
    }
    setApproveModalOpen(true)
  }

  const handleReject = async () => {
    if (!selectedInterview) return;
    if (!isDecisionReady) {
      toast({
        title: 'Interview Not Completed',
        description: 'Complete the interview first, then approve or reject the candidate.',
        variant: 'destructive',
      })
      return
    }
    setDecisionLoading('reject')
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'REJECTED', { suppress_notification: true });
      setCandidates((prev) => prev.map((candidate) => (
        String(candidate.id) === String(selectedInterview.candidate_id)
          ? { ...candidate, stage: 'REJECTED' }
          : candidate
      )))
      toast({
        title: 'Candidate Rejected',
        description: 'Candidate moved to Rejected without sending an interview email.',
      })
    } catch (error) {
      console.error('Failed to reject candidate:', error);
      toast({
        title: 'Failed to Reject Candidate',
        description: error.message || 'Could not queue the rejection email.',
        variant: 'destructive',
      })
    } finally {
      setDecisionLoading(null)
    }
  }

  const openScheduleModal = () => {
    setShowScheduleModal(true)
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
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Interviews</h1>
          <p className="text-muted-foreground">Review interview recordings and AI analysis</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <ChevronDown className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <select
              className="h-10 w-full appearance-none rounded-lg border border-input bg-background pl-8 pr-3 py-2 text-sm"
              value={selectedJobFilter}
              onChange={(e) => setSelectedJobFilter(e.target.value)}
            >
              <option value="all">All Active Jobs</option>
              {activeJobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </div>
          <Button onClick={openScheduleModal}>
            <Plus className="h-4 w-4 mr-2" />
            Reschedule Interview
          </Button>
        </div>
      </div>

      {/* Main Content - Side by Side */}
        <div className="flex gap-4 flex-1 overflow-hidden">
        {/* Candidate List - Left Side */}
        <Card className="w-80 flex-shrink-0 bg-blue-50 dark:bg-blue-950 xl:w-96">
          <CardHeader className="py-4">
            <CardTitle className="text-base">Interview Queue</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {filteredInterviews.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground px-4">
                <Video className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No interviews found</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2 p-2">
                {filteredInterviews.slice(0, visibleCount).map((interview) => {
                  const resultMeta = getInterviewResultMeta(interview, candidateStageMap.get(String(interview.candidate_id)))
                  const interviewScore = getNumericInterviewScore(interview)
                  return (
                  <button
                    key={interview.id}
                    onClick={() => setSelectedInterview(interview)}
                    className={cn(
                      "rounded-xl border p-3 text-left transition-colors",
                      selectedInterview?.id === interview.id
                        ? "bg-white border-primary shadow-sm dark:bg-slate-900"
                        : "bg-white/70 border-transparent hover:bg-white dark:bg-slate-900/50 dark:hover:bg-slate-900"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium truncate">{interview.candidate_name}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatDateTime(interview.scheduled_at)}
                        </p>
                      </div>
                      <Badge className={resultMeta.badgeClass}>
                        {resultMeta.label}
                      </Badge>
                    </div>
                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        {getEffectiveInterviewStatus(interview) === 'completed' ? 'Interview Score' : 'Status'}
                      </span>
                      {getEffectiveInterviewStatus(interview) === 'completed' ? (
                        <span className={cn('text-sm font-semibold', getScoreColor(interviewScore ?? 0))}>
                          {interviewScore !== null ? interviewScore : '-'}
                        </span>
                      ) : (
                        <span className="text-xs font-medium capitalize text-muted-foreground">
                          {getEffectiveInterviewStatus(interview)}
                        </span>
                      )}
                    </div>
                  </button>
                  )
                })}
                {visibleCount < filteredInterviews.length && (
                  <button
                    className="px-4 py-3 text-sm text-primary hover:bg-muted transition-colors text-center border-t"
                    onClick={() => setVisibleCount(v => v + SHOW_MORE_STEP)}
                  >
                    Show More ({filteredInterviews.length - visibleCount} remaining)
                  </button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Interview Details - Right Side */}
        {selectedInterview ? (
        <Card className="flex-1 flex flex-col overflow-hidden">
          <CardHeader className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{selectedInterview.candidate_name}</CardTitle>
                <p className="text-sm text-muted-foreground capitalize">
                  {selectedInterview.interview_type} Interview • {formatDateTime(selectedInterview.scheduled_at)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {selectedInterviewResultMeta && (
                  <Badge className={selectedInterviewResultMeta.badgeClass}>
                    {selectedInterviewResultMeta.label}
                  </Badge>
                )}
                <Button
                  className="bg-green-600 hover:bg-green-700 text-white"
                  onClick={openApproveModal}
                  disabled={decisionLoading !== null}
                >
                  {decisionLoading === 'approve' ? 'Sending...' : 'Approve'}
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700 text-white"
                  onClick={handleReject}
                  disabled={decisionLoading !== null}
                >
                  {decisionLoading === 'reject' ? 'Sending...' : 'Reject'}
                </Button>
              </div>
            </div>
            {!isDecisionReady && (
              <p className="text-xs text-muted-foreground mt-2">
                Decision emails can be sent only after the interview is completed.
              </p>
            )}
            {isDecisionReady && isDecisionFinalized && (
              <p className="text-xs text-muted-foreground mt-2">
                Final decision already recorded for this interview.
              </p>
            )}
          </CardHeader>
          <CardContent className="flex-1 overflow-auto">
            <Tabs defaultValue="video" className="w-full">
              <TabsList className="w-full">
                <TabsTrigger value="video" className="flex-1">
                  <Video className="h-4 w-4 mr-2" />
                  Video
                </TabsTrigger>
                <TabsTrigger value="transcript" className="flex-1">
                  <FileText className="h-4 w-4 mr-2" />
                  Transcript
                </TabsTrigger>
                <TabsTrigger value="analysis" className="flex-1">
                  <Brain className="h-4 w-4 mr-2" />
                  AI Analysis
                </TabsTrigger>
              </TabsList>

              <TabsContent value="video" className="mt-4">
                <div className="mx-auto w-full max-w-4xl">
                  <div className="aspect-video overflow-hidden rounded-xl bg-transparent">
                    <InterviewRecordingPlayer
                      recordingPath={selectedInterview.recording_path}
                      className="h-full w-full"
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="transcript" className="mt-4">
                {selectedInterview.transcript ? (
                  <div className="bg-muted rounded-xl p-4 font-mono text-sm whitespace-pre-wrap max-h-96 overflow-auto">
                    {selectedInterview.transcript}
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
                    <p>No transcript available</p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="analysis" className="mt-4">
                {selectedInterview.ai_summary ? (
                  <div className="space-y-4">
                    {/* AI Summary */}
                    <div className="bg-muted rounded-xl p-4">
                      <h4 className="font-medium mb-2 flex items-center gap-2">
                        <Brain className="h-4 w-4" />
                        AI Summary
                      </h4>
                      <p className="text-sm">{selectedInterview.ai_summary}</p>
                    </div>

                    {/* Scores */}
                    <div className="grid grid-cols-2 gap-3">
                      <Card>
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium">Overall</span>
                            <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.interview_score))}>
                              {selectedInterview.interview_score}
                            </span>
                          </div>
                          <Progress value={selectedInterview.interview_score} />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium">Technical</span>
                            <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.technical_score))}>
                              {selectedInterview.technical_score}
                            </span>
                          </div>
                          <Progress value={selectedInterview.technical_score} />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium">Communication</span>
                            <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.communication_score))}>
                              {selectedInterview.communication_score}
                            </span>
                          </div>
                          <Progress value={selectedInterview.communication_score} />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium">Culture Fit</span>
                            <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.culture_fit_score))}>
                              {selectedInterview.culture_fit_score}
                            </span>
                          </div>
                          <Progress value={selectedInterview.culture_fit_score} />
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <Brain className="h-16 w-16 mx-auto mb-4 opacity-50" />
                    <p>No AI analysis available</p>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
        ) : filteredInterviews.length > 0 ? (
          <Card className="flex-1 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p>Select a candidate to view interview details</p>
            </div>
          </Card>
        ) : null}
      </div>

      {/* Schedule Interview Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowScheduleModal(false)}>
          <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Schedule Interview</h2>
              <Button variant="ghost" size="icon" onClick={() => setShowScheduleModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1 block">Candidate Name</label>
                <select
                  className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={scheduleForm.name}
                  onChange={async (e) => {
                    const candidateName = e.target.value
                    const selectedCandidate = candidates.find(c => c.name === candidateName)
                    const job = jobs.find(j => j.id === selectedCandidate?.job_id)
                    
                    console.log('Selected candidate:', selectedCandidate)
                    console.log('Job found:', job)
                    
                    let predefinedQuestions = 'No predefined questions available'
                    if (selectedCandidate?.id) {
                      try {
                        const candidateDetails = await api.getCandidate(selectedCandidate.id)
                        predefinedQuestions = candidateDetails.predefined_questions || 'No predefined questions available'
                      } catch (error) {
                        console.error('Failed to fetch candidate details:', error)
                      }
                    }
                    
                     setScheduleForm({
                        ...scheduleForm, 
                        name: candidateName,
                        email: selectedCandidate?.email || '',
                        candidateId: selectedCandidate?.id || '',
                        jobId: job?.job_id || job?.id || '',
                        jobTitle: job?.title || '',
                        resumeText: selectedCandidate?.resume_text || 'No resume text available',
                      jdText: job?.description || 'No job description available',
                      predefinedQuestions: predefinedQuestions
                    })
                  }}
                >
                  <option value="">-- Select a candidate --</option>
                  {candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.name}>
                      {candidate.name}
                    </option>
                  ))}
                </select>
              </div>
              
               <div>
                  <label className="text-sm font-medium mb-1 block">Email</label>
                <input
                  type="email"
                  className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={scheduleForm.email}
                  onChange={(e) => setScheduleForm({...scheduleForm, email: e.target.value})}
                  placeholder="Enter email address"
                />
              </div>
              
               {scheduleForm.name && (
                 <>
                  <div>
                    <label className="text-sm font-medium mb-1 block">Interview Type</label>
                    <input
                      type="text"
                      className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.interviewType}
                      onChange={(e) => setScheduleForm({...scheduleForm, interviewType: e.target.value})}
                      placeholder="General"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-1 block">Interview Date & Time</label>
                    <input
                      type="datetime-local"
                      className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.scheduledAt}
                      onChange={(e) => setScheduleForm({...scheduleForm, scheduledAt: e.target.value})}
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-1 block">Duration (Minutes)</label>
                    <input
                      type="number"
                      min="15"
                      step="15"
                      className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.durationMinutes}
                      onChange={(e) => setScheduleForm({...scheduleForm, durationMinutes: e.target.value})}
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-1 block">Job ID</label>
                    <input
                      type="text"
                      className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.jobId}
                      readOnly
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-1 block">Job Title</label>
                    <input
                      type="text"
                      className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.jobTitle}
                      readOnly
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-1 block">Job Description</label>
                    <textarea
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.jdText}
                      readOnly
                      rows={3}
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-1 block">Resume Text</label>
                    <textarea
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.resumeText}
                      readOnly
                      rows={3}
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-1 block">Predefined Questions</label>
                    <textarea
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      value={scheduleForm.predefinedQuestions}
                      readOnly
                      rows={4}
                    />
                  </div>
                </>
              )}
              
              <div>
                <label className="text-sm font-medium mb-1 block">Slot Booking</label>
                <Button 
                  className="w-full" 
                  variant="outline"
                  onClick={() => {
                    window.open('https://pontis-backend-production.up.railway.app/booking.html', '_blank')
                  }}
                >
                  Book Interview Slot
                </Button>
              </div>
              {/*
              <div>
                <label className="text-sm font-medium mb-1 block">Meeting Link</label>
                <input
                  type="url"
                  className="w-full h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={scheduleForm.meetingLink}
                  onChange={(e) => setScheduleForm({...scheduleForm, meetingLink: e.target.value})}
                  placeholder="Enter meeting link (e.g., Zoom, Google Meet)"
                />
              </div>
              
              <div className="pt-4">
                <Button className="w-full" onClick={handleScheduleInterview}>
                  Send Email
                </Button>
              </div>
              */}
            </div>
          </div>
        </div>
      )}

      {approveModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setApproveModalOpen(false)}>
          <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-bold">Approve Candidate</h2>
                <p className="text-sm text-muted-foreground mt-2">Are you sure to approve</p>
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                  onClick={handleApprove}
                  disabled={decisionLoading !== null}
                >
                  {decisionLoading === 'approve' ? 'Sending...' : 'Approve'}
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setApproveModalOpen(false)}
                  disabled={decisionLoading !== null}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

