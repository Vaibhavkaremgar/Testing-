import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { cn, formatDate } from '@/lib/utils'
import { Upload, FileText, Search, Eye, CheckCircle, ThumbsUp, ThumbsDown } from 'lucide-react'

export default function Resumes() {
  const { user: currentUser } = useAuth()
  const isAdmin = currentUser?.role === 'admin'
  
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  
  // Admin-only states
  const [jobs, setJobs] = useState([])
  const [users, setUsers] = useState([])
  const [uploading, setUploading] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState([])
  const [selectedJobForUpload, setSelectedJobForUpload] = useState('')
  const [uploadType, setUploadType] = useState('single')
  const [error, setError] = useState('')
  const [selectedCandidates, setSelectedCandidates] = useState([])
  const [selectedUser, setSelectedUser] = useState('')
  const [assigning, setAssigning] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      if (isAdmin) {
        const [candidatesData, jobsData, usersData] = await Promise.all([
          api.getCandidates(),
          api.getJobs(),
          api.getAllUsers()
        ])
        setCandidates(candidatesData || [])
        setJobs(jobsData?.filter(j => j.is_active) || [])
        setUsers(usersData || [])
      } else {
        const data = await api.getMyAssignedCandidates()
        setCandidates(data || [])
      }
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFileInput = (e) => {
    setSelectedFiles([...e.target.files])
    e.target.value = ''
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return
    setUploading(true)
    setError('')
    
    try {
      const jobId = selectedJobForUpload ? parseInt(selectedJobForUpload) : null
      
      if (uploadType === 'zip') {
        await api.zipUploadResumes(selectedFiles[0], jobId, 60)
      } else if (selectedFiles.length === 1) {
        await api.uploadResume(selectedFiles[0], jobId, 60)
      } else {
        await api.bulkUploadResumes(selectedFiles, jobId, 60)
      }
      
      setSelectedFiles([])
      await fetchData()
      alert('Upload successful!')
    } catch (error) {
      setError(`Upload failed: ${error.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleAssign = async () => {
    if (!selectedUser || selectedCandidates.length === 0) return
    setAssigning(true)
    
    try {
      for (const candidateId of selectedCandidates) {
        await api.assignCandidate(candidateId, parseInt(selectedUser))
      }
      alert(`Assigned ${selectedCandidates.length} candidates`)
      setSelectedCandidates([])
      setSelectedUser('')
      await fetchData()
    } catch (error) {
      alert(`Assignment failed: ${error.message}`)
    } finally {
      setAssigning(false)
    }
  }

  const handleViewCandidate = async (candidate) => {
    setSelectedCandidate(candidate)
    setAnalysisLoading(true)
    
    try {
      const analysis = await api.getAIAnalysis(candidate.id)
      if (analysis && candidate.resume_score !== undefined) {
        analysis.match_score = candidate.resume_score
      }
      setAiAnalysis(analysis)
    } catch (error) {
      console.error('Failed to fetch AI analysis:', error)
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleReview = async (action) => {
    try {
      await api.reviewCandidate(selectedCandidate.id, action)
      alert(action === 'interview' ? 'Interview invitation sent!' : 'Candidate rejected')
      setSelectedCandidate(null)
      await fetchData()
    } catch (error) {
      alert(`Failed: ${error.message}`)
    }
  }

  const handleViewResume = (candidate) => {
    if (!candidate.resume_file_path) {
      alert('No resume file available')
      return
    }
    const url = api.getResumeFileUrl(candidate.id)
    const token = api.getToken()
    window.open(`${url}?token=${encodeURIComponent(token)}`, '_blank')
  }

  const filteredCandidates = candidates.filter(c => 
    c.name?.toLowerCase().includes(search.toLowerCase()) ||
    c.email?.toLowerCase().includes(search.toLowerCase())
  )

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
        <h1 className="text-2xl font-bold">Resume Management</h1>
        <p className="text-muted-foreground">
          {isAdmin ? 'Upload and manage candidate resumes' : 'Review assigned resumes'}
        </p>
      </div>

      {/* Upload Section - Admin Only */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Upload Resumes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 mb-4">
              <select
                className="flex h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={selectedJobForUpload}
                onChange={(e) => setSelectedJobForUpload(e.target.value)}
              >
                <option value="">Select Job (Optional)</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.company_name ? `${job.company_name} - ${job.title}` : job.title}
                  </option>
                ))}
              </select>
              <select
                className="flex h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
              >
                <option value="single">Single Upload</option>
                <option value="bulk">Bulk Upload</option>
                <option value="zip">ZIP Upload</option>
              </select>
            </div>
            {error && (
              <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}
            <div className="border-2 border-dashed rounded-xl p-8 text-center">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-lg font-medium mb-2">
                {selectedFiles.length > 0 ? `${selectedFiles.length} file(s) selected` : 'Select files to upload'}
              </p>
              <input
                type="file"
                multiple={uploadType !== 'single'}
                accept={uploadType === 'zip' ? '.zip' : '.pdf,.doc,.docx'}
                className="hidden"
                id="file-upload"
                onChange={handleFileInput}
              />
              <div className="flex gap-2 justify-center">
                <Button asChild variant="outline">
                  <label htmlFor="file-upload" className="cursor-pointer">
                    Browse Files
                  </label>
                </Button>
                {selectedFiles.length > 0 && (
                  <Button onClick={handleUpload} disabled={uploading}>
                    {uploading ? 'Uploading...' : 'Upload'}
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Assignment Bar - Admin Only */}
      {isAdmin && selectedCandidates.length > 0 && (
        <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <span className="font-medium">{selectedCandidates.length} selected</span>
              <select
                className="flex h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
              >
                <option value="">Select User to Assign</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name} ({user.role})
                  </option>
                ))}
              </select>
              <Button onClick={handleAssign} disabled={assigning || !selectedUser}>
                {assigning ? 'Assigning...' : 'Assign'}
              </Button>
              <Button variant="ghost" onClick={() => setSelectedCandidates([])}>
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search candidates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  {isAdmin && (
                    <th className="text-left p-4 font-medium w-12">
                      <input
                        type="checkbox"
                        checked={selectedCandidates.length === filteredCandidates.length && filteredCandidates.length > 0}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedCandidates(filteredCandidates.map(c => c.id))
                          } else {
                            setSelectedCandidates([])
                          }
                        }}
                        className="w-4 h-4"
                      />
                    </th>
                  )}
                  <th className="text-left p-4 font-medium">Candidate</th>
                  <th className="text-left p-4 font-medium">Job</th>
                  <th className="text-left p-4 font-medium">Score</th>
                  <th className="text-left p-4 font-medium">Skills</th>
                  <th className="text-left p-4 font-medium">Date</th>
                  <th className="text-right p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((candidate) => (
                  <tr key={candidate.id} className="border-b hover:bg-muted/50 transition-colors">
                    {isAdmin && (
                      <td className="p-4">
                        <input
                          type="checkbox"
                          checked={selectedCandidates.includes(candidate.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedCandidates([...selectedCandidates, candidate.id])
                            } else {
                              setSelectedCandidates(selectedCandidates.filter(id => id !== candidate.id))
                            }
                          }}
                          className="w-4 h-4"
                        />
                      </td>
                    )}
                    <td className="p-4">
                      <p className="font-medium">{candidate.name}</p>
                      <p className="text-sm text-muted-foreground">{candidate.email}</p>
                    </td>
                    <td className="p-4">
                      <p className="text-sm">{candidate.job_title || '-'}</p>
                    </td>
                    <td className="p-4">
                      {candidate.resume_score ? (
                        <div className="flex items-center gap-2">
                          <span className={cn('font-semibold', candidate.resume_score >= 80 ? 'text-green-600' : candidate.resume_score >= 60 ? 'text-yellow-600' : 'text-red-600')}>
                            {candidate.resume_score}
                          </span>
                          <Progress value={candidate.resume_score} className="w-16 h-2" />
                        </div>
                      ) : '-'}
                    </td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {candidate.skills?.slice(0, 3).map((skill) => (
                          <Badge key={skill} variant="secondary" className="text-xs">{skill}</Badge>
                        ))}
                        {candidate.skills?.length > 3 && (
                          <Badge variant="outline" className="text-xs">+{candidate.skills.length - 3}</Badge>
                        )}
                      </div>
                    </td>
                    <td className="p-4 text-sm text-muted-foreground">
                      {formatDate(candidate.created_at)}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="icon" onClick={() => handleViewResume(candidate)}>
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleViewCandidate(candidate)}>
                          <CheckCircle className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredCandidates.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                {isAdmin ? 'No candidates found' : 'No resumes assigned to you'}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Candidate Details Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedCandidate(null)}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Candidate Details</h2>
              <Button variant="ghost" size="icon" onClick={() => setSelectedCandidate(null)}>×</Button>
            </div>
            
            <div className="space-y-6">
              {/* Personal Info */}
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
                </div>
              </div>

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

              {/* AI Analysis */}
              <div>
                <h3 className="font-semibold mb-3">AI Analysis</h3>
                {analysisLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    <span>Analyzing...</span>
                  </div>
                ) : aiAnalysis ? (
                  <div className="space-y-4">
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
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No analysis available</p>
                )}
              </div>

              {/* Action Buttons */}
              {!isAdmin && (
                <div className="pt-4 border-t">
                  <div className="flex gap-3">
                    <Button className="flex-1" onClick={() => handleReview('interview')}>
                      <ThumbsUp className="h-4 w-4 mr-2" />
                      Send Interview
                    </Button>
                    <Button variant="destructive" className="flex-1" onClick={() => handleReview('reject')}>
                      <ThumbsDown className="h-4 w-4 mr-2" />
                      Reject
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
