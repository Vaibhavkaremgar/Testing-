import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { cn, formatDate, getScoreColor, getStageColor, formatStage } from '@/lib/utils'
import {
  Upload, FileText, Search, Filter, MoreHorizontal, Edit, CheckCircle, Clock, AlertCircle, Trash2, Sheet, Eye
} from 'lucide-react'

export default function Resumes() {
  const [candidates, setCandidates] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedJob, setSelectedJob] = useState('')
  const [uploadType, setUploadType] = useState('single')
  const [error, setError] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [editingCandidate, setEditingCandidate] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '' })
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [candidateJob, setCandidateJob] = useState(null)
  const [minPassingScore, setMinPassingScore] = useState(60)
  const [syncing, setSyncing] = useState(false)
  const [viewingResume, setViewingResume] = useState(null)
  const [resumeSummary, setResumeSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  // Load minimum passing score from localStorage
  useEffect(() => {
    const savedScore = localStorage.getItem('minPassingScore')
    if (savedScore) {
      setMinPassingScore(parseInt(savedScore))
    }

    // Listen for localStorage changes (cross-tab)
    const handleStorageChange = (e) => {
      if (e.key === 'minPassingScore') {
        setMinPassingScore(parseInt(e.newValue) || 60)
      }
    }

    // Listen for custom events (same page)
    const handleScoreChange = (e) => {
      setMinPassingScore(e.detail.newScore)
    }

    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('minPassingScoreChanged', handleScoreChange)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('minPassingScoreChanged', handleScoreChange)
    }
  }, [])

  const fetchCandidates = useCallback(async () => {
    try {
      const jobId = selectedJob ? parseInt(selectedJob) : undefined
      const data = await api.getCandidates({ search, job_id: jobId })
      setCandidates(data || [])
    } catch (error) {
      console.error('Failed to fetch candidates:', error)
      setCandidates([])
    }
  }, [search, selectedJob])

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [candidatesData, jobsData] = await Promise.all([
          api.getCandidates(),
          api.getJobs({ is_active: true })
        ])
        setCandidates(candidatesData || [])
        setJobs((jobsData || []).filter(job => job.is_active))
      } catch (error) {
        console.error('Failed to fetch data:', error)
        setCandidates([])
        setJobs([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  useEffect(() => {
    const debounce = setTimeout(fetchCandidates, 300)
    return () => clearTimeout(debounce)
  }, [search, selectedJob, fetchCandidates])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const validateFiles = (files) => {
    const validFiles = []
    const invalidFiles = []
    
    for (const file of files) {
      let isValid = false
      
      if (uploadType === 'zip') {
        // For ZIP upload, only accept ZIP files
        isValid = file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip')
      } else {
        // For single/bulk upload, accept PDF and Word files
        const validTypes = [
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        const validExtensions = ['.pdf', '.doc', '.docx']
        
        isValid = validTypes.includes(file.type) || 
                 validExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
      }
      
      if (isValid) {
        validFiles.push(file)
      } else {
        invalidFiles.push(file.name)
      }
    }
    
    if (invalidFiles.length > 0) {
      const expectedType = uploadType === 'zip' ? 'ZIP files' : 'PDF and Word files (.pdf, .doc, .docx)'
      setError(`Only ${expectedType} are allowed. Invalid files: ${invalidFiles.join(', ')}`)
      return []
    }
    
    setError('')
    return validFiles
  }
  const handleDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const files = [...e.dataTransfer.files]
    const validFiles = validateFiles(files)
    if (validFiles.length > 0) {
      setSelectedFiles(validFiles)
    }
  }

  const handleFileInput = async (e) => {
    const files = [...e.target.files]
    const validFiles = validateFiles(files)
    if (validFiles.length > 0) {
      setSelectedFiles(validFiles)
    }
    e.target.value = '' // Reset input
  }

  const handleManualUpload = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select files to upload')
      return
    }
    await handleUpload(selectedFiles)
    setSelectedFiles([]) // Clear selected files after upload
  }

  const handleUpload = async (files) => {
    setUploading(true)
    setError('')
    
    console.log('Starting upload with:', {
      filesCount: files.length,
      selectedJob,
      jobId: selectedJob ? parseInt(selectedJob) : null,
      uploadType,
      threshold: minPassingScore
    })
    
    try {
      const jobId = selectedJob ? parseInt(selectedJob) : null
      
      if (uploadType === 'zip') {
        console.log('ZIP file upload')
        const result = await api.zipUploadResumes(files[0], jobId, minPassingScore)
        console.log('ZIP upload result:', result)
      } else if (files.length === 1) {
        console.log('Single file upload')
        const result = await api.uploadResume(files[0], jobId, minPassingScore)
        console.log('Upload result:', result)
      } else {
        console.log('Bulk file upload')
        const result = await api.bulkUploadResumes(files, jobId, minPassingScore)
        console.log('Bulk upload result:', result)
      }
      
      // Refresh candidates list to show new data with scores and status
      await fetchCandidates()
      
      // Show success message
      alert('Resume(s) uploaded successfully! Scores and status have been calculated.')
    } catch (error) {
      console.error('Upload failed:', error)
      setError(`Upload failed: ${error.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleEdit = (candidate) => {
    setEditingCandidate(candidate)
    setEditForm({
      name: candidate.name || '',
      email: candidate.email || '',
      phone: candidate.phone || ''
    })
  }

  const handleSaveEdit = async () => {
    try {
      await api.updateCandidate(editingCandidate.id, editForm)
      setEditingCandidate(null)
      await fetchCandidates()
      
      // Auto-sync to sheets after update
      try {
        await api.syncCandidatesToSheets()
      } catch (syncError) {
        console.error('Auto-sync to sheets failed:', syncError)
      }
    } catch (error) {
      console.error('Update failed:', error)
      setError(`Update failed: ${error.message}`)
    }
  }

  const handleCancelEdit = () => {
    setEditingCandidate(null)
    setEditForm({ name: '', email: '', phone: '' })
  }

  const handleDelete = async (id) => {
    if (confirm('Are you sure you want to delete this candidate?')) {
      try {
        await api.deleteCandidate(id)
        await fetchCandidates()
        
        // Auto-sync to sheets after delete
        try {
          await api.syncCandidatesToSheets()
        } catch (syncError) {
          console.error('Auto-sync to sheets failed:', syncError)
        }
      } catch (error) {
        console.error('Delete failed:', error)
        setError(`Delete failed: ${error.message}`)
      }
    }
  }

  const handleViewCandidate = async (candidate) => {
    setSelectedCandidate(candidate)
    setAnalysisLoading(true)
    setAiAnalysis(null)
    
    // Fetch job details
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
    
    // Fetch AI analysis
    try {
      const analysis = await api.getAIAnalysis(candidate.id)
      // Override match_score with resume_score for consistency
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

  const handleCloseModal = () => {
    setSelectedCandidate(null)
    setCandidateJob(null)
    setAiAnalysis(null)
  }

  const handleViewResume = async (candidate) => {
    if (!candidate.resume_file_path) {
      alert('No resume file available for this candidate')
      return
    }

    try {
      const url = api.getResumeFileUrl(candidate.id)
      const token = api.getToken()
      
      if (!token) {
        alert('Authentication required. Please log in again.')
        return
      }

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Resume file not found on server')
        } else if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.')
        } else {
          throw new Error(`Failed to fetch resume (Status: ${response.status})`)
        }
      }
      
      const blob = await response.blob()
      
      if (blob.size === 0) {
        throw new Error('Resume file is empty')
      }
      
      const blobUrl = window.URL.createObjectURL(blob)
      const newWindow = window.open(blobUrl, '_blank')
      
      if (!newWindow) {
        // Popup blocked - download instead
        const link = document.createElement('a')
        link.href = blobUrl
        link.download = `${candidate.name}_resume.pdf`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      }
      
      // Clean up the blob URL after a delay
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 5000)
    } catch (error) {
      console.error('Error viewing resume:', error)
      alert(`Unable to view resume: ${error.message}`)
    }
  }

  const handleResumeSummary = async (candidate) => {
    setViewingResume(candidate)
    setSummaryLoading(true)
    try {
      const summary = await api.getResumeSummary(candidate.id)
      setResumeSummary(summary.summary)
    } catch (error) {
      console.error('Failed to fetch resume summary:', error)
      setResumeSummary('Unable to generate summary at this time.')
    } finally {
      setSummaryLoading(false)
    }
  }

  const closeResumeModal = () => {
    setViewingResume(null)
    setResumeSummary(null)
  }

  const handleSyncToSheets = async () => {
    setSyncing(true)
    setError('')
    
    try {
      const result = await api.syncCandidatesToSheets()
      if (result.sheets_synced !== undefined) {
        alert(`Sync to sheets completed successfully! ${result.sheets_synced} candidates synced.`)
      } else {
        alert(`Generated candidate IDs for ${result.synced_count} candidates!`)
      }
      await fetchCandidates() // Refresh to update sync status
    } catch (error) {
      console.error('Sync failed:', error)
      setError(`Sync failed: ${error.message}`)
    } finally {
      setSyncing(false)
    }
  }

  const handleSyncFromSheets = async () => {
    setSyncing(true)
    setError('')
    
    try {
      const result = await api.syncScoresFromSheets()
      if (result.success) {
        alert(`Successfully updated ${result.updated_count} candidates with scores from Google Sheets!`)
        await fetchCandidates() // Refresh to show updated scores and statuses
      } else {
        alert(`Sync failed: ${result.error}`)
      }
    } catch (error) {
      console.error('Sync from sheets failed:', error)
      setError(`Sync failed: ${error.message}`)
    } finally {
      setSyncing(false)
    }
  }

  const getParsingStatusBadge = (status) => {
    const statusConfig = {
      completed: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
      processing: { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-100 dark:bg-yellow-900/30' },
      pending: { icon: Clock, color: 'text-gray-600', bg: 'bg-gray-100 dark:bg-gray-800' },
      failed: { icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
    }
    const config = statusConfig[status] || statusConfig.pending
    return (
      <div className={cn('flex items-center gap-1 px-2 py-1 rounded-full text-xs', config.bg, config.color)}>
        <config.icon className="h-3 w-3" />
        <span className="capitalize">{status}</span>
      </div>
    )
  }

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
        <p className="text-muted-foreground">Upload and manage candidate resumes</p>
      </div>

      {/* Upload Section */}
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
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
            >
              <option value="">Select Job (Optional)</option>
              {jobs.filter(job => job.is_active).map((job) => (
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
          <div
            className={cn(
              'border-2 border-dashed rounded-xl p-8 text-center transition-colors',
              dragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25',
              uploading && 'opacity-50 pointer-events-none'
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-lg font-medium mb-2">
              {uploading ? 'Uploading...' : selectedFiles.length > 0 ? `${selectedFiles.length} file(s) selected` : `Drag and drop ${uploadType === 'zip' ? 'ZIP file' : 'resumes'} here`}
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              {uploadType === 'zip' ? 'ZIP files containing resumes only' : 'PDF and Word formats (.pdf, .doc, .docx)'}
            </p>
            {selectedFiles.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-medium mb-2">Selected files:</p>
                <div className="text-xs text-muted-foreground space-y-1">
                  {selectedFiles.map((file, index) => (
                    <div key={index} className="flex items-center justify-between bg-muted p-2 rounded">
                      <span>{file.name}</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => setSelectedFiles(files => files.filter((_, i) => i !== index))}
                      >
                        ×
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <input
              type="file"
              multiple={uploadType !== 'single'}
              accept={uploadType === 'zip' ? '.zip' : '.pdf,.doc,.docx'}
              className="hidden"
              id="file-upload"
              onChange={handleFileInput}
            />
            <div className="flex gap-2">
              <Button asChild variant="outline">
                <label htmlFor="file-upload" className="cursor-pointer">
                  Browse {uploadType === 'zip' ? 'ZIP File' : uploadType === 'single' ? 'Resume' : 'Resumes'}
                </label>
              </Button>
              {selectedFiles.length > 0 && (
                <Button onClick={handleManualUpload} disabled={uploading}>
                  {uploading ? 'Uploading...' : 'Upload Files'}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          className="flex h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm"
          value={selectedJob}
          onChange={(e) => setSelectedJob(e.target.value)}
        >
          <option value="">All Jobs</option>
          {jobs.filter(job => job.is_active).map((job) => (
            <option key={job.id} value={job.id}>
              {job.company_name ? `${job.company_name} - ${job.title}` : job.title}
            </option>
          ))}
        </select>
        <Button 
          onClick={handleSyncToSheets} 
          disabled={syncing || candidates.length === 0}
          className="flex items-center gap-2"
        >
          <Sheet className="h-4 w-4" />
          {syncing ? 'Syncing...' : 'Sync TO Sheets'}
        </Button>
        <Button 
          onClick={handleSyncFromSheets} 
          disabled={syncing}
          className="flex items-center gap-2"
        >
          <Sheet className="h-4 w-4" />
          {syncing ? 'Syncing...' : 'Sync FROM Sheets'}
        </Button>
      </div>

      {/* Table */}
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
                  <th className="text-left p-4 font-medium">Date</th>
                  <th className="text-right p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.id} className="border-b hover:bg-muted/50 transition-colors cursor-pointer" onClick={() => handleViewCandidate(candidate)}>
                    <td className="p-4" onClick={(e) => e.stopPropagation()}>
                      {editingCandidate?.id === candidate.id ? (
                        <div className="space-y-2">
                          <Input
                            value={editForm.name}
                            onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                            placeholder="Name"
                            className="h-8"
                          />
                          <Input
                            value={editForm.email}
                            onChange={(e) => setEditForm({...editForm, email: e.target.value})}
                            placeholder="Email"
                            className="h-8"
                          />
                          <Input
                            value={editForm.phone}
                            onChange={(e) => setEditForm({...editForm, phone: e.target.value})}
                            placeholder="Phone"
                            className="h-8"
                          />
                        </div>
                      ) : (
                        <div onClick={() => handleViewCandidate(candidate)}>
                          <p className="font-medium text-primary hover:underline cursor-pointer">{candidate.name}</p>
                          <p className="text-sm text-muted-foreground">{candidate.email}</p>
                        </div>
                      )}
                    </td>
                    <td className="p-4">
                      {candidate.job_title ? (
                        <div>
                          <p className="text-sm font-medium">{candidate.job_title}</p>
                          {jobs.find(j => j.id === candidate.job_id)?.company_name && (
                            <p className="text-xs text-muted-foreground">
                              {jobs.find(j => j.id === candidate.job_id).company_name}
                            </p>
                          )}
                        </div>
                      ) : (
                        <span className="text-sm">-</span>
                      )}
                    </td>
                    <td className="p-4">
                      {candidate.resume_score !== null && candidate.resume_score !== undefined ? (
                        <div className="flex items-center gap-2">
                          <span className={cn('font-semibold', candidate.resume_score >= 80 ? 'text-green-600' : candidate.resume_score >= 60 ? 'text-yellow-600' : 'text-red-600')}>
                            {candidate.resume_score}
                          </span>
                          <Progress value={candidate.resume_score} className="w-16 h-2" />
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="p-4">
                      {candidate.stage === 'interview_scheduled' ? (
                        <Badge className="bg-blue-500">Interview Scheduled</Badge>
                      ) : candidate.stage === 'shortlisted' ? (
                        <Badge className="bg-green-500">Shortlisted</Badge>
                      ) : candidate.stage === 'rejected' ? (
                        <Badge className="bg-red-500">Rejected</Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
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
                      {formatDate(candidate.created_at)}
                    </td>
                    <td className="p-4" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        {editingCandidate?.id === candidate.id ? (
                          <>
                            <Button variant="outline" size="sm" onClick={handleSaveEdit}>
                              Save
                            </Button>
                            <Button variant="ghost" size="sm" onClick={handleCancelEdit}>
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button variant="ghost" size="icon" onClick={() => handleViewResume(candidate)} title="View Resume">
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => handleEdit(candidate)}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => handleDelete(candidate.id)}>
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {candidates.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                No candidates found
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Candidate Details Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={handleCloseModal}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Candidate Details</h2>
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
                <h3 className="font-semibold mb-3">AI Resume Analysis</h3>
                {analysisLoading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    <span>Analyzing resume...</span>
                  </div>
                ) : aiAnalysis ? (
                  <div className="space-y-4">
                    {/* AI Generated Summary */}
                    {selectedCandidate.summary && (
                      <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                        <p className="text-sm font-medium mb-2 text-blue-900 dark:text-blue-100">📋 Candidate Summary</p>
                        <p className="text-sm text-blue-800 dark:text-blue-200 leading-relaxed">{selectedCandidate.summary}</p>
                      </div>
                    )}

                    {/* Match Score */}
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

                    {/* Key Strengths */}
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

                    {/* Skill Gaps */}
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
            </div>
          </div>
        </div>
      )}

      {/* Resume Summary Modal */}
      {viewingResume && resumeSummary && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeResumeModal}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Resume Summary - {viewingResume.name}</h2>
              <Button variant="ghost" size="icon" onClick={closeResumeModal}>
                ×
              </Button>
            </div>
            
            <div className="space-y-4">
              <div className="bg-muted p-4 rounded-lg">
                {summaryLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    <span>Generating summary...</span>
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed">{resumeSummary}</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
