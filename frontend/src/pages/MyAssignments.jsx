import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { cn, formatDate } from '@/lib/utils'
import { Eye, CheckCircle, XCircle } from 'lucide-react'

export default function MyAssignments() {
  const { user } = useAuth()
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCandidate, setSelectedCandidate] = useState(null)

  useEffect(() => {
    fetchAssignments()
  }, [])

  const fetchAssignments = async () => {
    try {
      const data = await api.getMyAssignedCandidates()
      setAssignments(data)
    } catch (error) {
      console.error('Failed to fetch assignments:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleReview = async (candidateId, action) => {
    try {
      await api.reviewCandidate(candidateId, action)
      alert(`Candidate ${action === 'interview' ? 'approved for interview' : 'rejected'}`)
      fetchAssignments()
      setSelectedCandidate(null)
    } catch (error) {
      alert(`Failed: ${error.message}`)
    }
  }

  const handleViewResume = (candidate) => {
    const url = api.getResumeFileUrl(candidate.id)
    const token = api.getToken()
    window.open(`${url}?token=${encodeURIComponent(token)}`, '_blank')
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Assignments</h1>
        <p className="text-muted-foreground">Review candidates assigned to you</p>
      </div>

      {assignments.length === 0 ? (
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
                    <th className="text-left p-4 font-medium">Assigned</th>
                    <th className="text-right p-4 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.map((candidate) => (
                    <tr key={candidate.id} className="border-b hover:bg-muted/50">
                      <td className="p-4">
                        <div>
                          <p className="font-medium">{candidate.name}</p>
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
                      <td className="p-4 text-sm text-muted-foreground">
                        {formatDate(candidate.assigned_at)}
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => handleViewResume(candidate)}
                            title="View Resume"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {candidate.review_status === 'pending' && (
                            <>
                              <Button 
                                variant="ghost" 
                                size="icon"
                                onClick={() => handleReview(candidate.id, 'interview')}
                                title="Approve for Interview"
                              >
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="icon"
                                onClick={() => handleReview(candidate.id, 'reject')}
                                title="Reject"
                              >
                                <XCircle className="h-4 w-4 text-red-600" />
                              </Button>
                            </>
                          )}
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
    </div>
  )
}
