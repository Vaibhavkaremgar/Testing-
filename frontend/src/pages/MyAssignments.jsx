import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { cn, formatDate } from '@/lib/utils'
import { Eye } from 'lucide-react'

export default function MyAssignments() {
  const { user } = useAuth()
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [candidateJob, setCandidateJob] = useState(null)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    fetchCandidates()
  }, [])

  const fetchCandidates = async () => {
    try {
      const data = await api.getMyAssignedCandidates()
      setCandidates(data)
    } catch (error) {
      console.error('Failed to fetch candidates:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleViewCandidate = async (candidate) => {
    setSelectedCandidate(candidate)
    setAnalysisLoading(true)
    setAiAnalysis(null)
    
    if (candidate.job_id) {
      try {
        const job = await api.getJob(candidate.job_id)
        setCandidateJob(job)
      } catch (error) {
        console.error('Failed to fetch job details:', error)
        setCandidateJob(null)
      }
    } else {
      setCandidateJob(null)
    }
    
    try {
      const analysis = await api.getAIAnalysis(candidate.id)
      if (analysis && candidate.resume_score !== undefined) {
        analysis.match_score = candidate.resume_score
      }
      setAiAnalysis(analysis)
    } catch (error) {
      console.error('Failed to fetch AI analysis:', error)
      setAiAnalysis(null)
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleReview = async (action) => {
    setReviewing(true)
    try {
      await api.reviewCandidate(selectedCandidate.id, action)
      alert(`Candidate ${action === 'interview' ? 'approved for interview' : 'rejected'} successfully`)
      setSelectedCandidate(null)
      setCandidateJob(null)
      setAiAnalysis(null)
      await fetchCandidates()
    } catch (error) {
      alert(`Failed: ${error.message}`)
    } finally {
      setReviewing(false)
    }
  }

  const handleViewResume = (candidate) => {
    const url = api.getResumeFileUrl(candidate.id)
    const token = api.getToken()
    window.open(`${url}?token=${encodeURIComponent(token)}`, '_blank')
  }

  const handleCloseModal = () => {
    setSelectedCandidate(null)
    setCandidateJob(null)
    setAiAnalysis(null)
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Resumes</h1>
        <p className="text-muted-foreground">Review candidates assigned to you</p>
      </div>

      {candidates.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No candidates assigned to you yet
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-4 font-medium">Candidate</th>
                    <th className="text-left p-4 font-medium">Job</th>
                    <th className="text-left p-4 font-medium">Score</th>
                    <th className="text-left p-4 font-medium">Status</th>
                    <th className="text-left p-4 font-medium">Skills</th>
                    <th className="text-left p-4 font-medium">Assigned</th>
                    <th className="text-right p-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate) => (
                    <tr 
                      key={candidate.id} 
                      className="border-b hover:bg-muted/50 cursor-pointer"
                      onClick={() => handleViewCandidate(candidate)}
                    >
                      <td className="p-4">
                        <div>
                          <p className="font-medium text-primary hover:underline">{candidate.name}</p>
                          <p className="text-sm text-muted-foreground">{candidate.email}</p>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="text-sm">{candidate.job_title || '-'}</span>
                      </td>
                      <td className="p-4">
                        {candidate.resume_score ? (
                          <div className="flex items-center gap-2">
                            <span className={cn('font-semibold', 
                              candidate.resume_score >= 80 ? 'text-green-600' : 
                              candidate.resume_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                            )}>
                              {candidate.resume_score}
                            </span>
                            <Progress value={candidate.resume_score} className="w-16 h-2" />
                          </div>
                        ) : '-'}
                      </td>
                      <td className="p-4">
                        <Badge className={
                          candidate.review_status === 'pending' ? 'bg-yellow-500' :
                          candidate.review_status === 'interview_invited' ? 'bg-green-500' :
                          candidate.review_status === 'rejected' ? 'bg-red-500' : 'bg-gray-500'
                        }>
                          {candidate.review_status?.replace('_', ' ') || 'Pending'}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {candidate.skills?.slice(0, 3).map((skill) => (
                            <Badge key={skill} variant="secondary" className="text-xs">
                              {skill}
                            </Badge>
                          ))}
                          {candidate.skills?.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{candidate.skills.length - 3}
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="p-4 text-sm text-muted-foreground">
                        {formatDate(candidate.assigned_at)}
                      </td>
                      <td className="p-4" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handleViewResume(candidate)}
                            title="View Resume"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Candidate Review Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={handleCloseModal}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Candidate Review</h2>
              <Button variant="ghost" size="icon" onClick={handleCloseModal}>
                ×
              </Button>
            </div>
            
            <div className="space-y-6">
              {/* Candidate Info */}
              <div>
                <h3 className="font-semibold mb-3">Personal Information</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Name</p>
                    <p className="font-medium">{selectedCandidate.name}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Email</p>
                    <p>{selectedCandidate.email}</p>
                  </div>
                  {selectedCandidate.phone && (
                    <div>
                      <p className="text-sm text-muted-foreground">Phone</p>
                      <p>{selectedCandidate.phone}</p>
                    </div>
                  )}
                  {selectedCandidate.location && (
                    <div>
                      <p className="text-sm text-muted-foreground">Location</p>
                      <p>{selectedCandidate.location}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Professional Info */}
              {(selectedCandidate.current_company || selectedCandidate.current_role || selectedCandidate.experience_years) && (
                <div>
                  <h3 className="font-semibold mb-3">Professional Information</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {selectedCandidate.current_company && (
                      <div>
                        <p className="text-sm text-muted-foreground">Current Company</p>
                        <p>{selectedCandidate.current_company}</p>
                      </div>
                    )}
                    {selectedCandidate.current_role && (
                      <div>
                        <p className="text-sm text-muted-foreground">Current Role</p>
                        <p>{selectedCandidate.current_role}</p>
                      </div>
                    )}
                    {selectedCandidate.experience_years && (
                      <div>
                        <p className="text-sm text-muted-foreground">Experience</p>
                        <p>{selectedCandidate.experience_years} years</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Skills */}
              {selectedCandidate.skills && selectedCandidate.skills.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-3">Skills</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedCandidate.skills.map((skill) => (
                      <Badge key={skill} variant="secondary">{skill}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Job Information */}
              {candidateJob && (
                <div>
                  <h3 className="font-semibold mb-3">Applied Position</h3>
                  <div className="bg-muted p-4 rounded-lg">
                    <h4 className="font-medium text-lg mb-2">{candidateJob.title}</h4>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Department</p>
                        <p>{candidateJob.department}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Location</p>
                        <p>{candidateJob.location}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Employment Type</p>
                        <p>{candidateJob.employment_type}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Experience Level</p>
                        <p>{candidateJob.experience_level}</p>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground mb-2">Job Description</p>
                      <div className="text-sm whitespace-pre-wrap bg-background p-3 rounded border max-h-40 overflow-y-auto">
                        {candidateJob.description}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* AI Analysis */}
              <div>
                <h3 className="font-semibold mb-3">Pontis Insight</h3>
                {analysisLoading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    <span>Analyzing resume...</span>
                  </div>
                ) : aiAnalysis ? (
                  <div className="space-y-4">
                    {selectedCandidate.summary && (
                      <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                        <p className="text-sm font-medium mb-2 text-blue-900 dark:text-blue-100">📋 Candidate Summary</p>
                        <p className="text-sm text-blue-800 dark:text-blue-200 leading-relaxed">{selectedCandidate.summary}</p>
                      </div>
                    )}

                    <div className="bg-muted p-4 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Resume Score</span>
                        <Badge className={aiAnalysis.match_score >= 80 ? 'bg-green-500' : aiAnalysis.match_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'}>
                          {aiAnalysis.match_score >= 80 ? 'Strong Fit' : aiAnalysis.match_score >= 60 ? 'Good Fit' : 'Needs Review'}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-2xl font-bold">{aiAnalysis.match_score}</span>
                        <Progress value={aiAnalysis.match_score} className="flex-1" />
                      </div>
                    </div>

                    {aiAnalysis.key_strengths && aiAnalysis.key_strengths.length > 0 && (
                      <div>
                        <p className="text-sm font-medium mb-2">Key Strengths</p>
                        <ul className="space-y-1">
                          {aiAnalysis.key_strengths.map((strength, idx) => (
                            <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                              <span className="text-green-500 mt-1">✓</span>
                              <span>{strength}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {aiAnalysis.skill_gaps && aiAnalysis.skill_gaps.length > 0 && (
                      <div>
                        <p className="text-sm font-medium mb-2">Areas for Improvement</p>
                        <ul className="space-y-1">
                          {aiAnalysis.skill_gaps.map((gap, idx) => (
                            <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                              <span className="text-yellow-500 mt-1">⚠</span>
                              <span>{gap}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No AI analysis available for this candidate.</p>
                )}
              </div>

              {/* Review Actions */}
              {selectedCandidate.review_status === 'pending' && (
                <div className="pt-4 border-t">
                  <div className="flex gap-3">
                    <Button 
                      className="flex-1 bg-green-600 hover:bg-green-700"
                      onClick={() => handleReview('interview')}
                      disabled={reviewing}
                    >
                      {reviewing ? 'Processing...' : 'Send Interview Invitation'}
                    </Button>
                    <Button 
                      variant="destructive"
                      className="flex-1"
                      onClick={() => handleReview('reject')}
                      disabled={reviewing}
                    >
                      {reviewing ? 'Processing...' : 'Reject'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
