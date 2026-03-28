import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { cn, formatDateTime, getScoreColor } from '@/lib/utils'
import { useToast } from '@/hooks/use-toast'
import {
  Video, Calendar, Clock, User, FileText, Brain, Star, Send, X, Play, CheckCircle, RotateCcw, Plus, ExternalLink
} from 'lucide-react'

const DEFAULT_LIST_LIMIT = 100

function getInterviewPlaybackUrl(interview) {
  if (!interview) return ''
  return api.getInterviewVideoUrl(interview.session_token || interview.async_token || interview.id)
}

function getInterviewResultMeta(interview) {
  if (interview?.status === 'completed' && typeof interview?.interview_score === 'number') {
    if (interview.interview_score >= 6) {
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
    label: (interview?.status || 'Pending').replace('_', ' '),
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
  const [videoError, setVideoError] = useState('')
  const [mediaMode, setMediaMode] = useState('video')
  const [decisionLoading, setDecisionLoading] = useState(null)
  const { toast } = useToast()
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    email: '',
    jobId: '',
    jobTitle: '',
    slot: '',
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
        const interviewRows = await api.getInterviews({ ...params, limit: DEFAULT_LIST_LIMIT })
        const interviewsData = (interviewRows || [])
          .map(interview => ({
            ...interview,
            playback_url: getInterviewPlaybackUrl(interview)
          }))
        
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
        const params = { limit: DEFAULT_LIST_LIMIT }
        if (superAdminAgencyId) params.agency_id = superAdminAgencyId
        const data = await api.getCandidates(params)
        setCandidates(data)
      } catch (error) {
        console.error('Failed to fetch candidates:', error)
      }
    }
    
    const fetchJobs = async () => {
      try {
        const params = { limit: DEFAULT_LIST_LIMIT }
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

  const handleScheduleInterview = async () => {
    try {
      if (!scheduleForm.email) {
        alert('Please select a candidate first');
        return;
      }
      if (!scheduleForm.meetingLink) {
        alert('Please enter a meeting link');
        return;
      }
      
      // Compose email with meeting link
      const subject = encodeURIComponent(`Interview Invitation - ${scheduleForm.name}`);
      const body = encodeURIComponent(
        `Dear ${scheduleForm.name},\n\n` +
        `We are pleased to invite you for an interview.\n\n` +
        `Meeting Link: ${scheduleForm.meetingLink}\n\n` +
        `Please join the meeting at the scheduled time.\n\n` +
        `Best regards,\nHR Team`
      );
      
      // Open default email client with pre-filled content
      window.location.href = `mailto:${scheduleForm.email}?subject=${subject}&body=${body}`;
      
      alert(`Email client opened for ${scheduleForm.email}`);
      setShowScheduleModal(false);
      setScheduleForm({
        name: '',
        email: '',
        jobId: '',
        jobTitle: '',
        slot: '',
        resumeText: '',
        jdText: '',
        meetingLink: '',
        predefinedQuestions: ''
      });
    } catch (error) {
      console.error('Failed to send interview email:', error)
      alert('Failed to open email client')
    }
  }

  const handleApprove = async () => {
    if (!selectedInterview || selectedInterview.status !== 'completed') return;
    setDecisionLoading('approve')
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'SELECTED', { suppress_notification: true });
      toast({
        title: 'Candidate Selected',
        description: 'Candidate moved to Selected without sending an interview email.',
      })
      // Remove from interviews list and clear selection
      const updatedInterviews = interviews.filter(i => i.id !== selectedInterview.id);
      setInterviews(updatedInterviews);
      setSelectedInterview(updatedInterviews.length > 0 ? updatedInterviews[0] : null);
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

  const handleReject = async () => {
    if (!selectedInterview || selectedInterview.status !== 'completed') return;
    setDecisionLoading('reject')
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'REJECTED', { suppress_notification: true });
      toast({
        title: 'Candidate Rejected',
        description: 'Candidate moved to Rejected without sending an interview email.',
      })
      // Remove from interviews list and clear selection
      const updatedInterviews = interviews.filter(i => i.id !== selectedInterview.id);
      setInterviews(updatedInterviews);
      setSelectedInterview(updatedInterviews.length > 0 ? updatedInterviews[0] : null);
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

  useEffect(() => {
    setVideoError('')
    setMediaMode('video')
  }, [selectedInterview?.id])

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
        <Button onClick={() => setShowScheduleModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Schedule Interview
        </Button>
      </div>

      {/* Main Content - Side by Side */}
      <div className="flex gap-4 flex-1 overflow-hidden">
        {/* Candidate List - Left Side */}
        <Card className="w-64 flex-shrink-0 bg-blue-50 dark:bg-blue-950">
          <CardHeader className="py-4">
            <CardTitle className="text-base">Interview Recordings</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {interviews.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground px-4">
                <Video className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No interview recordings</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2 p-2">
                {interviews.slice(0, visibleCount).map((interview) => {
                  const resultMeta = getInterviewResultMeta(interview)
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
                      <span className="text-xs text-muted-foreground">Interview Score</span>
                      <span className={cn('text-sm font-semibold', getScoreColor(interview.interview_score ?? 0))}>
                        {typeof interview.interview_score === 'number' ? interview.interview_score : '-'}
                      </span>
                    </div>
                  </button>
                  )
                })}
                {visibleCount < interviews.length && (
                  <button
                    className="px-4 py-3 text-sm text-primary hover:bg-muted transition-colors text-center border-t"
                    onClick={() => setVisibleCount(v => v + SHOW_MORE_STEP)}
                  >
                    Show More ({interviews.length - visibleCount} remaining)
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
              <div className="flex gap-2">
                <Button
                  className="bg-green-600 hover:bg-green-700 text-white"
                  onClick={handleApprove}
                  disabled={selectedInterview.status !== 'completed' || decisionLoading !== null}
                >
                  {decisionLoading === 'approve' ? 'Sending...' : 'Approve'}
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700 text-white"
                  onClick={handleReject}
                  disabled={selectedInterview.status !== 'completed' || decisionLoading !== null}
                >
                  {decisionLoading === 'reject' ? 'Sending...' : 'Reject'}
                </Button>
              </div>
            </div>
            {selectedInterview.status !== 'completed' && (
              <p className="text-xs text-muted-foreground mt-2">
                Decision emails can be sent only after the interview is completed.
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
                <div className="bg-muted rounded-xl aspect-video flex items-center justify-center">
                  {selectedInterview.playback_url && mediaMode === 'video' ? (
                    <video
                      key={selectedInterview.id}
                      controls
                      preload="metadata"
                      playsInline
                      className="w-full h-full rounded-xl"
                      src={selectedInterview.playback_url}
                      onError={() => setVideoError('Unable to load interview recording. The video may be missing or in an unsupported format.')}
                      onLoadedMetadata={(e) => {
                        const element = e.currentTarget
                        if (element.videoWidth === 0 || element.videoHeight === 0) {
                          setMediaMode('audio')
                          setVideoError('This recording does not include a video track. Playing audio instead.')
                        } else {
                          setMediaMode('video')
                          setVideoError('')
                        }
                      }}
                    >
                      Your browser does not support the video tag.
                    </video>
                  ) : selectedInterview.playback_url && mediaMode === 'audio' ? (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
                      <Video className="h-16 w-16 opacity-40" />
                      <div>
                        <p className="font-medium">Audio-Only Recording</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          This interview recording was saved without a video track.
                        </p>
                      </div>
                      <audio
                        key={`${selectedInterview.id}-audio`}
                        controls
                        preload="metadata"
                        className="w-full max-w-lg"
                        src={selectedInterview.playback_url}
                        onError={() => setVideoError('Unable to load interview recording. The audio file may be missing or unsupported.')}
                      >
                        Your browser does not support the audio tag.
                      </audio>
                    </div>
                  ) : (
                    <div className="text-center text-muted-foreground">
                      <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
                      <p>No recording available</p>
                    </div>
                  )}
                </div>
                {videoError && (
                  <p className="mt-3 text-sm text-destructive">{videoError}</p>
                )}
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
        ) : interviews.length > 0 ? (
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
                    window.open('https://calendly.com', '_blank')
                  }}
                >
                  Book Interview Slot
                </Button>
              </div>
              
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

