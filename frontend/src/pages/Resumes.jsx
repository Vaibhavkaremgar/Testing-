import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { cn, formatDate, getScoreColor, getStageColor, formatStage } from '@/lib/utils'
import {
  Upload, FileText, Search, Filter, MoreHorizontal, Edit, CheckCircle, Clock, AlertCircle, Trash2, Sheet, Eye, X
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export default function Resumes() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const { user: currentUser } = useAuth()
  const [candidates, setCandidates] = useState([])
  const [jobs, setJobs] = useState([])
  const [allJobs, setAllJobs] = useState([]) // Store all jobs for filter
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedJobForUpload, setSelectedJobForUpload] = useState('')
  const [selectedJobForFilter, setSelectedJobForFilter] = useState('')
  const [jobFilter, setJobFilter] = useState([])
  const [scoreFilter, setScoreFilter] = useState([])
  const [statusFilter, setStatusFilter] = useState([])
  const [uploadType, setUploadType] = useState('single')
  const [error, setError] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [editingCandidate, setEditingCandidate] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '' })
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [candidateJob, setCandidateJob] = useState(null)
  const [minPassingScore, setMinPassingScore] = useState(60)
  const [jobScores, setJobScores] = useState({})
  const [syncing, setSyncing] = useState(false)
  const [viewingResume, setViewingResume] = useState(null)
  const [resumeSummary, setResumeSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({ show: false, current: 0, total: 0, status: 'uploading' })
  const [selectedCandidates, setSelectedCandidates] = useState([])
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [emailModal, setEmailModal] = useState({ show: false, type: '', subject: '', message: '' })
  const [sending, setSending] = useState(false)

  // Load job-specific minimum passing scores
  useEffect(() => {
    const fetchJobScores = async () => {
      try {
        const jobsData = await api.getJobs()
        const scores = {}
        jobsData.forEach(job => {
          scores[job.id] = job.min_passing_score || 60
        })
        setJobScores(scores)
      } catch (error) {
        console.error('Failed to fetch job scores:', error)
      }
    }
    fetchJobScores()
    
    // Refresh job scores every 5 seconds to catch updates
    const interval = setInterval(fetchJobScores, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchCandidates = useCallback(async () => {
    try {
      const data = await api.getCandidates({ search, client: selectedClient })
      let filteredData = (data || []).filter(c => c.stage !== 'APPLIED')
      
      if (jobFilter.length > 0) {
        filteredData = filteredData.filter(c => jobFilter.includes(c.job_id?.toString()))
      }
      
      if (scoreFilter.length > 0) {
        filteredData = filteredData.filter(c => {
          const score = c.resume_score || 0
          return scoreFilter.some(range => {
            if (range === '0-20') return score >= 0 && score <= 20
            if (range === '21-40') return score >= 21 && score <= 40
            if (range === '41-60') return score >= 41 && score <= 60
            if (range === '61-80') return score >= 61 && score <= 80
            if (range === '81-100') return score >= 81 && score <= 100
            return false
          })
        })
      }
      
      if (statusFilter.length > 0) {
        filteredData = filteredData.filter(c => statusFilter.includes(c.stage))
      }
      
      setCandidates(filteredData)
    } catch (error) {
      console.error('Failed to fetch candidates:', error)
      setCandidates([])
    }
  }, [search, selectedClient, jobFilter, scoreFilter, statusFilter])

  useEffect(() => {
    const fetchData = async () => {
      try {
        console.log('Fetching candidates and jobs...')
        const [candidatesData, jobsData, usersData] = await Promise.all([
          api.getCandidates(),
          api.getJobs(),
          api.getPublicUsers()
        ])
        console.log('Jobs data received:', jobsData)
        console.log('Jobs count:', jobsData?.length)
        setCandidates(candidatesData || [])
        setAllJobs(jobsData || [])  // Store all jobs
        const activeJobs = (jobsData || []).filter(job => job.is_active)
        console.log('Active jobs:', activeJobs)
        setJobs(activeJobs)  // Only active jobs for uploader
        setUsers(usersData || [])
      } catch (error) {
        console.error('Failed to fetch data:', error)
        console.error('Error details:', error.message, error.stack)
        setCandidates([])
        setJobs([])
        setAllJobs([])
        setUsers([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  useEffect(() => {
    const debounce = setTimeout(fetchCandidates, 300)
    return () => clearTimeout(debounce)
  }, [search, fetchCandidates])

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
    
    // Show progress for bulk uploads
    if (files.length > 1 || uploadType === 'zip') {
      setUploadProgress({ show: true, current: 0, total: files.length, status: 'uploading' })
    }
    
    // Get threshold from selected job's min_passing_score
    const jobId = selectedJobForUpload ? parseInt(selectedJobForUpload) : null
    const threshold = jobId ? (jobScores[jobId] || 60) : 60
    
    console.log('Starting upload with:', {
      filesCount: files.length,
      selectedJobForUpload,
      jobId,
      uploadType,
      threshold
    })
    
    try {
      
      if (uploadType === 'zip') {
        console.log('ZIP file upload')
        const result = await api.zipUploadResumes(files[0], jobId, threshold)
        console.log('ZIP upload result:', result)
        const successCount = result.results?.filter(r => r.status === 'success').length || 0
        setUploadProgress({ show: true, current: successCount, total: result.results?.length || 0, status: 'completed' })
      } else if (files.length === 1) {
        console.log('Single file upload')
        const result = await api.uploadResume(files[0], jobId, threshold)
        console.log('Upload result:', result)
      } else {
        console.log('Bulk file upload')
        const result = await api.bulkUploadResumes(files, jobId, threshold)
        console.log('Bulk upload result:', result)
        const successCount = result.results?.filter(r => r.status === 'success').length || 0
        setUploadProgress({ show: true, current: successCount, total: files.length, status: 'completed' })
      }
      
      await fetchCandidates()
      
      if (files.length === 1 && uploadType !== 'zip') {
        alert('Resume analyzed successfully!')
      }
    } catch (error) {
      console.error('Upload failed:', error)
      setError(`Upload failed: ${error.message}`)
      setUploadProgress({ show: false, current: 0, total: 0, status: 'error' })
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



  const handleOpenEmailModal = (type) => {
    let subject = ''
    let message = ''
    
    if (type === 'invitation') {
      subject = 'Interview Invitation - You have been shortlisted!'
      message = `Dear ${selectedCandidate.name},\n\nCongratulations! You have been shortlisted for the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nPlease select a convenient time slot for your interview by replying to this email.\n\nBest regards,\nRecruitment Team`
    } else if (type === 'reschedule') {
      subject = 'Interview Reschedule Request'
      message = `Dear ${selectedCandidate.name},\n\nWe need to reschedule your interview for the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nPlease reply with your available time slots and we will confirm a new interview time.\n\nWe apologize for any inconvenience.\n\nBest regards,\nRecruitment Team`
    } else if (type === 'rejection') {
      subject = 'Application Status Update'
      message = `Dear ${selectedCandidate.name},\n\nThank you for your interest in the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nAfter careful consideration, we regret to inform you that we will not be moving forward with your application at this time.\n\nWe appreciate the time you invested in the application process and wish you the best in your job search.\n\nBest regards,\nRecruitment Team`
    }
    
    setEmailModal({ show: true, type, subject, message })
  }

  const handleSendEmail = async () => {
    setSending(true)
    try {
      const stageMap = {
        invitation: 'INTERVIEW_SCHEDULED',
        reschedule: 'INTERVIEW_RESCHEDULED',
        rejection: 'REJECTED'
      }
      
      const emailTypeMap = {
        invitation: 'interview_invitation',
        reschedule: 'interview_reschedule',
        rejection: 'rejection'
      }
      
      await api.updateCandidateStage(selectedCandidate.id, stageMap[emailModal.type])
      await fetchCandidates()
      
      const result = await api.sendEmail(
        selectedCandidate.id,
        emailTypeMap[emailModal.type],
        emailModal.subject,
        emailModal.message
      )
      
      if (result.success) {
        alert(`Email sent successfully to ${selectedCandidate.email}`)
      } else {
        alert('Email sent but status updated')
      }
      
      setEmailModal({ show: false, type: '', subject: '', message: '' })
      handleCloseModal()
    } catch (error) {
      console.error('Error:', error)
      alert(`Failed: ${error.message}`)
    } finally {
      setSending(false)
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

    const url = api.getResumeFileUrl(candidate.id)
    const token = api.getToken()
    
    if (!token) {
      alert('Authentication required. Please log in again.')
      return
    }

    // Open file in new tab (backend handles Word to PDF conversion if LibreOffice is installed)
    window.open(`${url}?token=${encodeURIComponent(token)}`, '_blank')
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

      {/* Assignment Bar */}
      {selectedCandidates.length > 0 && currentUser?.role === 'admin' && (
        <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="font-medium text-lg">{selectedCandidates.length}</span>
                <span className="text-sm text-muted-foreground">candidate{selectedCandidates.length > 1 ? 's' : ''} selected</span>
                {selectedCandidates.length > 20 && (
                  <Badge variant="destructive" className="ml-2">Max 20 allowed</Badge>
                )}
              </div>
              <select
                className="flex h-10 rounded-lg border border-input bg-background px-3 py-2 text-sm min-w-[200px]"
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
              <Button
                onClick={async () => {
                  if (!selectedUser) {
                    alert('Please select a user to assign candidates')
                    return
                  }
                  if (selectedCandidates.length > 20) {
                    alert('You can only assign up to 20 candidates at a time')
                    return
                  }
                  setAssigning(true)
                  try {
                    const result = await api.bulkAssignCandidates(selectedCandidates, parseInt(selectedUser))
                    alert(result.message)
                    setSelectedCandidates([])
                    setSelectedUser('')
                    await fetchCandidates()
                  } catch (error) {
                    alert(`Assignment failed: ${error.message}`)
                  } finally {
                    setAssigning(false)
                  }
                }}
                disabled={assigning || !selectedUser || selectedCandidates.length > 20}
                className="bg-primary hover:bg-primary/90"
              >
                {assigning ? 'Assigning...' : 'Send to User'}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedCandidates([])
                  setSelectedUser('')
                }}
              >
                Clear Selection
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="w-32">
              <Filter className="h-4 w-4 mr-2" />
              Job
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {allJobs.map((job) => (
              <DropdownMenuCheckboxItem
                key={job.id}
                checked={jobFilter.includes(job.id.toString())}
                onCheckedChange={(checked) => {
                  setJobFilter(prev => 
                    checked ? [...prev, job.id.toString()] : prev.filter(id => id !== job.id.toString())
                  )
                }}
              >
                {job.company_name ? `${job.company_name} - ${job.title}` : job.title}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="w-32">
              <Filter className="h-4 w-4 mr-2" />
              Score
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            {['0-20', '21-40', '41-60', '61-80', '81-100'].map((range) => (
              <DropdownMenuCheckboxItem
                key={range}
                checked={scoreFilter.includes(range)}
                onCheckedChange={(checked) => {
                  setScoreFilter(prev => 
                    checked ? [...prev, range] : prev.filter(r => r !== range)
                  )
                }}
              >
                {range}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="w-32">
              <Filter className="h-4 w-4 mr-2" />
              Status
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('SHORTLISTED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev => 
                  checked ? [...prev, 'SHORTLISTED'] : prev.filter(s => s !== 'SHORTLISTED')
                )
              }}
            >
              Shortlisted
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('RESUME_REJECTED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev => 
                  checked ? [...prev, 'RESUME_REJECTED'] : prev.filter(s => s !== 'RESUME_REJECTED')
                )
              }}
            >
              Rejected
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {(jobFilter.length > 0 || scoreFilter.length > 0 || statusFilter.length > 0) && (
          <Button variant="ghost" size="icon" onClick={() => {
            setJobFilter([])
            setScoreFilter([])
            setStatusFilter([])
          }}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  {currentUser?.role === 'admin' && (
                    <th className="text-left p-4 font-medium w-12">
                      <input
                        type="checkbox"
                        checked={selectedCandidates.length === candidates.length && candidates.length > 0}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedCandidates(candidates.map(c => c.id))
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
                  <th className="text-left p-4 font-medium">Status</th>
                  <th className="text-left p-4 font-medium">Skills</th>
                  <th className="text-left p-4 font-medium">Date</th>
                  <th className="text-right p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.id} className="border-b hover:bg-muted/50 transition-colors cursor-pointer" onClick={() => handleViewCandidate(candidate)}>
                    {currentUser?.role === 'admin' && (
                      <td className="p-4" onClick={(e) => e.stopPropagation()}>
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
                          <span className={cn('font-semibold', 
                            candidate.resume_score >= (candidate.score_threshold || 60) ? 'text-green-600' : 'text-red-600'
                          )}>
                            {candidate.resume_score}
                          </span>
                          <Progress value={candidate.resume_score} className="w-16 h-2" />
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="p-4">
                      <Badge className={
                        candidate.stage === 'SHORTLISTED' ? 'bg-green-500' :
                        candidate.stage === 'RESUME_REJECTED' ? 'bg-red-500' :
                        candidate.stage === 'INTERVIEW_SCHEDULED' ? 'bg-blue-500' :
                        candidate.stage === 'INTERVIEW_RESCHEDULED' ? 'bg-yellow-500' :
                        candidate.stage === 'REJECTED' ? 'bg-red-600' :
                        'bg-gray-500'
                      }>
                        {candidate.stage === 'SHORTLISTED' ? 'Resume Shortlisted' :
                         candidate.stage === 'RESUME_REJECTED' ? 'Resume Rejected' :
                         candidate.stage === 'INTERVIEW_SCHEDULED' ? 'Interview Invited' :
                         candidate.stage === 'INTERVIEW_RESCHEDULED' ? 'Interview Rescheduled' :
                         candidate.stage === 'REJECTED' ? 'Rejected' :
                         'Pending'}
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
                            <Button variant="ghost" size="icon" onClick={() => handleEdit(candidate)} title="Edit">
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => handleDelete(candidate.id)} title="Delete">
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
                <h3 className="font-semibold mb-3">Pontis Insight</h3>
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

              {/* Action Buttons */}
              <div className="pt-4 border-t">
                <div className="flex gap-3">
                  <Button 
                    className="flex-1"
                    onClick={() => handleOpenEmailModal('invitation')}
                  >
                    Send Interview Invitation
                  </Button>
                  <Button 
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleOpenEmailModal('reschedule')}
                  >
                    Interview Reschedule
                  </Button>
                  <Button 
                    variant="destructive"
                    className="flex-1"
                    onClick={() => handleOpenEmailModal('rejection')}
                  >
                    Decline Invitation
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Email Customization Modal */}
      {emailModal.show && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" onClick={() => setEmailModal({ show: false, type: '', subject: '', message: '' })}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Customize Email</h2>
              <Button variant="ghost" size="icon" onClick={() => setEmailModal({ show: false, type: '', subject: '', message: '' })}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Subject</label>
                <Input
                  value={emailModal.subject}
                  onChange={(e) => setEmailModal({ ...emailModal, subject: e.target.value })}
                  placeholder="Email subject"
                />
              </div>
              
              <div>
                <label className="text-sm font-medium mb-2 block">Message</label>
                <textarea
                  value={emailModal.message}
                  onChange={(e) => setEmailModal({ ...emailModal, message: e.target.value })}
                  placeholder="Email message"
                  rows={12}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm resize-none"
                />
              </div>
              
              <div className="flex gap-3 pt-4">
                <Button 
                  className="flex-1" 
                  onClick={handleSendEmail}
                  disabled={sending}
                >
                  {sending ? 'Sending...' : 'Send Email'}
                </Button>
                <Button 
                  variant="outline" 
                  className="flex-1" 
                  onClick={() => setEmailModal({ show: false, type: '', subject: '', message: '' })}
                  disabled={sending}
                >
                  Cancel
                </Button>
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

      {/* Upload Progress Modal */}
      {uploadProgress.show && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">
              {uploadProgress.status === 'uploading' ? 'Uploading Resumes...' : 'Upload Complete'}
            </h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>Progress</span>
                  <span className="font-medium">{uploadProgress.current} / {uploadProgress.total}</span>
                </div>
                <Progress value={(uploadProgress.current / uploadProgress.total) * 100} className="h-2" />
              </div>
              {uploadProgress.status === 'completed' && (
                <div className="flex justify-end">
                  <Button onClick={() => setUploadProgress({ show: false, current: 0, total: 0, status: 'uploading' })}>
                    Close
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
