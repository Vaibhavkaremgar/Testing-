import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import DateRangeFilter from '@/components/DateRangeFilter'
import ExpandableList from '@/components/ExpandableList'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { cn, formatDate, getDateRangePreset, getScoreColor } from '@/lib/utils'
import {
  Upload, FileText, Search, Filter, MoreHorizontal, Edit, CheckCircle, Clock, AlertCircle, Trash2, Sheet, Eye, X, ChevronDown
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const DEFAULT_LIST_LIMIT = 100

const ResumeStatusBadge = React.memo(function ResumeStatusBadge({ candidate }) {
  const status = getResumeDisplayStatus(candidate)
  return (
    <Badge className={status.badgeClass}>
      {status.label}
    </Badge>
  )
})

function getResumeDisplayStatus(candidate) {
  const normalizedStatus = String(candidate?.status || '').toLowerCase()
  const stage = candidate?.display_stage || candidate?.stage
  const resumeScore = candidate?.resume_score
  const threshold = candidate?.score_threshold || 60

  if (stage === 'SELECTED') {
    return { key: 'RESUME_SHORTLISTED', label: 'Selected', badgeClass: 'bg-emerald-600' }
  }

  if (stage === 'REJECTED') {
    return { key: 'RESUME_REJECTED', label: 'Rejected', badgeClass: 'bg-red-500' }
  }

  if (stage === 'INTERVIEWED') {
    return { key: 'INTERVIEWED', label: 'Interviewed', badgeClass: 'bg-violet-500' }
  }

  if (stage === 'INTERVIEW_SCHEDULED') {
    return { key: 'INTERVIEW_SCHEDULED', label: 'Interview Scheduled', badgeClass: 'bg-blue-500' }
  }

  if (typeof resumeScore === 'number' && resumeScore <= (threshold - 10)) {
    return { key: 'RESUME_REJECTED', label: 'Rejected', badgeClass: 'bg-red-500' }
  }

  if (stage === 'RESUME_REJECTED') {
    return { key: 'RESUME_REJECTED', label: 'Rejected', badgeClass: 'bg-red-500' }
  }

  if (stage === 'REVIEW') {
    return { key: 'IN_REVIEW', label: 'In Review', badgeClass: 'bg-amber-500' }
  }

  if (stage === 'INTERVIEW_RESCHEDULED' || candidate?.is_rescheduled === true || normalizedStatus === 'rescheduled') {
    return { key: 'INTERVIEW_RESCHEDULED', label: 'Interview Rescheduled', badgeClass: 'bg-yellow-500' }
  }

  if ([
    'SHORTLISTED',
    'NO_SHOW',
  ].includes(stage)) {
    return { key: 'RESUME_SHORTLISTED', label: 'Shortlisted', badgeClass: 'bg-green-500' }
  }

  return { key: 'IN_REVIEW', label: 'In Review', badgeClass: 'bg-amber-500' }
}

function formatCandidateDisplayName(name) {
  if (!name) return 'Unknown Candidate'

  const cleaned = name
    .replace(/[_-]+/g, ' ')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\[[^\]]*\]/g, ' ')
    .replace(/\b\d+\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return cleaned || 'Unknown Candidate'
}

function formatSummaryAsParagraph(summary) {
  const toConciseSummary = (value) => {
    const cleanedValue = String(value || '')
      .replace(/^candidate summary[:.\s-]*/i, '')
      .replace(/\s+/g, ' ')
      .trim()

    if (!cleanedValue) return ''

    const sectionMatches = Array.from(
      cleanedValue.matchAll(/(Experience Match|Skill Match|Domain Match|Strengths|Gaps \(if any\)|Overall Fit):\s*([^:]+?)(?=(Experience Match|Skill Match|Domain Match|Strengths|Gaps \(if any\)|Overall Fit):|$)/gi)
    )

    if (!sectionMatches.length) {
      return cleanedValue
    }

    const sections = Object.fromEntries(
      sectionMatches.map((match) => [
        match[1].toLowerCase(),
        String(match[2] || '').trim().replace(/[.]+$/, ''),
      ])
    )

    return [
      sections['experience match'],
      sections['skill match'],
      sections['strengths'],
      sections['overall fit'],
    ]
      .filter(Boolean)
      .slice(0, 4)
      .map((sentence) => `${sentence}.`)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()
  }

  if (Array.isArray(summary)) {
    return summary
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .map((item) => item.replace(/[.]+$/, ''))
      .join('. ') + (summary.length ? '.' : '')
  }

  const normalized = String(summary || '')
    .split('\n')
    .map((line) => line.replace(/^\s*[-*•]\s*/, '').trim())
    .filter(Boolean)
    .map((line) => line.replace(/[.]+$/, ''))
    .join('. ')
    .replace(/\s+/g, ' ')
    .trim()

  return normalized ? toConciseSummary(`${normalized}.`.replace(/\.\./g, '.')) : ''
}

