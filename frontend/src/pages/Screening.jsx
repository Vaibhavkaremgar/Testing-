import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn, formatDateTime, getScoreColor } from '@/lib/utils'
import {
  Video, Calendar, Clock, User, Briefcase, Star, Phone, Mail, MapPin
} from 'lucide-react'

export default function Screening() {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchScreeningCandidates = async () => {
      try {
        const data = await api.getCandidates({ stage: 'screening' })
        setCandidates(data)
      } catch (error) {
        console.error('Failed to fetch screening candidates:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchScreeningCandidates()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Interview Happening</h1>
        <p className="text-muted-foreground">Candidates currently in interview process</p>
      </div>

      {candidates.length === 0 ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <div className="text-center text-muted-foreground">
              <Video className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p>No interviews happening at the moment</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {candidates.map((candidate) => (
            <Card key={candidate.id} className="hover:shadow-lg transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{candidate.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{candidate.current_role}</p>
                  </div>
                  <Badge variant="default" className="bg-blue-500">
                    <Video className="h-3 w-3 mr-1" />
                    Live
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Contact Info */}
                <div className="space-y-2">
                  {candidate.email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span>{candidate.email}</span>
                    </div>
                  )}
                  {candidate.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span>{candidate.phone}</span>
                    </div>
                  )}
                  {candidate.location && (
                    <div className="flex items-center gap-2 text-sm">
                      <MapPin className="h-4 w-4 text-muted-foreground" />
                      <span>{candidate.location}</span>
                    </div>
                  )}
                </div>

                {/* Professional Info */}
                {candidate.current_company && (
                  <div className="flex items-center gap-2 text-sm">
                    <Briefcase className="h-4 w-4 text-muted-foreground" />
                    <span>{candidate.current_company}</span>
                    {candidate.experience_years && (
                      <Badge variant="outline" className="text-xs">
                        {candidate.experience_years}y exp
                      </Badge>
                    )}
                  </div>
                )}

                {/* Applied Position */}
                {candidate.job_title && (
                  <div>
                    <p className="text-sm font-medium">Applied for:</p>
                    <Badge variant="secondary" className="mt-1">
                      {candidate.job_title}
                    </Badge>
                  </div>
                )}

                {/* Resume Score */}
                {candidate.resume_score && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Resume Score:</span>
                    <div className="flex items-center gap-1">
                      <Star className="h-4 w-4 text-yellow-500" />
                      <span className={cn('font-semibold', getScoreColor(candidate.resume_score))}>
                        {candidate.resume_score}
                      </span>
                    </div>
                  </div>
                )}

                {/* Skills */}
                {candidate.skills && candidate.skills.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Skills:</p>
                    <div className="flex flex-wrap gap-1">
                      {candidate.skills.slice(0, 4).map((skill) => (
                        <Badge key={skill} variant="outline" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                      {candidate.skills.length > 4 && (
                        <Badge variant="outline" className="text-xs">
                          +{candidate.skills.length - 4}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}