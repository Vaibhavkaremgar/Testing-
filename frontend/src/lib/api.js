const DEFAULT_API_ORIGIN = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://dashboard.pontis.one'
const API_ORIGIN = (import.meta.env.VITE_API_URL || DEFAULT_API_ORIGIN).replace(/\/$/, '')
const API_BASE = `${API_ORIGIN}/api`
const DEFAULT_LIST_LIMIT = 20
const APP_BASE = API_BASE.replace(/\/api$/, '')
const RECORDING_API_BASE = "https://interview.pontis.one/api"

export function getDashboardRecordingUrl(sessionToken, token) {
  return `${RECORDING_API_BASE}/recording/${sessionToken}?token=${token}`
}

// Debug logging
console.log('VITE_API_URL:', import.meta.env.VITE_API_URL)
console.log('API_BASE:', API_BASE)

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('token')
    this.responseCache = new Map()
  }

  setToken(token) {
    this.token = token
    if (token) {
      localStorage.setItem('token', token)
    } else {
      localStorage.removeItem('token')
    }
  }

  getToken() {
    return this.token || localStorage.getItem('token')
  }

  cloneCacheValue(value) {
    if (value === null || value === undefined) return value
    if (typeof structuredClone === 'function') {
      return structuredClone(value)
    }
    return JSON.parse(JSON.stringify(value))
  }

  getCacheKey(endpoint, method) {
    return `${method}:${this.getToken() || 'anonymous'}:${endpoint}`
  }

  getCachedResponse(cacheKey, ttlMs) {
    const cachedEntry = this.responseCache.get(cacheKey)
    if (!cachedEntry) return null
    if ((Date.now() - cachedEntry.timestamp) > ttlMs) {
      this.responseCache.delete(cacheKey)
      return null
    }
    return this.cloneCacheValue(cachedEntry.value)
  }

  setCachedResponse(cacheKey, value) {
    this.responseCache.set(cacheKey, {
      timestamp: Date.now(),
      value: this.cloneCacheValue(value),
    })
  }

  async request(endpoint, options = {}) {
    const {
      cacheTtlMs = 60 * 1000,
      skipCache = false,
      ...fetchOptions
    } = options
    const url = `${API_BASE}${endpoint}`
    const method = (fetchOptions.method || 'GET').toUpperCase()
    const headers = {
      ...fetchOptions.headers,
    }

    if (this.getToken()) {
      headers['Authorization'] = `Bearer ${this.getToken()}`
    }

    if (!(fetchOptions.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }

    const isCacheableGet = method === 'GET' && !fetchOptions.body && !skipCache
    const cacheKey = isCacheableGet ? this.getCacheKey(endpoint, method) : null
    if (cacheKey) {
      const cachedResponse = this.getCachedResponse(cacheKey, cacheTtlMs)
      if (cachedResponse !== null) {
        return cachedResponse
      }
    }

    let response
    try {
      response = await fetch(url, {
        ...fetchOptions,
        headers,
      })
    } catch (error) {
      throw new Error(`Unable to reach the server at ${API_ORIGIN}. Make sure the backend is running and the API URL is correct.`)
    }

    if (response.status === 401) {
      // Don't auto-logout, just throw error
      throw new Error('Unauthorized')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }))
      const detail = error?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.message || error?.message || 'An error occurred'
      const requestError = new Error(message)
      requestError.status = response.status
      requestError.detail = detail
      throw requestError
    }

    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      const data = await response.json()
      if (cacheKey) {
        this.setCachedResponse(cacheKey, data)
      }
      return data
    }
    return {}
  }

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' })
  }

  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' })
  }

  buildQuery(params = {}, { defaultLimit } = {}) {
    const searchParams = new URLSearchParams()
    const source = defaultLimit && params.limit === undefined
      ? { ...params, limit: defaultLimit }
      : params

    Object.entries(source).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })

    const query = searchParams.toString()
    return query ? `?${query}` : ''
  }

  // Auth
  async login(email, password) {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)

    const loginUrl = `${API_BASE}/auth/login`
    console.log('Login URL:', loginUrl)

    try {
      let response
      try {
        response = await fetch(loginUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData,
        })
      } catch (networkError) {
        throw new Error(`Unable to reach the server at ${API_ORIGIN}. Make sure the backend is running and the API URL is correct.`)
      }

      console.log('Response status:', response.status)
      console.log('Response headers:', response.headers)
      
      if (!response.ok) {
        let errorMessage = 'Login failed'
        try {
          const error = await response.json()
          errorMessage = error.detail || errorMessage
        } catch (e) {
          errorMessage = `Login failed (${response.status})`
        }
        throw new Error(errorMessage)
      }

      const data = await response.json()
      
      if (!data.access_token) {
        throw new Error('No access token received')
      }

      this.setToken(data.access_token)
      return data
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  async register(userData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    })
  }

  async getMe() {
    return this.request('/auth/me')
  }

  async changePassword(currentPassword, newPassword) {
    return this.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      }),
    })
  }

  async updateProfile(profileData) {
    return this.request('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(profileData),
    })
  }

  async uploadAvatar(file) {
    const formData = new FormData()
    formData.append('file', file)
    return this.request('/auth/profile/avatar', {
      method: 'POST',
      body: formData,
    })
  }

  async getLoginScreen() {
    return this.request('/auth/login-screen')
  }

  async getUsersByAgency(agencyId) {
    return this.request(`/auth/users/by-agency/${agencyId}`)
  }

  async getAllUsers(params = {}) {
    return this.request(`/auth/users${this.buildQuery(params)}`)
  }

  async getPublicUsers() {
    return this.request('/auth/users/public')
  }

  async updateUser(userId, userData) {
    return this.request(`/auth/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    })
  }

  async deleteUser(userId) {
    return this.request(`/auth/users/${userId}`, {
      method: 'DELETE',
    })
  }

  logout() {
    this.setToken(null)
  }

  // Candidates
  async getCandidates(params = {}, options = {}) {
    return this.request(`/candidates${this.buildQuery(
      params,
      options.includeDefaultLimit === false ? {} : { defaultLimit: DEFAULT_LIST_LIMIT }
    )}`)
  }

  async getCandidatesCount(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/candidates/count${query ? `?${query}` : ''}`)
  }

  async getCandidate(id) {
    return this.request(`/candidates/${id}`)
  }

  async createCandidate(data) {
    return this.request('/candidates', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateCandidate(id, data) {
    return this.request(`/candidates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async updateCandidateStage(id, stage, options = {}) {
    return this.request(`/candidates/${id}/stage`, {
      method: 'PATCH',
      body: JSON.stringify({ stage, ...options }),
    })
  }

  async updateCandidateNotes(id, notes) {
    return this.request(`/candidates/${id}/notes`, {
      method: 'PATCH',
      body: JSON.stringify({ notes }),
    })
  }

  async assignCandidate(id, userId) {
    return this.request(`/candidates/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ assigned_to_user_id: userId }),
    })
  }

  async reviewCandidate(id, action) {
    return this.request(`/candidates/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
  }

  async reviewCandidate(id, action) {
    return this.request(`/candidates/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
  }

  async getMyAssignedCandidates() {
    return this.request('/candidates/assigned/me')
  }

  async bulkAssignCandidates(candidateIds, userId) {
    return this.request('/candidates/bulk-assign', {
      method: 'POST',
      body: JSON.stringify({
        candidate_ids: candidateIds,
        user_id: userId
      }),
    })
  }

  
  async deleteCandidate(id) {
    return this.request(`/candidates/${id}`, { method: 'DELETE' })
  }

  async uploadResume(file, jobId = null, threshold = 60) {
    const formData = new FormData()
    formData.append('file', file)
    
    let url = '/candidates/upload'
    const params = new URLSearchParams()
    if (jobId) params.append('job_id', jobId)
    params.append('threshold', threshold)
    url += `?${params.toString()}`
    
    return this.request(url, {
      method: 'POST',
      body: formData,
    })
  }

  async bulkUploadResumes(files, jobId = null, threshold = 60) {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    
    let url = '/candidates/bulk-upload'
    const params = new URLSearchParams()
    if (jobId) params.append('job_id', jobId)
    params.append('threshold', threshold)
    url += `?${params.toString()}`
    
    return this.request(url, {
      method: 'POST',
      body: formData,
    })
  }

  async zipUploadResumes(file, jobId = null, threshold = 60) {
    const formData = new FormData()
    formData.append('file', file)
    
    let url = '/candidates/zip-upload'
    const params = new URLSearchParams()
    if (jobId) params.append('job_id', jobId)
    params.append('threshold', threshold)
    url += `?${params.toString()}`
    
    return this.request(url, {
      method: 'POST',
      body: formData,
    })
  }

  async getUploadProgress(uploadId) {
    return this.request(`/candidates/upload-progress/${uploadId}`, { skipCache: true })
  }

  async getPipelineStages(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/candidates/pipeline/stages${query ? `?${query}` : ''}`, { skipCache: true })
  }

  async syncCandidatesToSheets() {
    return this.request('/candidates/sync-to-sheets', {
      method: 'POST',
    })
  }

  async syncScoresFromSheets() {
    return this.request('/candidates/sync-from-sheets', {
      method: 'POST',
    })
  }

  // Jobs
  async getJobs(params = {}, options = {}) {
    return this.request(`/jobs${this.buildQuery(
      params,
      options.includeDefaultLimit === false ? {} : { defaultLimit: DEFAULT_LIST_LIMIT }
    )}`)
  }

  async getDashboardData(params = {}) {
    return this.request(`/dashboard-data${this.buildQuery(params)}`, { skipCache: true })
  }

  async getJobsCount(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/jobs/count${query ? `?${query}` : ''}`)
  }

  async getUsageSummary() {
    return this.request('/usage/summary', { skipCache: true })
  }

  async getJob(id) {
    return this.request(`/jobs/${id}`)
  }

  async createJob(data) {
    return this.request('/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateJob(id, data) {
    return this.request(`/jobs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteJob(id) {
    return this.request(`/jobs/${id}`, { method: 'DELETE' })
  }

  // Interviews
  async getInterviews(params = {}, options = {}) {
    const searchParams = new URLSearchParams()
    const source = options.includeDefaultLimit === false || params.limit !== undefined
      ? params
      : { ...params, limit: DEFAULT_LIST_LIMIT }
    Object.entries(source).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/interviews${query ? `?${query}` : ''}`)
  }

  async getInterviewsCount(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/interviews/count${query ? `?${query}` : ''}`)
  }

  async getInterview(id) {
    return this.request(`/interviews/${id}`)
  }

  async createInterview(data) {
    return this.request('/interviews', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateInterview(id, data) {
    return this.request(`/interviews/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async completeInterview(id) {
    return this.request(`/interviews/${id}/complete`, { method: 'POST' })
  }

  async deleteInterview(id) {
    return this.request(`/interviews/${id}`, { method: 'DELETE' })
  }

  // Analytics
  async getDashboardStats(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/dashboard-stats${query ? `?${query}` : ''}`)
  }

  async getPipelineStats() {
    return this.request('/analytics/pipeline-stats')
  }

  async getHiringFunnel(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/hiring-funnel${query ? `?${query}` : ''}`)
  }

  async getRecruitmentFunnel(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/recruitment-funnel${query ? `?${query}` : ''}`)
  }

  async getKpiSummary(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/kpi-summary${query ? `?${query}` : ''}`)
  }

  async getAnalyticsWidgetCatalog() {
    return this.request('/analytics/widgets/catalog')
  }

  async getAnalyticsWidgetLayout() {
    return this.request('/analytics/widgets/layout')
  }

  async saveAnalyticsWidgetLayout(items = []) {
    return this.request('/analytics/widgets/layout', {
      method: 'POST',
      body: JSON.stringify({ items }),
    })
  }

  async getTimeToHire(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'all') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/time-to-hire${query ? `?${query}` : ''}`)
  }

  async getSkillHeatmap(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'all') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/skill-heatmap${query ? `?${query}` : ''}`)
  }

  async getScoreDistribution(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'all') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/score-distribution${query ? `?${query}` : ''}`)
  }

  async getResumeScoresTrend(params = {}) {
    return this.request(`/analytics/resume-scores-trend${this.buildQuery(params)}`)
  }

  async getInterviewScoresTrend(params = {}) {
    return this.request(`/analytics/interview-scores-trend${this.buildQuery(params)}`)
  }

  async getHiringByDepartment(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'all') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/hiring-by-department${query ? `?${query}` : ''}`)
  }

  async getSourceBreakdown() {
    return this.request('/analytics/source-breakdown')
  }

  async getDeclineReasons() {
    return this.request('/analytics/decline-reasons')
  }

  async getOfferAcceptanceRate() {
    return this.request('/analytics/offer-acceptance-rate')
  }

  async getHiringMetrics() {
    return this.request('/analytics/hiring-metrics')
  }

  async getHiringIntelligence() {
    return this.request('/analytics/hiring-intelligence')
  }

  async getActiveJobs(params = {}) {
    return this.request(`/analytics/active-jobs${this.buildQuery(params)}`)
  }

  async getUpcomingInterviews(params = {}) {
    return this.request(`/analytics/upcoming-interviews${this.buildQuery(params)}`)
  }

  async getTimeToHireStages(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/analytics/time-to-hire-stages${query ? `?${query}` : ''}`)
  }

  // Email Templates
  async getEmailTemplateMeta() {
    return this.request('/email-templates/meta')
  }

  async getEmailTemplates(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/email-templates${query ? `?${query}` : ''}`)
  }

  async getEmailTemplatesForAgencyStatus(agencyId, status) {
    return this.request(`/email-templates/agency/${agencyId}/status/${status}`)
  }

  async createEmailTemplate(data) {
    return this.request('/email-templates', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateEmailTemplate(id, data) {
    return this.request(`/email-templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async previewEmailTemplate(data) {
    return this.request('/email-templates/preview', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Settings
  async getResumeScoreSettings() {
    return this.request('/settings/resume-score')
  }

  async saveResumeScoreSettings(settings) {
    return this.request('/settings/resume-score', {
      method: 'POST',
      body: JSON.stringify(settings),
    })
  }

  // Resume Summary
  async getResumeSummary(candidateId) {
    return this.request(`/candidates/${candidateId}/resume-summary`)
  }

  // AI Analysis
  async getAIAnalysis(candidateId) {
    return this.request(`/candidates/${candidateId}/ai-analysis`)
  }

  // Get resume file URL
  getResumeFileUrl(candidateId) {
    return `${API_BASE}/candidates/${candidateId}/resume-file`
  }

  getDashboardRecordingUrl(sessionToken) {
    const token = this.getToken()
    const normalizedSessionToken = String(sessionToken || '').trim()
    if (!normalizedSessionToken) {
      return ''
    }
    const encodedSessionToken = encodeURIComponent(normalizedSessionToken)
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    return `${API_BASE}/recording/${encodedSessionToken}${query}`
  }

  getInterviewVideoUrl(interviewId) {
    const token = this.getToken()
    const normalizedInterviewId = String(interviewId || '').trim()
    if (!normalizedInterviewId) {
      return ''
    }
    const encodedInterviewId = encodeURIComponent(normalizedInterviewId)
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    return `${API_BASE}/interviews/video/${encodedInterviewId}${query}`
  }

  getUploadedRecordingUrl(recordingPath) {
    const normalizedPath = String(recordingPath || '').trim()
    if (!normalizedPath) {
      return ''
    }

    if (/^https?:\/\//i.test(normalizedPath)) {
      return normalizedPath
    }

    const sanitizedPath = normalizedPath
      .replace(/^\/+/, '')
      .replace(/^uploads\/+/i, '')

    return sanitizedPath ? `${APP_BASE}/uploads/${sanitizedPath}` : ''
  }

  // Extract job data from file
  async extractJobData(file) {
    const formData = new FormData()
    formData.append('file', file)
    
    return this.request('/jobs/extract-data', {
      method: 'POST',
      body: formData,
    })
  }

  // Clients
  async getClients(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/clients${query ? `?${query}` : ''}`)
  }

  async getClientsCount() {
    return this.request('/clients/count')
  }

  async getClientNames() {
    return this.request('/clients/names')
  }

  async getClientStats() {
    return this.request('/clients/stats')
  }

  async getClient(id) {
    return this.request(`/clients/${id}`)
  }

  async createClient(data) {
    return this.request('/clients', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateClient(id, data) {
    return this.request(`/clients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteClient(id) {
    return this.request(`/clients/${id}`, { method: 'DELETE' })
  }

  // Communications
  async getCommunications(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/communications${query ? `?${query}` : ''}`)
  }

  async deleteEmailCommunication(id) {
    return this.request(`/communications/${id}`, { method: 'DELETE' })
  }

  // Send Email
  async sendEmail(candidateId, subject, message) {
    return this.request('/candidates/send-email', {
      method: 'POST',
      body: JSON.stringify({
        candidate_id: candidateId,
        subject: subject,
        message: message
      }),
    })
  }

  async createSlotSelectionLink(candidateId, payload = {}, status = 'slot_selection') {
    return this.request('/notifications/slot-selection-link', {
      method: 'POST',
      body: JSON.stringify({
        candidate_id: candidateId,
        status,
        payload,
      }),
    })
  }

  async triggerNotification(candidateId, status, payload = {}) {
    return this.request('/notifications/trigger', {
      method: 'POST',
      body: JSON.stringify({
        candidate_id: candidateId,
        status,
        payload,
      }),
    })
  }
  // Agencies (Super Admin)
  async getAgencies() {
    return this.request('/agencies')
  }

  async createAgency(data) {
    return this.request('/agencies', { method: 'POST', body: JSON.stringify(data) })
  }

  async updateAgency(id, data) {
    return this.request(`/agencies/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  }

  async deleteAgency(id) {
    return this.request(`/agencies/${id}`, { method: 'DELETE' })
  }
}

export const api = new ApiClient()
export default api