function normalizeCandidateSkills(skills) {
  if (Array.isArray(skills)) {
    return skills.filter(Boolean)
  }

  if (typeof skills === 'string') {
    return skills
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

  return []
}

function normalizeCandidateScore(candidate) {
  const scoreValue = candidate?.resume_score ?? candidate?.score ?? candidate?.match_score
  if (scoreValue === null || scoreValue === undefined || scoreValue === '') {
    return null
  }

  const parsedScore = Number(scoreValue)
  return Number.isFinite(parsedScore) ? parsedScore : null
}

function normalizeResumeCandidate(candidate, jobsById = {}) {
  const resolvedJobId = candidate?.job_id ?? candidate?.job?.id ?? null
  const jobDetails = resolvedJobId ? jobsById[resolvedJobId] || jobsById[String(resolvedJobId)] : null
  const normalizedSkills = normalizeCandidateSkills(
    candidate?.skills ?? candidate?.skill_set ?? candidate?.job?.skills
  )
  const normalizedScore = normalizeCandidateScore(candidate)
  const normalizedStatus = String(candidate?.status || '').toLowerCase()
  const isRescheduled = candidate?.is_rescheduled === true || normalizedStatus === 'rescheduled'
  const normalizedId = candidate?.id ? String(candidate.id) : null

  return {
    ...candidate,
    job_id: resolvedJobId,
    job_title: candidate?.job_title || candidate?.job?.title || jobDetails?.title || '',
    resume_score: normalizedScore,
    skills: normalizedSkills,
    display_stage: isRescheduled ? 'INTERVIEW_RESCHEDULED' : (candidate?.display_stage || candidate?.stage),
    merged_candidate_ids: normalizedId ? [normalizedId] : [],
  }
}

function isOrphanedResumeCandidate(candidate) {
  const hasJobContext = Boolean(candidate?.job_id || candidate?.job_title)
  const hasResumeContent = Boolean(candidate?.resume_file_path || candidate?.resume_text)
  const hasResumeScore = candidate?.resume_score !== null && candidate?.resume_score !== undefined
  const hasProfileDetails = Boolean(
    candidate?.current_role ||
    candidate?.current_company ||
    candidate?.experience_years !== null && candidate?.experience_years !== undefined ||
    candidate?.skills?.length
  )

  return !hasJobContext && !hasResumeContent && !hasResumeScore && !hasProfileDetails
}

function buildResumeCandidateDedupKey(candidate) {
  const normalizedId = String(candidate?.id || '').trim()
  const normalizedEmail = String(candidate?.email || '').trim().toLowerCase()
  const normalizedName = String(candidate?.name || '').trim().toLowerCase()
  const normalizedJobId = candidate?.job_id ? String(candidate.job_id) : ''
  const normalizedCreatedAt = candidate?.created_at ? String(candidate.created_at) : ''

  // Preserve distinct candidate records from the API instead of collapsing
  // separate uploads that happen to share the same parsed email or job.
  if (normalizedId) {
    return `id:${normalizedId}`
  }

  if (normalizedEmail && normalizedJobId) {
    return `email:${normalizedEmail}:job:${normalizedJobId}`
  }

  if (normalizedEmail) {
    return `email:${normalizedEmail}`
  }

  if (normalizedName && normalizedCreatedAt) {
    return `name:${normalizedName}:created:${normalizedCreatedAt}`
  }

  if (normalizedName && normalizedJobId) {
    return `name:${normalizedName}:job:${normalizedJobId}`
  }

  return `id:${candidate?.id || Math.random()}`
}

function getResumeCandidatePreferenceScore(candidate) {
  const stage = candidate?.display_stage || candidate?.stage || ''
  const stagePriority = {
    NO_SHOW: 70,
    INTERVIEWED: 60,
    INTERVIEW_RESCHEDULED: 50,
    INTERVIEW_SCHEDULED: 40,
    SELECTED: 30,
    REJECTED: 20,
    SHORTLISTED: 10,
    REVIEW: 5,
    RESUME_REJECTED: 0,
  }

  let score = stagePriority[stage] || 0

  if (candidate?.email) score += 5
  if (candidate?.job_id) score += 5
  if (candidate?.job_title) score += 4
  if (candidate?.current_role) score += 3
  if (candidate?.skills?.length) score += 2
  if (candidate?.resume_score !== null && candidate?.resume_score !== undefined) score += 2

  return score
}

function getResumeCandidateCompletenessScore(candidate) {
  let score = 0

  if (candidate?.email) score += 6
  if (candidate?.job_id) score += 6
  if (candidate?.job_title) score += 5
  if (candidate?.resume_file_path) score += 4
  if (candidate?.resume_text) score += 4
  if (candidate?.resume_score !== null && candidate?.resume_score !== undefined) score += 3
  if (candidate?.current_role) score += 3
  if (candidate?.current_company) score += 3
  if (candidate?.skills?.length) score += 2

  return score
}

function getResumeCandidateEventDateKey(candidate) {
  const rawDate =
    candidate?.stage_entered_at
    || candidate?.stage_updated_at
    || candidate?.applied_at
    || candidate?.created_at

  if (!rawDate) {
    return ''
  }

  const parsedDate = new Date(rawDate)
  if (Number.isNaN(parsedDate.getTime())) {
    return ''
  }

  return parsedDate.toISOString().slice(0, 10)
}

function isInterviewOwnedResumeStage(candidate) {
  const stage = candidate?.display_stage || candidate?.stage || ''
  return ['INTERVIEW_SCHEDULED', 'INTERVIEW_RESCHEDULED', 'INTERVIEWED', 'NO_SHOW'].includes(stage)
}

function isLikelyInterviewPlaceholderCandidate(candidate) {
  if (!isInterviewOwnedResumeStage(candidate)) {
    return false
  }

  return getResumeCandidateCompletenessScore(candidate) <= 4
}

function buildInterviewPlaceholderMergeKey(candidate) {
  const normalizedName = String(candidate?.name || '').trim().toLowerCase()
  const eventDateKey = getResumeCandidateEventDateKey(candidate)

  if (!normalizedName || !eventDateKey) {
    return ''
  }

  return `${normalizedName}:${eventDateKey}`
}

function buildInterviewOwnedResumeMergeKey(candidate) {
  if (!isInterviewOwnedResumeStage(candidate)) {
    return ''
  }

  const normalizedEmail = String(candidate?.email || '').trim().toLowerCase()
  const normalizedJobId = candidate?.job_id ? String(candidate.job_id).trim() : ''
  const normalizedName = String(candidate?.name || '').trim().toLowerCase()

  if (normalizedEmail && normalizedJobId) {
    return `email:${normalizedEmail}:job:${normalizedJobId}`
  }

  // Keep this fallback narrow to avoid collapsing unrelated candidates:
  // only interview-owned duplicates with the same job and name are merged.
  if (normalizedName && normalizedJobId) {
    return `name:${normalizedName}:job:${normalizedJobId}`
  }

  return ''
}

function mergeResumeCandidateRecords(primaryCandidate, secondaryCandidate) {
  const primaryStageScore = getResumeCandidatePreferenceScore(primaryCandidate)
  const secondaryStageScore = getResumeCandidatePreferenceScore(secondaryCandidate)
  const mergedCandidateIds = Array.from(new Set([
    ...(Array.isArray(primaryCandidate?.merged_candidate_ids) ? primaryCandidate.merged_candidate_ids : []),
    ...(Array.isArray(secondaryCandidate?.merged_candidate_ids) ? secondaryCandidate.merged_candidate_ids : []),
  ].filter(Boolean)))

  const mergedCandidate = {
    ...secondaryCandidate,
    ...primaryCandidate,
    merged_candidate_ids: mergedCandidateIds,
  }

  if (secondaryStageScore > primaryStageScore) {
    mergedCandidate.stage = secondaryCandidate.stage || mergedCandidate.stage
    mergedCandidate.display_stage = secondaryCandidate.display_stage || mergedCandidate.display_stage
    mergedCandidate.status = secondaryCandidate.status || mergedCandidate.status
    mergedCandidate.stage_updated_at = secondaryCandidate.stage_updated_at || mergedCandidate.stage_updated_at
    mergedCandidate.stage_entered_at = secondaryCandidate.stage_entered_at || mergedCandidate.stage_entered_at
    mergedCandidate.applied_at = secondaryCandidate.applied_at || mergedCandidate.applied_at
    mergedCandidate.created_at = secondaryCandidate.created_at || mergedCandidate.created_at
  }

  return mergedCandidate
}

function dedupeResumeCandidates(candidates) {
  const deduped = new Map()

  candidates.forEach((candidate) => {
    const key = buildResumeCandidateDedupKey(candidate)
    const existing = deduped.get(key)

    if (!existing || getResumeCandidatePreferenceScore(candidate) > getResumeCandidatePreferenceScore(existing)) {
      deduped.set(key, candidate)
    }
  })

  const normalizedCandidates = Array.from(deduped.values())
  const preferredCandidateIndexByInterviewKey = new Map()

  normalizedCandidates.forEach((candidate, index) => {
    if (isLikelyInterviewPlaceholderCandidate(candidate)) {
      return
    }

    const mergeKey = buildInterviewPlaceholderMergeKey(candidate)
    if (!mergeKey) {
      return
    }

    const existingIndex = preferredCandidateIndexByInterviewKey.get(mergeKey)
    if (existingIndex === undefined) {
      preferredCandidateIndexByInterviewKey.set(mergeKey, index)
      return
    }

    const existingCandidate = normalizedCandidates[existingIndex]
    if (getResumeCandidateCompletenessScore(candidate) > getResumeCandidateCompletenessScore(existingCandidate)) {
      preferredCandidateIndexByInterviewKey.set(mergeKey, index)
    }
  })

  const consumedIndexes = new Set()
  const preferredCandidateIndexByInterviewOwnedKey = new Map()

  normalizedCandidates.forEach((candidate, index) => {
    const mergeKey = buildInterviewOwnedResumeMergeKey(candidate)
    if (!mergeKey) {
      return
    }

    const existingIndex = preferredCandidateIndexByInterviewOwnedKey.get(mergeKey)
    if (existingIndex === undefined) {
      preferredCandidateIndexByInterviewOwnedKey.set(mergeKey, index)
      return
    }

    const existingCandidate = normalizedCandidates[existingIndex]
    const candidateScore = getResumeCandidatePreferenceScore(candidate) + getResumeCandidateCompletenessScore(candidate)
    const existingScore = getResumeCandidatePreferenceScore(existingCandidate) + getResumeCandidateCompletenessScore(existingCandidate)

    if (candidateScore > existingScore) {
      preferredCandidateIndexByInterviewOwnedKey.set(mergeKey, index)
    }
  })

  normalizedCandidates.forEach((candidate, index) => {
    const mergeKey = buildInterviewOwnedResumeMergeKey(candidate)
    if (!mergeKey) {
      return
    }

    const preferredCandidateIndex = preferredCandidateIndexByInterviewOwnedKey.get(mergeKey)
    if (preferredCandidateIndex === undefined || preferredCandidateIndex === index) {
      return
    }

    const preferredCandidate = normalizedCandidates[preferredCandidateIndex]
    const shouldMergeInterviewOwnedRecords =
      isLikelyInterviewPlaceholderCandidate(candidate) ||
      isLikelyInterviewPlaceholderCandidate(preferredCandidate)

    if (!shouldMergeInterviewOwnedRecords) {
      return
    }

    normalizedCandidates[preferredCandidateIndex] = mergeResumeCandidateRecords(
      preferredCandidate,
      candidate,
    )
    consumedIndexes.add(index)
  })

  normalizedCandidates.forEach((candidate, index) => {
    if (!isLikelyInterviewPlaceholderCandidate(candidate)) {
      return
    }

    const mergeKey = buildInterviewPlaceholderMergeKey(candidate)
    if (!mergeKey) {
      return
    }

    const preferredCandidateIndex = preferredCandidateIndexByInterviewKey.get(mergeKey)
    if (preferredCandidateIndex === undefined || preferredCandidateIndex === index) {
      return
    }

    normalizedCandidates[preferredCandidateIndex] = mergeResumeCandidateRecords(
      normalizedCandidates[preferredCandidateIndex],
      candidate,
    )
    consumedIndexes.add(index)
  })

  return normalizedCandidates.filter((_, index) => !consumedIndexes.has(index))
}

export default function Resumes() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedClient = searchParams.get('client')
  const selectedGlobalJobId = searchParams.get('job_id') || ''
  const selectedCandidateId = searchParams.get('candidate_id') || ''
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const canDeleteResumes = currentUser?.role === 'admin'
  const [uploading, setUploading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedJobForUpload, setSelectedJobForUpload] = useState('')
  const [selectedJobForFilter, setSelectedJobForFilter] = useState('')
  const [dateRange, setDateRange] = useState(() => getDateRangePreset('all_time'))
  const [jobFilter, setJobFilter] = useState([])
  const [scoreFilter, setScoreFilter] = useState([])
  const [statusFilter, setStatusFilter] = useState([])
  const [uploadType, setUploadType] = useState('single')
  const [error, setError] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [editingCandidate, setEditingCandidate] = useState(null)
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    phone: '',
    experience_years: '',
    skills: '',
    education: '',
    internal_notes: '',
    current_company: '',
    current_role: '',
    location: '',
    linkedin_url: '',
    summary: '',
    predefined_questions: '',
  })
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [candidateJob, setCandidateJob] = useState(null)
  const [minPassingScore, setMinPassingScore] = useState(60)
  const [syncing, setSyncing] = useState(false)
  const [viewingResume, setViewingResume] = useState(null)
  const [resumeSummary, setResumeSummary] = useState(null)
  const [resumeSummaryCandidateId, setResumeSummaryCandidateId] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({ show: false, current: 0, total: 0, status: 'uploading' })
  const [selectedCandidates, setSelectedCandidates] = useState([])
  const [selectedUser, setSelectedUser] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [deletingCandidates, setDeletingCandidates] = useState(false)
  const [emailModal, setEmailModal] = useState({ show: false, type: '', subject: '', message: '' })
  const [sending, setSending] = useState(false)
  const [isEditingEmail, setIsEditingEmail] = useState(false)
  const [deleteCandidateModal, setDeleteCandidateModal] = useState({ open: false, candidates: [] })
  const uploadInFlightRef = useRef(false)
  const selectedCandidateStatus = selectedCandidate ? getResumeDisplayStatus(selectedCandidate) : null

  const {
    data: dashboardData,
    isLoading: loading,
    refetch: refetchResumeData,
  } = useQuery({
    queryKey: ['dashboard-data', 'resumes', selectedClient, selectedGlobalJobId, dateRange.from, dateRange.to],
    queryFn: () => api.getDashboardData({
      client: selectedClient || undefined,
      from_date: dateRange.from || undefined,
      to_date: dateRange.to || undefined,
      job_limit: DEFAULT_LIST_LIMIT,
      user_limit: DEFAULT_LIST_LIMIT,
    }),
  })

  // Keep this page self-contained: it now hydrates from a single cached endpoint.
  const allJobs = useMemo(() => dashboardData?.jobs || [], [dashboardData])
  const jobs = useMemo(() => allJobs.filter((job) => job.is_active), [allJobs])
  const uploadJobs = useMemo(() => {
    const seenLabels = new Set()

    return jobs.filter((job) => {
      const label = (job.company_name ? `${job.company_name} - ${job.title}` : job.title || '').trim().toLowerCase()
      if (!label || seenLabels.has(label)) {
        return false
      }

      seenLabels.add(label)
      return true
    })
  }, [jobs])
  const users = useMemo(() => dashboardData?.users || [], [dashboardData])
  const jobsById = useMemo(() => Object.fromEntries(allJobs.map((job) => [job.id, job])), [allJobs])
  const jobScores = useMemo(
    () => Object.fromEntries((dashboardData?.scores || []).map((score) => [score.job_id, score.min_passing_score || 60])),
    [dashboardData],
  )
  const candidates = useMemo(() => {
    let filteredData = dedupeResumeCandidates(
      (dashboardData?.candidates || []).map((candidate) => normalizeResumeCandidate(candidate, jobsById))
    )
      .filter((candidate) => !isOrphanedResumeCandidate(candidate))

    if (selectedGlobalJobId) {
      filteredData = filteredData.filter((candidate) => candidate.job_id?.toString() === selectedGlobalJobId)
    } else if (jobFilter.length > 0) {
      filteredData = filteredData.filter((candidate) => jobFilter.includes(candidate.job_id?.toString()))
    }

    if (search.trim()) {
      const searchValue = search.trim().toLowerCase()
      filteredData = filteredData.filter((candidate) =>
        [candidate.name, candidate.email, candidate.job_title]
          .filter(Boolean)
          .some((value) => value.toLowerCase().includes(searchValue)),
      )
    }

    if (scoreFilter.length > 0) {
      filteredData = filteredData.filter((candidate) => {
        const score = candidate.resume_score || 0
        return scoreFilter.some((range) => {
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
      filteredData = filteredData.filter((candidate) => statusFilter.includes(getResumeDisplayStatus(candidate).key))
    }

    return filteredData
  }, [dashboardData?.candidates, jobFilter, jobsById, scoreFilter, search, selectedGlobalJobId, statusFilter])
  useEffect(() => {
    if (selectedGlobalJobId) {
      setSelectedJobForFilter(selectedGlobalJobId)
      setJobFilter([selectedGlobalJobId])
      return
    }

    setSelectedJobForFilter('')
    setJobFilter([])
  }, [selectedGlobalJobId])

  useEffect(() => {
    if (!selectedCandidateId || candidates.length === 0 || selectedCandidate?.id === selectedCandidateId) {
      return
    }

    const matchedCandidate = candidates.find((candidate) => String(candidate.id) === selectedCandidateId)
    if (matchedCandidate) {
      handleViewCandidate(matchedCandidate)
    }
  }, [candidates, selectedCandidate?.id, selectedCandidateId])

  const fetchCandidates = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['dashboard-data', 'resumes'] })
    await queryClient.refetchQueries({ queryKey: ['dashboard-data', 'resumes'], type: 'active' })
  }, [queryClient])

  // Refresh list whenever an upload reaches 'completed'
  useEffect(() => {
    if (uploadProgress.status === 'completed') {
      fetchCandidates()
    }
  }, [uploadProgress.status, fetchCandidates])

  useEffect(() => {
    if (!uploadProgress.show || !uploadProgress.uploadId || uploadProgress.status === 'completed' || uploadProgress.status === 'error') {
      return
    }

    const intervalId = setInterval(async () => {
      try {
        const progress = await api.getUploadProgress(uploadProgress.uploadId)
        setUploadProgress(prev => ({
          ...prev,
          current: progress.current ?? prev.current,
          total: progress.total ?? prev.total,
          status: progress.status || prev.status,
          message: progress.message || prev.message,
        }))
        if (progress.status === 'completed' || progress.status === 'error') {
          clearInterval(intervalId)
        }
      } catch (error) {
        console.error('Failed to fetch upload progress:', error)
      }
    }, 1500)

    return () => clearInterval(intervalId)
  }, [uploadProgress.show, uploadProgress.uploadId, uploadProgress.status])

  useEffect(() => {
    setSelectedCandidates((prev) => prev.filter((candidateId) => candidates.some((candidate) => candidate.id === candidateId)))
  }, [candidates])

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
    if (uploadInFlightRef.current) {
      return
    }
    if (selectedFiles.length === 0) {
      setError('Please select files to upload')
      return
    }
    await handleUpload(selectedFiles)
    setSelectedFiles([]) // Clear selected files after upload
  }

  const handleUpload = async (files) => {
    if (uploadInFlightRef.current) {
      return
    }
    uploadInFlightRef.current = true
    setUploading(true)
    setError('')
    
    // Show progress for bulk uploads
    if (files.length > 1 || uploadType === 'zip') {
      setUploadProgress({ show: true, current: 0, total: files.length, status: 'uploading', message: 'Preparing upload...' })
    }
    
    // Get threshold from selected job's min_passing_score
    const jobId = selectedJobForUpload || null
    const threshold = jobId ? (jobScores[jobId] || 60) : 60
    
    console.log('Starting upload with:', {
      filesCount: files.length,
      selectedJobForUpload,
      jobId,
      uploadType,
      threshold
    })
    
    try {
      let shouldRefreshCandidates = false
      
      if (uploadType === 'zip') {
        console.log('ZIP file upload')
        setUploadProgress({ show: true, current: 0, total: 0, status: 'uploading', message: 'Uploading ZIP file...' })
        const result = await api.zipUploadResumes(files[0], jobId, threshold)
        console.log('ZIP upload result:', result)
        const queuedCount = result.queued || result.results?.filter(r => r.status === 'queued').length || 0
        setUploadProgress({
          show: true,
          current: 0,
          total: result.results?.length || queuedCount,
          status: 'processing',
          uploadId: result.upload_id,
          message: result.message || `Queued ${queuedCount} resumes for screening`
        })
        shouldRefreshCandidates = true
      } else if (files.length === 1) {
        console.log('Single file upload')
        const result = await api.uploadResume(files[0], jobId, threshold)
        console.log('Upload result:', result)
        setUploadProgress({
          show: true,
          current: 0,
          total: 1,
          status: 'processing',
          uploadId: result.upload_id,
          message: result.message || 'Resume queued for analysis'
        })
        shouldRefreshCandidates = true
      } else {
        console.log('Bulk file upload')
        setUploadProgress({ show: true, current: 0, total: files.length, status: 'uploading', message: 'Uploading resumes...' })
        const result = await api.bulkUploadResumes(files, jobId, threshold)
        console.log('Bulk upload result:', result)
        const queuedCount = result.queued || result.results?.filter(r => r.status === 'queued').length || files.length
        setUploadProgress({
          show: true,
          current: 0,
          total: queuedCount,
          status: 'processing',
          uploadId: result.upload_id,
          message: result.message || `Queued ${queuedCount} resumes for screening`
        })
        shouldRefreshCandidates = true
      }
      
    } catch (error) {
      console.error('Upload failed:', error)
      setError(`Upload failed: ${error.message}`)
      setUploadProgress(prev => ({ ...prev, show: true, status: 'error', message: error.message || 'Upload failed' }))
    } finally {
      uploadInFlightRef.current = false
      setUploading(false)
    }
  }

  const handleEdit = (candidate) => {
    setEditingCandidate(candidate)
    setEditForm({
      name: candidate.name || '',
      email: candidate.email || '',
      phone: candidate.phone || '',
      experience_years: candidate.experience_years ?? '',
      skills: Array.isArray(candidate.skills) ? candidate.skills.join(', ') : '',
      education: Array.isArray(candidate.education) ? candidate.education.map((item) => (
        typeof item === 'string' ? item : JSON.stringify(item)
      )).join('\n') : '',
      internal_notes: candidate.internal_notes || '',
      current_company: candidate.current_company || '',
      current_role: candidate.current_role || '',
      location: candidate.location || '',
      linkedin_url: candidate.linkedin_url || '',
      summary: candidate.summary || '',
      predefined_questions: candidate.predefined_questions || '',
    })
  }

  const parseMultilineValues = (value) => String(value || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)

  const handleSaveEdit = async () => {
    try {
      const payload = {
        name: editForm.name.trim(),
        email: editForm.email.trim() || null,
        phone: editForm.phone.trim() || null,
        experience_years: editForm.experience_years === '' ? null : Number(editForm.experience_years),
        skills: editForm.skills
          .split(/[,\n]/)
          .map((item) => item.trim())
          .filter(Boolean),
        education: parseMultilineValues(editForm.education),
        internal_notes: editForm.internal_notes.trim() || null,
        current_company: editForm.current_company.trim() || null,
        current_role: editForm.current_role.trim() || null,
        location: editForm.location.trim() || null,
        linkedin_url: editForm.linkedin_url.trim() || null,
        summary: editForm.summary.trim() || null,
        predefined_questions: editForm.predefined_questions.trim() || null,
      }

      await api.updateCandidate(editingCandidate.id, payload)
      setEditingCandidate(null)
      await fetchCandidates()
      alert('✓ Candidate updated successfully')
    } catch (error) {
      console.error('Update failed:', error)
      const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
      setError(`Update failed: ${errorMsg}`)
      alert(`✗ Update failed: ${errorMsg}`)
    }
  }

  const handleCancelEdit = () => {
    setEditingCandidate(null)
    setEditForm({
      name: '',
      email: '',
      phone: '',
      experience_years: '',
      skills: '',
      education: '',
      internal_notes: '',
      current_company: '',
      current_role: '',
      location: '',
      linkedin_url: '',
      summary: '',
      predefined_questions: '',
    })
  }

  const handleDelete = async (id) => {
    if (!canDeleteResumes) {
      setError('Only agency admins can delete resumes')
      return
    }

    const candidate = candidates.find((item) => item.id === id) || null
    setDeleteCandidateModal({ open: true, candidates: candidate ? [candidate] : [] })
  }

  const handleBulkDelete = () => {
    if (!canDeleteResumes) {
      setError('Only agency admins can delete resumes')
      return
    }

    const candidatesToDelete = candidates.filter((candidate) => selectedCandidates.includes(candidate.id))
    if (candidatesToDelete.length === 0) return
    setDeleteCandidateModal({ open: true, candidates: candidatesToDelete })
  }

  const handleCloseDeleteModal = () => {
    setDeleteCandidateModal({ open: false, candidates: [] })
  }

  const handleConfirmDelete = async () => {
    const candidatesToDelete = deleteCandidateModal.candidates || []
    if (candidatesToDelete.length === 0) return

    try {
      setDeletingCandidates(true)

      const deleteTargetIds = Array.from(new Set(
        candidatesToDelete.flatMap((candidate) => {
          const mergedIds = Array.isArray(candidate?.merged_candidate_ids) ? candidate.merged_candidate_ids : []
          if (mergedIds.length > 0) {
            return mergedIds
          }
          return candidate?.id ? [candidate.id] : []
        }).filter(Boolean)
      ))

      const deleteResults = await Promise.allSettled(
        deleteTargetIds.map((candidateId) => api.deleteCandidate(candidateId))
      )

      const failedDeletes = deleteResults.filter((result) => result.status === 'rejected')
      const deletedIds = deleteTargetIds
        .filter((_, index) => deleteResults[index].status === 'fulfilled')

      handleCloseDeleteModal()
      if (deletedIds.length > 0) {
        setSelectedCandidates((prev) => prev.filter((candidateId) => !deletedIds.includes(candidateId)))
      }
      await fetchCandidates()

      if (deletedIds.length > 0) {
        try {
          await api.syncCandidatesToSheets()
        } catch (syncError) {
          console.error('Auto-sync to sheets failed:', syncError)
        }
      }

      if (failedDeletes.length > 0) {
        setError(`Deleted ${deletedIds.length} candidate${deletedIds.length === 1 ? '' : 's'}, but ${failedDeletes.length} failed.`)
      } else {
        setError('')
      }
    } catch (error) {
      console.error('Delete failed:', error)
      setError(`Delete failed: ${error.message}`)
    } finally {
      setDeletingCandidates(false)
    }
  }



  const handleOpenEmailModal = (type) => {
    let subject = ''
    let message = ''
    
    if (type === 'invitation') {
      subject = 'Interview Invitation - You have been shortlisted!'
      message = `Dear ${formatCandidateDisplayName(selectedCandidate.name)},\n\nCongratulations! You have been shortlisted for the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nPlease select a convenient time slot for your interview by replying to this email.\n\nBest regards,\nRecruitment Team`
    } else if (type === 'reschedule') {
      subject = 'Interview Reschedule Request'
      message = `Dear ${formatCandidateDisplayName(selectedCandidate.name)},\n\nWe need to reschedule your interview for the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nPlease reply with your available time slots and we will confirm a new interview time.\n\nWe apologize for any inconvenience.\n\nBest regards,\nRecruitment Team`
    } else if (type === 'rejection') {
      subject = 'Application Status Update'
      message = `Dear ${formatCandidateDisplayName(selectedCandidate.name)},\n\nThank you for your interest in the position${candidateJob ? ` of ${candidateJob.title}` : ''}.\n\nAfter careful consideration, we regret to inform you that we will not be moving forward with your application at this time.\n\nWe appreciate the time you invested in the application process and wish you the best in your job search.\n\nBest regards,\nRecruitment Team`
    }
    
    setEmailModal({ show: true, type, subject, message })
    setIsEditingEmail(false)
  }

  const selectedCandidateStage = String(selectedCandidate?.stage || '').toUpperCase()
  const canSendRejectedInterviewInvite = selectedCandidateStage === 'REJECTED' || selectedCandidateStage === 'RESUME_REJECTED'
  const shouldShowInviteButton = selectedCandidateStage !== 'SHORTLISTED' || canSendRejectedInterviewInvite

  const handleSendEmail = async () => {
    setSending(true)
    try {
      if (emailModal.type === 'invitation' && canSendRejectedInterviewInvite) {
        const candidateDetails = await api.getCandidate(selectedCandidate.id).catch(() => selectedCandidate)
        const resolvedJob = candidateJob || (candidateDetails?.job_id ? await api.getJob(candidateDetails.job_id).catch(() => null) : null)

        await api.triggerNotification(selectedCandidate.id, 'resume_shortlisted', {
          candidateName: candidateDetails?.name || selectedCandidate.name || '',
          candidateEmail: candidateDetails?.email || selectedCandidate.email || '',
          candidateId: candidateDetails?.id || selectedCandidate.id || '',
          jobId: resolvedJob?.id || candidateDetails?.job_id || '',
          jobTitle: resolvedJob?.title || candidateDetails?.job_title || '',
          jobRole: candidateDetails?.current_role || resolvedJob?.title || '',
          jobDescription: resolvedJob?.description || '',
          resumeText: candidateDetails?.resume_text || selectedCandidate.resume_text || '',
          predefinedQuestions: candidateDetails?.predefined_questions || '',
          skills: Array.isArray(candidateDetails?.skills)
            ? candidateDetails.skills.join(', ')
            : (Array.isArray(selectedCandidate?.skills) ? selectedCandidate.skills.join(', ') : ''),
          agency_id: candidateDetails?.agency_id || selectedCandidate?.agency_id || '',
          user_id: '',
          companyName: resolvedJob?.company_name || '',
        })

        await api.updateCandidateStage(selectedCandidate.id, 'SHORTLISTED')
        await fetchCandidates()

        alert(`✓ Shortlisted interview email sent successfully to ${selectedCandidate.email}`)
        setEmailModal({ show: false, type: '', subject: '', message: '' })
        handleCloseModal()
        return
      }

      if (emailModal.type === 'reschedule') {
        const candidateDetails = await api.getCandidate(selectedCandidate.id).catch(() => selectedCandidate)
        const resolvedJob = candidateJob || (candidateDetails?.job_id ? await api.getJob(candidateDetails.job_id).catch(() => null) : null)

        await api.createSlotSelectionLink(selectedCandidate.id, {
          candidateName: candidateDetails?.name || selectedCandidate.name || '',
          candidateEmail: candidateDetails?.email || selectedCandidate.email || '',
          candidateId: candidateDetails?.id || selectedCandidate.id || '',
          jobId: resolvedJob?.id || candidateDetails?.job_id || '',
          jobTitle: resolvedJob?.title || candidateDetails?.job_title || '',
          jobRole: candidateDetails?.current_role || resolvedJob?.title || '',
          jobDescription: resolvedJob?.description || '',
          resumeText: candidateDetails?.resume_text || selectedCandidate.resume_text || '',
          predefinedQuestions: candidateDetails?.predefined_questions || '',
          skills: Array.isArray(candidateDetails?.skills)
            ? candidateDetails.skills.join(', ')
            : (Array.isArray(selectedCandidate?.skills) ? selectedCandidate.skills.join(', ') : ''),
          agency_id: candidateDetails?.agency_id || selectedCandidate?.agency_id || '',
          user_id: '',
          companyName: resolvedJob?.company_name || '',
        }, 'interview_rescheduled')

        await fetchCandidates()

        alert(`âœ“ Reschedule email sent successfully to ${selectedCandidate.email}`)
        setEmailModal({ show: false, type: '', subject: '', message: '' })
        handleCloseModal()
        return
      }

      await api.sendEmail(selectedCandidate.id, emailModal.subject, emailModal.message)
      
      // Update candidate stage
      const stageMap = {
        invitation: 'SHORTLISTED',
        reschedule: 'INTERVIEW_RESCHEDULED',
        rejection: 'REJECTED'
      }
      
      await api.updateCandidateStage(selectedCandidate.id, stageMap[emailModal.type])
      await fetchCandidates()
      
      alert(`✓ Email sent successfully to ${selectedCandidate.email}`)
      setEmailModal({ show: false, type: '', subject: '', message: '' })
      handleCloseModal()
    } catch (error) {
      console.error('Error sending email:', error)
      alert(`✗ Failed to send email: ${error.message}`)
    } finally {
      setSending(false)
    }
  }

  const handleViewCandidate = async (candidate) => {
    setSelectedCandidate(normalizeResumeCandidate(candidate, jobsById))
    setAnalysisLoading(true)
    setAiAnalysis(null)
    setResumeSummary(null)
    setResumeSummaryCandidateId(null)

    const candidateDetailsPromise = api.getCandidate(candidate.id).catch((error) => {
      console.error('Failed to fetch candidate details:', error)
      return null
    })
    const summaryPromise = api.getResumeSummary(candidate.id).catch((error) => {
      console.error('Failed to fetch resume summary:', error)
      return { summary: 'Unable to generate summary at this time.' }
    })

    setSummaryLoading(true)
    summaryPromise
      .then((summaryResult) => {
        setResumeSummary(summaryResult?.summary || 'Unable to generate summary at this time.')
        setResumeSummaryCandidateId(candidate.id)
      })
      .finally(() => {
        setSummaryLoading(false)
      })

    try {
      const [candidateDetails, jobResult, analysis] = await Promise.all([
        candidateDetailsPromise,
        candidate.job_id
          ? api.getJob(candidate.job_id).catch((error) => {
            console.error('Failed to fetch job details:', error)
            return null
          })
          : Promise.resolve(null),
        api.getAIAnalysis(candidate.id).catch((error) => {
          console.error('Failed to fetch AI analysis:', error)
          return null
        }),
      ])

      if (candidateDetails) {
        setSelectedCandidate(normalizeResumeCandidate(candidateDetails, jobsById))
      }
      setCandidateJob(jobResult)

      // Override match_score with resume_score for consistency
      const matchScore = candidateDetails?.resume_score ?? candidate.resume_score
      if (analysis && matchScore !== undefined) {
        analysis.match_score = matchScore
      }
      setAiAnalysis(analysis)
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleCloseModal = () => {
    setSelectedCandidate(null)
    setCandidateJob(null)
    setAiAnalysis(null)
    setResumeSummary(null)
    setResumeSummaryCandidateId(null)
    setSummaryLoading(false)
    if (selectedCandidateId) {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.delete('candidate_id')
      setSearchParams(nextParams, { replace: true })
    }
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
    if (resumeSummaryCandidateId === candidate.id && resumeSummary) {
      return
    }
    setSummaryLoading(true)
    try {
      const summary = await api.getResumeSummary(candidate.id)
      setResumeSummary(summary.summary)
      setResumeSummaryCandidateId(candidate.id)
    } catch (error) {
      console.error('Failed to fetch resume summary:', error)
      setResumeSummary('Unable to generate summary at this time.')
      setResumeSummaryCandidateId(candidate.id)
    } finally {
      setSummaryLoading(false)
    }
  }

  const closeResumeModal = () => {
    setViewingResume(null)
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
            <div className="relative flex-1">
              <select required
                className="flex h-10 w-full appearance-none rounded-lg border border-input bg-background pl-3 pr-10 py-2 text-sm"
                value={selectedJobForUpload}
                onChange={(e) => setSelectedJobForUpload(e.target.value)}
              >
                <option value="">Select Job </option>
                {uploadJobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.company_name ? `${job.company_name} - ${job.title}` : job.title}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            <div className="relative">
              <select
                className="flex h-10 appearance-none rounded-lg border border-input bg-background pl-3 pr-10 py-2 text-sm"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
              >
                <option value="single">Single Upload</option>
                <option value="bulk">Bulk Upload</option>
                <option value="zip">ZIP Upload</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
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
                    const result = await api.bulkAssignCandidates(selectedCandidates, selectedUser)
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
              {canDeleteResumes && (
                <Button
                  variant="destructive"
                  onClick={handleBulkDelete}
                  disabled={deletingCandidates}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  {deletingCandidates ? 'Deleting...' : `Delete Selected (${selectedCandidates.length})`}
                </Button>
              )}
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
      <div className="flex flex-wrap gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <DateRangeFilter value={dateRange} onChange={setDateRange} />
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
              checked={statusFilter.includes('RESUME_SHORTLISTED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev => 
                  checked ? [...prev, 'RESUME_SHORTLISTED'] : prev.filter(s => s !== 'RESUME_SHORTLISTED')
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
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('IN_REVIEW')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev => 
                  checked ? [...prev, 'IN_REVIEW'] : prev.filter(s => s !== 'IN_REVIEW')
                )
              }}
            >
              In Review
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('INTERVIEW_SCHEDULED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev =>
                  checked ? [...prev, 'INTERVIEW_SCHEDULED'] : prev.filter(s => s !== 'INTERVIEW_SCHEDULED')
                )
              }}
            >
              Interview Scheduled
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('INTERVIEWED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev =>
                  checked ? [...prev, 'INTERVIEWED'] : prev.filter(s => s !== 'INTERVIEWED')
                )
              }}
            >
              Interviewed
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={statusFilter.includes('INTERVIEW_RESCHEDULED')}
              onCheckedChange={(checked) => {
                setStatusFilter(prev => 
                  checked ? [...prev, 'INTERVIEW_RESCHEDULED'] : prev.filter(s => s !== 'INTERVIEW_RESCHEDULED')
                )
              }}
            >
              Interview Rescheduled
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
            <ExpandableList
              items={candidates}
              initialCount={5}
              renderItems={({ items }) => (
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
                    {items.map((candidate) => {
                  const jobDetails = jobsById[candidate.job_id]

                  return (
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
                      <div onClick={() => handleViewCandidate(candidate)}>
                        <p className="font-medium text-primary hover:underline cursor-pointer">{formatCandidateDisplayName(candidate.name)}</p>
                        <p className="text-sm text-muted-foreground">{candidate.email}</p>
                      </div>
                    </td>
                    <td className="p-4">
                      {candidate.job_title ? (
                        <div>
                          <p className="text-sm font-medium">{candidate.job_title}</p>
                          {jobDetails?.company_name && (
                            <p className="text-xs text-muted-foreground">
                              {jobDetails.company_name}
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
                      <ResumeStatusBadge candidate={candidate} />
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
                        <Button variant="ghost" size="icon" onClick={() => handleViewResume(candidate)} title="View Resume">
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(candidate)} title="Edit">
                          <Edit className="h-4 w-4" />
                        </Button>
                        {canDeleteResumes && (
                          <Button variant="ghost" size="icon" onClick={() => handleDelete(candidate.id)} title="Delete">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                  )
                    })}
                  </tbody>
                </table>
              )}
            />
            {candidates.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                No candidates found
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={Boolean(editingCandidate)} onOpenChange={(open) => {
        if (!open) {
          handleCancelEdit()
        }
      }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Resume Data</DialogTitle>
            <DialogDescription>Update parsed candidate details without changing the existing workflow.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Phone Number</label>
              <Input value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Experience</label>
              <Input type="number" min="0" step="0.1" value={editForm.experience_years} onChange={(e) => setEditForm({ ...editForm, experience_years: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Current Company</label>
              <Input value={editForm.current_company} onChange={(e) => setEditForm({ ...editForm, current_company: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Current Role</label>
              <Input value={editForm.current_role} onChange={(e) => setEditForm({ ...editForm, current_role: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Location</label>
              <Input value={editForm.location} onChange={(e) => setEditForm({ ...editForm, location: e.target.value })} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">LinkedIn URL</label>
              <Input value={editForm.linkedin_url} onChange={(e) => setEditForm({ ...editForm, linkedin_url: e.target.value })} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Skills</label>
              <textarea
                className="min-h-[88px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={editForm.skills}
                onChange={(e) => setEditForm({ ...editForm, skills: e.target.value })}
                placeholder="Comma or newline separated skills"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Education</label>
              <textarea
                className="min-h-[88px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={editForm.education}
                onChange={(e) => setEditForm({ ...editForm, education: e.target.value })}
                placeholder="One item per line"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Notes</label>
              <textarea
                className="min-h-[100px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={editForm.internal_notes}
                onChange={(e) => setEditForm({ ...editForm, internal_notes: e.target.value })}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Summary</label>
              <textarea
                className="min-h-[100px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={editForm.summary}
                onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Predefined Questions</label>
              <textarea
                className="min-h-[88px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                value={editForm.predefined_questions}
                onChange={(e) => setEditForm({ ...editForm, predefined_questions: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelEdit}>Cancel</Button>
            <Button onClick={handleSaveEdit} disabled={!editForm.name.trim()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
              {selectedCandidate.parsing_status === 'processing' && (
                <div className="flex items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-sm text-yellow-800 dark:text-yellow-200">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-yellow-600 flex-shrink-0"></div>
                  <span>Resume is still being analyzed. Details will appear once processing completes — refresh to check.</span>
                </div>
              )}

              {/* Candidate Info */}
              <div>
                <h3 className="font-semibold mb-3">Personal Information</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Name</p>
                    <p className="font-medium">{formatCandidateDisplayName(selectedCandidate.name)}</p>
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
              {(selectedCandidate.current_company || selectedCandidate.current_role || selectedCandidate.experience_years !== null && selectedCandidate.experience_years !== undefined) && (
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
                    {(selectedCandidate.experience_years !== null && selectedCandidate.experience_years !== undefined) && (
                      <div>
                        <p className="text-sm text-muted-foreground">Experience</p>
                        <p>{selectedCandidate.experience_years} years</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {selectedCandidateStatus && (
                <div>
                  <h3 className="font-semibold mb-3">Resume Status</h3>
                  <Badge className={selectedCandidateStatus.badgeClass}>
                    {selectedCandidateStatus.label}
                  </Badge>
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
                        <p className="line-clamp-5 text-sm text-blue-800 dark:text-blue-200 leading-relaxed">
                          {formatSummaryAsParagraph(selectedCandidate.summary)}
                        </p>
                      </div>
                    )}

                    {/* Match Score */}
                    <div className="bg-muted p-4 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Resume Score</span>
                        {selectedCandidateStatus && (
                          <Badge className={selectedCandidateStatus.badgeClass}>
                            {selectedCandidateStatus.label}
                          </Badge>
                        )}
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
                  {shouldShowInviteButton ? (
                    <>
                      <Button 
                        className="flex-1"
                        onClick={() => handleOpenEmailModal('invitation')}
                      >
                        {canSendRejectedInterviewInvite ? 'Send Interview Invite' : 'Send Interview Invitation'}
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
                    </>
                  ) : (
                    <Button 
                      variant="outline"
                      className="flex-1"
                      onClick={() => handleOpenEmailModal('reschedule')}
                    >
                      Interview Reschedule
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Email Customization Modal */}
      {emailModal.show && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" onClick={() => { setEmailModal({ show: false, type: '', subject: '', message: '' }); setIsEditingEmail(false); }}>
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Customize Email</h2>
              <div className="flex items-center gap-2">
                {!isEditingEmail && (
                  <Button variant="outline" size="sm" onClick={() => setIsEditingEmail(true)}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={() => { setEmailModal({ show: false, type: '', subject: '', message: '' }); setIsEditingEmail(false); }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Subject</label>
                {isEditingEmail ? (
                  <Input
                    value={emailModal.subject}
                    onChange={(e) => setEmailModal({ ...emailModal, subject: e.target.value })}
                    placeholder="Email subject"
                  />
                ) : (
                  <div className="w-full rounded-lg border border-input bg-muted px-3 py-2 text-sm">
                    {emailModal.subject}
                  </div>
                )}
              </div>
              
              <div>
                <label className="text-sm font-medium mb-2 block">Message</label>
                {isEditingEmail ? (
                  <textarea
                    value={emailModal.message}
                    onChange={(e) => setEmailModal({ ...emailModal, message: e.target.value })}
                    placeholder="Email message"
                    rows={12}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm resize-none"
                  />
                ) : (
                  <div className="w-full rounded-lg border border-input bg-muted px-3 py-2 text-sm whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                    {emailModal.message}
                  </div>
                )}
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
                  onClick={() => { setEmailModal({ show: false, type: '', subject: '', message: '' }); setIsEditingEmail(false); }}
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
              <h2 className="text-xl font-bold">Resume Summary - {formatCandidateDisplayName(viewingResume.name)}</h2>
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
                  <p className="line-clamp-5 text-sm leading-relaxed">{formatSummaryAsParagraph(resumeSummary)}</p>
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
              {uploadProgress.status === 'completed'
                ? 'Resume Uploaded and Analyzed successfully'
                : uploadProgress.status === 'error'
                  ? 'Upload Failed'
                  : 'Uploading Resumes...'}
            </h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>Progress</span>
                  <span className="font-medium">{uploadProgress.current} / {uploadProgress.total}</span>
                </div>
                <div className="relative overflow-hidden rounded-full">
                  <Progress value={uploadProgress.total ? (uploadProgress.current / uploadProgress.total) * 100 : 0} className="h-2" />
                  {uploadProgress.status !== 'completed' && uploadProgress.status !== 'error' && (
                    <div className="absolute inset-y-0 left-0 w-20 animate-pulse bg-white/30 rounded-full" />
                  )}
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {uploadProgress.message || 'Processing resumes...'}
                </p>
              </div>
              {(uploadProgress.status === 'completed' || uploadProgress.status === 'error') && (
                <div className="flex justify-end">
                  <Button onClick={() => setUploadProgress({ show: false, current: 0, total: 0, status: 'uploading', message: '', uploadId: null })}>
                    Close
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <Dialog
        open={deleteCandidateModal.open}
        onOpenChange={(open) => setDeleteCandidateModal({ open, candidates: open ? deleteCandidateModal.candidates : [] })}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{deleteCandidateModal.candidates.length > 1 ? 'Delete Candidates' : 'Delete Candidate'}</DialogTitle>
            <DialogDescription>
              {deleteCandidateModal.candidates.length > 1
                ? `Are you sure you want to delete ${deleteCandidateModal.candidates.length} selected candidates?`
                : `Are you sure you want to delete the candidate${deleteCandidateModal.candidates[0]?.name ? ` "${deleteCandidateModal.candidates[0].name}"` : ''}?`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleCloseDeleteModal}
            >
              Cancel
            </Button>
            <Button
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={handleConfirmDelete}
              disabled={deletingCandidates}
            >
              {deletingCandidates ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

