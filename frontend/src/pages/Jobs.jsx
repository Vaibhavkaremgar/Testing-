import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Plus, Briefcase, MapPin, Clock, Users, Edit, Trash2, Upload, FileText } from 'lucide-react'

export default function Jobs() {
  const [searchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const [jobs, setJobs] = useState([])
  const [allJobs, setAllJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [visibleCount, setVisibleCount] = useState(10)
  const SHOW_MORE_STEP = 10
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingJob, setEditingJob] = useState(null)
  const [clientNames, setClientNames] = useState([])
  const [showOtherCompany, setShowOtherCompany] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    job_id: '',
    company_name: '',
    department: '',
    location: '',
    employment_type: 'Full-time',
    experience_required: '',
    salary_range: '',
    vacancies: 1,
    min_passing_score: 60,
    description: '',
    requirements: '',
    responsibilities: '',
    skills: '',
    interview_questions: []
  })
  const [inputMethod, setInputMethod] = useState('manual')
  const [uploadedFile, setUploadedFile] = useState(null)
  const [extracting, setExtracting] = useState(false)
  const [currentQuestion, setCurrentQuestion] = useState('')

  const fetchJobs = async () => {
    try {
      const params = {}
      if (selectedClient) params.client = selectedClient
      const data = await api.getJobs(params)
      setAllJobs(data)
      setJobs(data)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchClientNames = async () => {
    try {
      const names = await api.getClientNames()
      setClientNames(names)
    } catch (error) {
      console.error('Failed to fetch client names:', error)
    }
  }

  useEffect(() => {
    fetchJobs()
    fetchClientNames()
  }, [selectedClient])

  useEffect(() => { setVisibleCount(10) }, [selectedClient])

  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log('Form submitted', formData)
    try {
      const jobData = {
        ...formData,
        company_name: formData.company_name || null,
        skills: formData.skills.split(',').map(s => s.trim()).filter(Boolean),
        interview_questions: formData.interview_questions
      }
      console.log('Sending job data:', jobData)
      
      if (editingJob) {
        await api.updateJob(editingJob.id, jobData)
      } else {
        await api.createJob(jobData)
      }
      
      console.log('Job created successfully')
      setDialogOpen(false)
      setEditingJob(null)
      setShowOtherCompany(false)
      setFormData({
        title: '', job_id: '', company_name: '', department: '', location: '', employment_type: 'Full-time',
        experience_required: '', salary_range: '', vacancies: 1, min_passing_score: 60, description: '', requirements: '', responsibilities: '', skills: '',
        interview_questions: []
      })
      await fetchJobs()
    } catch (error) {
      console.error('Failed to save job:', error)
      alert('Failed to create job: ' + (error.message || 'Unknown error'))
    }
  }

  const handleEdit = (job) => {
    setEditingJob(job)
    const isOther = job.company_name && !clientNames.includes(job.company_name)
    setShowOtherCompany(isOther)
    setFormData({
      title: job.title,
      job_id: job.job_id || '',
      company_name: isOther ? job.company_name : (job.company_name || ''),
      department: job.department || '',
      location: job.location || '',
      employment_type: job.employment_type || 'Full-time',
      experience_required: job.experience_required || '',
      salary_range: job.salary_range || '',
      vacancies: job.vacancies || 1,
      min_passing_score: job.min_passing_score || 60,
      description: job.description || '',
      requirements: job.requirements || '',
      responsibilities: job.responsibilities || '',
      skills: job.skills?.join(', ') || '',
      interview_questions: job.interview_questions || []
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (confirm('Are you sure you want to delete this job?')) {
      try {
        await api.deleteJob(id)
        await fetchJobs()
      } catch (error) {
        console.error('Failed to delete job:', error)
      }
    }
  }

  const handleToggleActive = async (job) => {
    try {
      await api.updateJob(job.id, { ...job, is_active: !job.is_active })
      await fetchJobs()
    } catch (error) {
      console.error('Failed to toggle job status:', error)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    setUploadedFile(file)
    setExtracting(true)
    
    try {
      const extractedData = await api.extractJobData(file)
      setFormData({
        ...formData,
        department: extractedData.department || '',
        location: extractedData.location || '',
        employment_type: extractedData.employment_type || 'Full-time',
        experience_required: extractedData.experience_required || '',
        salary_range: extractedData.salary_range || '',
        description: extractedData.description || '',
        requirements: extractedData.requirements || '',
        skills: extractedData.skills?.join(', ') || ''
      })
    } catch (error) {
      console.error('Failed to extract job data:', error)
      alert('Failed to extract data from file. Please try again or enter manually.')
    } finally {
      setExtracting(false)
    }
  }

  const resetForm = () => {
    setFormData({
      title: '', job_id: '', company_name: '', department: '', location: '', employment_type: 'Full-time',
      experience_required: '', salary_range: '', vacancies: 1, min_passing_score: 60, description: '', requirements: '', responsibilities: '', skills: '',
      interview_questions: []
    })
    setInputMethod('manual')
    setUploadedFile(null)
    setCurrentQuestion('')
    setShowOtherCompany(false)
  }

  const addQuestion = () => {
    if (!currentQuestion.trim()) return
    setFormData({
      ...formData,
      interview_questions: [...formData.interview_questions, { id: Date.now(), text: currentQuestion }]
    })
    setCurrentQuestion('')
  }

  const removeQuestion = (id) => {
    setFormData({
      ...formData,
      interview_questions: formData.interview_questions.filter(q => q.id !== id)
    })
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Job Descriptions</h1>
          <p className="text-muted-foreground">Manage open positions</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => {
              setEditingJob(null)
              resetForm()
            }}>
              <Plus className="h-4 w-4 mr-2" />
              Add Job
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingJob ? 'Edit Job' : 'Create New Job'}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              {/* Mandatory Fields - Always First */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Job Title *</label>
                  <Input
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Job ID *</label>
                  <Input
                    value={formData.job_id}
                    onChange={(e) => setFormData({ ...formData, job_id: e.target.value })}
                    placeholder="e.g., JOB-001"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Company Name</label>
                {!showOtherCompany ? (
                  <select
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    value={formData.company_name}
                    onChange={(e) => {
                      if (e.target.value === 'other') {
                        setShowOtherCompany(true)
                        setFormData({ ...formData, company_name: '' })
                      } else {
                        setFormData({ ...formData, company_name: e.target.value })
                      }
                    }}
                  >
                    <option value="">Select a company</option>
                    {clientNames.map((name) => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                    <option value="other">Other</option>
                  </select>
                ) : (
                  <div className="flex gap-2">
                    <Input
                      value={formData.company_name}
                      onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                      placeholder="Enter company name"
                      autoFocus
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setShowOtherCompany(false)
                        setFormData({ ...formData, company_name: '' })
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </div>

              {/* Input Method Selection */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Input Method</label>
                <select
                  className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={inputMethod}
                  onChange={(e) => setInputMethod(e.target.value)}
                >
                  <option value="manual">Enter Manually</option>
                  <option value="upload">Upload File</option>
                </select>
              </div>

              {/* File Upload Section */}
              {inputMethod === 'upload' && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Upload Job Description File</label>
                  <div className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-4 text-center">
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx,.txt"
                      onChange={handleFileUpload}
                      className="hidden"
                      id="job-file-upload"
                    />
                    <label htmlFor="job-file-upload" className="cursor-pointer">
                      <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">
                        {uploadedFile ? uploadedFile.name : 'Click to upload job description file'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Supports PDF, DOC, DOCX, TXT files
                      </p>
                    </label>
                    {extracting && (
                      <div className="flex items-center justify-center gap-2 mt-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                        <span className="text-sm">Extracting data...</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {/* Other Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Department</label>
                  <Input
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    disabled={inputMethod === 'upload'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Location</label>
                  <Input
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    disabled={inputMethod === 'upload'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Employment Type</label>
                  <select
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    value={formData.employment_type}
                    onChange={(e) => setFormData({ ...formData, employment_type: e.target.value })}
                    disabled={inputMethod === 'upload'}
                  >
                    <option>Full-time</option>
                    <option>Part-time</option>
                    <option>Contract</option>
                    <option>Internship</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Experience Required</label>
                  <Input
                    value={formData.experience_required}
                    onChange={(e) => setFormData({ ...formData, experience_required: e.target.value })}
                    placeholder="e.g., 3-5 years"
                    disabled={inputMethod === 'upload'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Salary Range</label>
                  <Input
                    value={formData.salary_range}
                    onChange={(e) => setFormData({ ...formData, salary_range: e.target.value })}
                    placeholder="e.g., $100k - $150k"
                    disabled={inputMethod === 'upload'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Vacancies</label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.vacancies}
                    onChange={(e) => setFormData({ ...formData, vacancies: parseInt(e.target.value) || 1 })}
                    placeholder="Number of positions"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Minimum Passing Score</label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.min_passing_score}
                    onChange={(e) => setFormData({ ...formData, min_passing_score: parseInt(e.target.value) || 60 })}
                    placeholder="Resume score threshold"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <textarea
                  className="flex min-h-[100px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  disabled={inputMethod === 'upload'}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Requirements</label>
                <textarea
                  className="flex min-h-[100px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  value={formData.requirements}
                  onChange={(e) => setFormData({ ...formData, requirements: e.target.value })}
                  disabled={inputMethod === 'upload'}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Skills (comma-separated)</label>
                <Input
                  value={formData.skills}
                  onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                  placeholder="Python, React, AWS"
                  disabled={inputMethod === 'upload'}
                />
              </div>

              {/* Interview Questions Section */}
              <div className="space-y-3 border-t pt-4">
                <label className="text-sm font-medium">Async Interview Questions (Optional)</label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter question"
                    value={currentQuestion}
                    onChange={(e) => setCurrentQuestion(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addQuestion())}
                  />
                  <Button type="button" onClick={addQuestion}>
                    Add
                  </Button>
                </div>

                {formData.interview_questions.length > 0 && (
                  <div className="space-y-2">
                    {formData.interview_questions.map((q, idx) => (
                      <div key={q.id} className="flex items-center gap-2 p-2 bg-muted rounded">
                        <span className="flex-1 text-sm">{idx + 1}. {q.text}</span>
                        <Button type="button" variant="ghost" size="sm" onClick={() => removeQuestion(q.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">
                  {editingJob ? 'Update' : 'Create'} Job
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {jobs.slice(0, visibleCount).map((job) => (
          <Card key={job.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="text-base">{job.title}</CardTitle>
                  {job.job_id && (
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">ID: {job.job_id}</p>
                  )}
                  {job.company_name && (
                    <p className="text-sm font-medium text-primary mt-1">{job.company_name}</p>
                  )}
                  <p className="text-sm text-muted-foreground">{job.department}</p>
                </div>
                <Badge variant={job.is_active ? 'success' : 'secondary'}>
                  {job.is_active ? 'Active' : 'Closed'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                {job.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    {job.location}
                  </span>
                )}
                {job.employment_type && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {job.employment_type}
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-1 text-sm">
                <Users className="h-4 w-4 text-muted-foreground" />
                <span>{job.candidate_count || 0} candidates</span>
                {job.vacancies && (
                  <span className="text-muted-foreground">• {job.vacancies} positions</span>
                )}
              </div>

              {job.skills?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {job.skills.slice(0, 3).map((skill) => (
                    <Badge key={skill} variant="secondary" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                  {job.skills.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{job.skills.length - 3}
                    </Badge>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t">
                <div className="flex items-center gap-2">
                  <Switch 
                    checked={job.is_active} 
                    onCheckedChange={() => handleToggleActive(job)}
                    className="scale-75"
                  />
                  <span className="text-xs text-muted-foreground">
                    {job.is_active ? 'Active' : 'Closed'}
                  </span>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => handleEdit(job)}>
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(job.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {visibleCount < jobs.length && (
        <div className="flex justify-center pt-2">
          <Button variant="outline" onClick={() => setVisibleCount(v => v + SHOW_MORE_STEP)}>
            Show More ({jobs.length - visibleCount} remaining)
          </Button>
        </div>
      )}
    </div>
  )
}
