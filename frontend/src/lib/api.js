const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : 'https://ai-recruitment-dashboard-production.up.railway.app/api'
const RECORDING_API_BASE = import.meta.env.VITE_RECORDING_API_URL || 'https://pontis-backend-production.up.railway.app/api'
const DEFAULT_LIST_LIMIT = 100

// Debug logging
console.log('VITE_API_URL:', import.meta.env.VITE_API_URL)
console.log('API_BASE:', API_BASE)

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('token')
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

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`
    const headers = {
      ...options.headers,
    }

    if (this.getToken()) {
      headers['Authorization'] = `Bearer ${this.getToken()}`
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      // Don't auto-logout, just throw error
      throw new Error('Unauthorized')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }))
      throw new Error(error.detail || 'An error occurred')
    }

    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return response.json()
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

  // Auth
  async login(email, password) {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)

    const loginUrl = `${API_BASE}/auth/login`
    console.log('Login URL:', loginUrl)

    try {
      const response = await fetch(loginUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      })

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

  async getAllUsers() {
    return this.request('/auth/users')
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
  async getCandidates(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params.limit ? params : { ...params, limit: DEFAULT_LIST_LIMIT }).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/candidates${query ? `?${query}` : ''}`)
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

  async updateCandidateStage(id, stage) {
    return this.request(`/candidates/${id}/stage`, {
      method: 'PATCH',
      body: JSON.stringify({ stage }),
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
    return this.request(`/candidates/upload-progress/${uploadId}`)
  }

  async getPipelineStages(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/candidates/pipeline/stages${query ? `?${query}` : ''}`)
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
  async getJobs(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params.limit ? params : { ...params, limit: DEFAULT_LIST_LIMIT }).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    })
    const query = searchParams.toString()
    return this.request(`/jobs${query ? `?${query}` : ''}`)
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
  async getInterviews(params = {}) {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
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

  async getResumeScoresTrend() {
    return this.request('/analytics/resume-scores-trend')
  }

  async getInterviewScoresTrend() {
    return this.request('/analytics/interview-scores-trend')
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

  async getActiveJobs() {
    return this.request('/analytics/active-jobs')
  }

  async getUpcomingInterviews() {
    return this.request('/analytics/upcoming-interviews')
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

  getInterviewVideoUrl(sessionId) {
    const token = this.getToken()
    const encodedSessionId = encodeURIComponent(sessionId)
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    return `${API_BASE}/interviews/video/${encodedSessionId}${query}`
  }

  getExternalInterviewRecordingUrl(interviewId) {
    const encodedInterviewId = encodeURIComponent(interviewId)
    return `${RECORDING_API_BASE}/recording/${encodedInterviewId}`
  }

  getInterviewRecordingUrl(sessionId) {
    return this.getInterviewVideoUrl(sessionId)
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

