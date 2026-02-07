import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { cn, formatDateTime, getScoreColor } from '@/lib/utils'
import {
  Video, Calendar, Clock, User, FileText, Brain, Star, Send, X, Play, CheckCircle, RotateCcw
} from 'lucide-react'

export default function Interviews() {
  const [interviews, setInterviews] = useState([])
  const [selectedInterview, setSelectedInterview] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        const data = await api.getInterviews()
        // Filter to show only completed interviews
        const completedInterviews = data.filter(interview => interview.status === 'completed')
        setInterviews(completedInterviews)
        if (completedInterviews.length > 0) {
          setSelectedInterview(completedInterviews[0])
        }
      } catch (error) {
        console.error('Failed to fetch interviews:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchInterviews()
  }, [])

  const handleSendOffer = async (candidateId) => {
    try {
      console.log('Sending offer to candidate:', candidateId)
      alert('Offer sent successfully!')
    } catch (error) {
      console.error('Failed to send offer:', error)
      alert('Failed to send offer')
    }
  }

  const handleReject = async (candidateId) => {
    try {
      console.log('Rejecting candidate:', candidateId)
      alert('Candidate rejected')
    } catch (error) {
      console.error('Failed to reject candidate:', error)
      alert('Failed to reject candidate')
    }
  }

  const handleRevoke = async (candidateId) => {
    try {
      console.log('Revoking decision for candidate:', candidateId)
      alert('Decision revoked successfully!')
    } catch (error) {
      console.error('Failed to revoke decision:', error)
      alert('Failed to revoke decision')
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
        <h1 className="text-2xl font-bold">Interviews</h1>
        <p className="text-muted-foreground">Review interview recordings and AI analysis</p>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">
        {/* Interview List */}
        <div className="col-span-4 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col overflow-hidden">
            <CardHeader className="py-4">
              <CardTitle className="text-base">Completed Interviews</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto p-0">
              {interviews.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
                  <p>No completed interviews found</p>
                </div>
              ) : (
                <div className="divide-y">
                  {interviews.map((interview) => (
                    <div
                      key={interview.id}
                      className={cn(
                        'p-4 cursor-pointer hover:bg-muted/50 transition-colors',
                        selectedInterview?.id === interview.id && 'bg-muted'
                      )}
                      onClick={() => setSelectedInterview(interview)}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium">{interview.candidate_name}</p>
                          <p className="text-sm text-muted-foreground capitalize">{interview.interview_type}</p>
                        </div>
                        <Badge variant="success">
                          {interview.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDateTime(interview.scheduled_at)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {interview.duration_minutes} min
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Interview Details */}
        <div className="col-span-8 flex flex-col min-h-0">
          {selectedInterview ? (
            <Card className="flex-1 flex flex-col overflow-hidden">
              <CardHeader className="py-4 border-b">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{selectedInterview.candidate_name}</CardTitle>
                    <p className="text-sm text-muted-foreground capitalize">
                      {selectedInterview.interview_type} Interview
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="default" onClick={() => handleSendOffer(selectedInterview.candidate_id)}>
                      <Send className="h-4 w-4 mr-2" />
                      Send Offer
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => handleReject(selectedInterview.candidate_id)}>
                      <X className="h-4 w-4 mr-2" />
                      Reject
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleRevoke(selectedInterview.candidate_id)}>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Revoke
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-auto p-0">
                <Tabs defaultValue="video" className="h-full flex flex-col">
                  <TabsList className="m-4 mb-0 w-fit">
                    <TabsTrigger value="video">
                      <Video className="h-4 w-4 mr-2" />
                      Video
                    </TabsTrigger>
                    <TabsTrigger value="transcript">
                      <FileText className="h-4 w-4 mr-2" />
                      Transcript
                    </TabsTrigger>
                    <TabsTrigger value="analysis">
                      <Brain className="h-4 w-4 mr-2" />
                      AI Analysis
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="video" className="flex-1 p-4 pt-2">
                    <div className="bg-muted rounded-xl aspect-video flex items-center justify-center">
                      {selectedInterview.video_url ? (
                        <div className="text-center">
                          <Play className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
                          <p className="text-muted-foreground">Click to play interview recording</p>
                        </div>
                      ) : (
                        <div className="text-center text-muted-foreground">
                          <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
                          <p>No recording available</p>
                        </div>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="transcript" className="flex-1 p-4 pt-2 overflow-auto">
                    {selectedInterview.transcript ? (
                      <div className="bg-muted rounded-xl p-4 font-mono text-sm whitespace-pre-wrap">
                        {selectedInterview.transcript}
                      </div>
                    ) : (
                      <div className="text-center py-12 text-muted-foreground">
                        No transcript available
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="analysis" className="flex-1 p-4 pt-2 overflow-auto">
                    {selectedInterview.ai_summary ? (
                      <div className="space-y-6">
                        {/* AI Summary */}
                        <div className="bg-muted rounded-xl p-4">
                          <h4 className="font-medium mb-2 flex items-center gap-2">
                            <Brain className="h-4 w-4" />
                            AI Summary
                          </h4>
                          <p className="text-sm">{selectedInterview.ai_summary}</p>
                        </div>

                        {/* Scores */}
                        <div className="grid grid-cols-2 gap-4">
                          <Card>
                            <CardContent className="p-4">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">Overall Score</span>
                                <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.interview_score))}>
                                  {selectedInterview.interview_score}
                                </span>
                              </div>
                              <Progress value={selectedInterview.interview_score} />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardContent className="p-4">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">Technical</span>
                                <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.technical_score))}>
                                  {selectedInterview.technical_score}
                                </span>
                              </div>
                              <Progress value={selectedInterview.technical_score} />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardContent className="p-4">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">Communication</span>
                                <span className={cn('text-lg font-bold', getScoreColor(selectedInterview.communication_score))}>
                                  {selectedInterview.communication_score}
                                </span>
                              </div>
                              <Progress value={selectedInterview.communication_score} />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardContent className="p-4">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">Culture Fit</span>
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
                        <p>Complete the interview to generate AI analysis</p>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          ) : (
            <Card className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
                <p>Select an interview to view details</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
