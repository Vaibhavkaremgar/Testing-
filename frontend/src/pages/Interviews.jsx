import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { Pagination } from '@/components/ui/pagination'
import { api } from '@/lib/api'
import { cn, formatDateTime, getScoreColor } from '@/lib/utils'
import {
  Video, Calendar, Clock, User, FileText, Brain, Star, Send, X, Play, CheckCircle, RotateCcw, Plus, ExternalLink
} from 'lucide-react'

export default function Interviews() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [interviews, setInterviews] = useState([])
  const [selectedInterview, setSelectedInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [candidates, setCandidates] = useState([])
  const [jobs, setJobs] = useState([])
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
  const [currentPage, setCurrentPage] = useState(1)
  const [totalInterviews, setTotalInterviews] = useState(0)
  const ITEMS_PER_PAGE = 10

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        const skip = (currentPage - 1) * ITEMS_PER_PAGE
        const params = { skip, limit: ITEMS_PER_PAGE }
        if (selectedClient) params.client = selectedClient
        
        // Get only SELECTED and REJECTED candidates
        const [selected, rejected, countData] = await Promise.all([
          api.getCandidates({ ...params, stage: 'SELECTED' }),
          api.getCandidates({ ...params, stage: 'REJECTED' }),
          api.getCandidatesCount(selectedClient ? { client: selectedClient } : {})
        ])
        
        const allCandidates = [...selected, ...rejected]
        
        // Transform to interview format
        const interviewsData = allCandidates.map(candidate => ({
          id: candidate.id,
          candidate_id: candidate.id,
          candidate_name: candidate.name,
          interview_type: 'technical',
          scheduled_at: candidate.created_at,
          status: 'completed',
          video_url: candidate.interview_video_url,
          transcript: candidate.interview_transcript,
          ai_summary: candidate.interview_ai_summary || candidate.summary || 'No summary available',
          interview_score: candidate.interview_technical_score && candidate.interview_communication_score && candidate.interview_culture_fit_score 
            ? Math.round((candidate.interview_technical_score + candidate.interview_communication_score + candidate.interview_culture_fit_score) / 3)
            : candidate.resume_score || 0,
          technical_score: candidate.interview_technical_score || candidate.resume_score || 0,
          communication_score: candidate.interview_communication_score || candidate.resume_score || 0,
          culture_fit_score: candidate.interview_culture_fit_score || candidate.resume_score || 0
        }))
        
        setInterviews(interviewsData)
        setTotalInterviews(countData.count)
        if (interviewsData.length > 0 && !selectedInterview) {
          setSelectedInterview(interviewsData[0])
        }
      } catch (error) {
        console.error('Failed to fetch interviews:', error)
        setInterviews([])
        setTotalInterviews(0)
      } finally {
        setLoading(false)
      }
    }
    
    const fetchCandidates = async () => {
      try {
        const data = await api.getCandidates()
        setCandidates(data)
      } catch (error) {
        console.error('Failed to fetch candidates:', error)
      }
    }
    
    const fetchJobs = async () => {
      try {
        const data = await api.getJobs()
        setJobs(data)
      } catch (error) {
        console.error('Failed to fetch jobs:', error)
      }
    }
    
    fetchInterviews()
    fetchCandidates()
    fetchJobs()
  }, [selectedClient, currentPage])

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
    if (!selectedInterview) return;
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'selected');
      alert('Candidate approved and moved to Selected stage!');
      // Remove from interviews list and clear selection
      const updatedInterviews = interviews.filter(i => i.id !== selectedInterview.id);
      setInterviews(updatedInterviews);
      setSelectedInterview(updatedInterviews.length > 0 ? updatedInterviews[0] : null);
    } catch (error) {
      console.error('Failed to approve candidate:', error);
      alert('Failed to approve candidate');
    }
  }

  const handleReject = async () => {
    if (!selectedInterview) return;
    try {
      await api.updateCandidateStage(selectedInterview.candidate_id, 'rejected');
      alert('Candidate rejected and moved to Rejected stage!');
      // Remove from interviews list and clear selection
      const updatedInterviews = interviews.filter(i => i.id !== selectedInterview.id);
      setInterviews(updatedInterviews);
      setSelectedInterview(updatedInterviews.length > 0 ? updatedInterviews[0] : null);
    } catch (error) {
      console.error('Failed to reject candidate:', error);
      alert('Failed to reject candidate');
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
            <CardTitle className="text-base">Completed Interviews</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {interviews.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground px-4">
                <Video className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No completed interviews</p>
              </div>
            ) : (
              <>
                <div className="flex flex-col">
                  {interviews.map((interview) => (
                    <button
                      key={interview.id}
                      onClick={() => setSelectedInterview(interview)}
                      className={cn(
                        "px-4 py-3 text-left hover:bg-muted transition-colors border-l-2",
                        selectedInterview?.id === interview.id
                          ? "bg-muted border-primary font-medium"
                          : "border-transparent"
                      )}
                    >
                      {interview.candidate_name}
                    </button>
                  ))}
                </div>
                <div className="p-2">
                  <Pagination
                    currentPage={currentPage}
                    totalPages={Math.ceil(totalInterviews / ITEMS_PER_PAGE)}
                    totalItems={totalInterviews}
                    itemsPerPage={ITEMS_PER_PAGE}
                    onPageChange={setCurrentPage}
                  />
                </div>
              </>
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
                <Button className="bg-green-600 hover:bg-green-700 text-white" onClick={handleApprove}>
                  Approve
                </Button>
                <Button className="bg-red-600 hover:bg-red-700 text-white" onClick={handleReject}>
                  Reject
                </Button>
              </div>
            </div>
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
                  {selectedInterview.video_url ? (
                    <video controls className="w-full h-full rounded-xl">
                      <source src={selectedInterview.video_url} type="video/mp4" />
                      Your browser does not support the video tag.
                    </video>
                  ) : (
                    <div className="text-center text-muted-foreground">
                      <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
                      <p>No recording available</p>
                    </div>
                  )}
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
