import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Eye,
  Mail,
  Pencil,
  Plus,
  Save,
} from 'lucide-react'

const EMPTY_FORM = {
  name: '',
  status: '',
  subject: '',
  body: '',
  description: '',
  is_html: true,
  is_active: true,
}

const PREVIEW_PAYLOAD_TEMPLATE = `{
  "candidate_name": "Ava Johnson",
  "candidate_id": "CAND-001",
  "job_id": "JOB-101",
  "job_title": "Senior AI Recruiter",
  "job_role": "AI Recruiter",
  "job_description": "Lead AI-driven recruitment workflows and candidate experience.",
  "skills": "FastAPI, React, Screening, Stakeholder Management",
  "resume_text": "8 years in technical recruitment with ML hiring specialization.",
  "agency_id": "agency-demo",
  "user_id": "user-demo",
  "slot_link": "https://example.com/slot-selection?token=demo",
  "meeting_link": "https://example.com/interview-room?token=demo",
  "interview_date": "2026-03-28",
  "interview_time": "14:30"
}`

export default function EmailTemplates() {
  const { user } = useAuth()
  const { toast } = useToast()
  const isAdmin = user?.role === 'admin'
  const isSuperAdmin = user?.role === 'super_admin'
  const isRegularUser = !isAdmin && !isSuperAdmin
  const canManage = isRegularUser

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [templates, setTemplates] = useState([])
  const [agencies, setAgencies] = useState([])
  const [meta, setMeta] = useState({ statuses: [], placeholders: [], can_manage: false })
  const [selectedAgencyId, setSelectedAgencyId] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [editingTemplate, setEditingTemplate] = useState(null)
  const [previewTemplate, setPreviewTemplate] = useState(null)
  const [previewPayload, setPreviewPayload] = useState(PREVIEW_PAYLOAD_TEMPLATE)
  const [previewResult, setPreviewResult] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)

  const effectiveAgencyId = useMemo(() => {
    if (isSuperAdmin) {
      return selectedAgencyId || undefined
    }
    return user?.agency_id || undefined
  }, [isSuperAdmin, selectedAgencyId, user?.agency_id])

  const filteredTemplates = useMemo(() => {
    if (selectedStatus === 'all') {
      return templates
    }
    return templates.filter((template) => template.status === selectedStatus)
  }, [selectedStatus, templates])

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    if (!loading) {
      loadTemplates()
    }
  }, [selectedAgencyId])

  const loadInitialData = async () => {
    try {
      const [metaResponse, agencyResponse] = await Promise.all([
        api.getEmailTemplateMeta(),
        isSuperAdmin ? api.getAgencies() : Promise.resolve([]),
      ])

      setMeta(metaResponse)
      setFormData((current) => ({
        ...current,
        status: current.status || metaResponse.statuses?.[0] || '',
      }))

      if (isSuperAdmin) {
        setAgencies(agencyResponse || [])
      }
    } catch (error) {
      toast({
        title: 'Failed to load email templates',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
      loadTemplates()
    }
  }

  const loadTemplates = async () => {
    try {
      const data = await api.getEmailTemplates({
        agency_id: effectiveAgencyId,
      })
      setTemplates(data)
    } catch (error) {
      toast({
        title: 'Failed to load templates',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      })
    }
  }

  const resetForm = () => {
    setFormData({
      ...EMPTY_FORM,
      status: meta.statuses?.[0] || '',
    })
  }

  const openCreateDialog = () => {
    setEditingTemplate(null)
    resetForm()
    setDialogOpen(true)
  }

  const openEditDialog = (template) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name || '',
      status: template.status || '',
      subject: template.subject || '',
      body: template.body || '',
      description: template.description || '',
      is_html: template.is_html ?? true,
      is_active: template.is_active ?? true,
    })
    setDialogOpen(true)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (!formData.name.trim() || !formData.status || !formData.subject.trim() || !formData.body.trim()) {
      toast({
        title: 'Missing required fields',
        description: 'Name, status, subject, and body are required.',
        variant: 'destructive',
      })
      return
    }

    setSaving(true)
    try {
      const payload = {
        ...formData,
        agency_id: effectiveAgencyId,
        variables: meta.placeholders || [],
      }

      if (editingTemplate) {
        await api.updateEmailTemplate(editingTemplate.id, payload)
      } else {
        await api.createEmailTemplate(payload)
      }

      toast({
        title: editingTemplate ? 'Template updated' : 'Template created',
        description: 'The email template has been saved successfully.',
      })

      setDialogOpen(false)
      setEditingTemplate(null)
      resetForm()
      await loadTemplates()
    } catch (error) {
      toast({
        title: 'Could not save template',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  const openPreview = async (template) => {
    setPreviewTemplate(template)
    setPreviewResult(null)
    setPreviewOpen(true)
    await renderPreview(template.status)
  }

  const renderPreview = async (status) => {
    let parsedPayload = {}

    try {
      parsedPayload = previewPayload.trim() ? JSON.parse(previewPayload) : {}
    } catch {
      toast({
        title: 'Invalid preview payload',
        description: 'Preview payload must be valid JSON.',
        variant: 'destructive',
      })
      return
    }

    setPreviewLoading(true)
    try {
      const result = await api.previewEmailTemplate({
        agency_id: effectiveAgencyId,
        status,
        payload: parsedPayload,
        user_id: user?.id,
      })
      setPreviewResult(result)
    } catch (error) {
      toast({
        title: 'Preview failed',
        description: error.message || 'Please try again.',
        variant: 'destructive',
      })
    } finally {
      setPreviewLoading(false)
    }
  }

  const getScopeLabel = (template) => {
    if (template.is_default) return 'Default'
    if (template.agency_id) return 'Agency'
    return 'Shared'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!canManage || meta.can_manage === false) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Email Customization</h1>
          <p className="text-muted-foreground">Template management is available for users only.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Email Customization</h1>
          <p className="text-muted-foreground">Manage recruitment email templates by status</p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreateDialog}>
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingTemplate ? 'Edit Template' : 'Create New Template'}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Template Name *</Label>
                  <Input
                    value={formData.name}
                    onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Status *</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value) => setFormData({ ...formData, status: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      {meta.statuses.map((status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={formData.description}
                  onChange={(event) => setFormData({ ...formData, description: event.target.value })}
                  placeholder="Used when a resume is shortlisted."
                />
              </div>

              <div className="space-y-2">
                <Label>Subject *</Label>
                <Input
                  value={formData.subject}
                  onChange={(event) => setFormData({ ...formData, subject: event.target.value })}
                  placeholder="Your profile is shortlisted for {{job_title}}"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Body *</Label>
                <Textarea
                  className="min-h-[220px] font-mono text-sm"
                  value={formData.body}
                  onChange={(event) => setFormData({ ...formData, body: event.target.value })}
                  placeholder={`Hi {{candidate_name}},\n\nWe are pleased to move you forward for {{job_title}}.\nUse this slot link: {{slot_link}}`}
                  required
                />
              </div>

              <div className="rounded-lg border p-4 space-y-3">
                <p className="text-sm font-medium">Supported placeholders</p>
                <div className="flex flex-wrap gap-2">
                  {meta.placeholders.map((placeholder) => (
                    <Badge key={placeholder} variant="outline" className="text-xs font-mono">
                      {placeholder}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div>
                    <p className="text-sm font-medium">HTML Template</p>
                    <p className="text-xs text-muted-foreground">Enable richer formatting</p>
                  </div>
                  <Switch
                    checked={formData.is_html}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_html: checked })}
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div>
                    <p className="text-sm font-medium">Active</p>
                    <p className="text-xs text-muted-foreground">Template can be used automatically</p>
                  </div>
                  <Switch
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={saving}>
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? 'Saving...' : editingTemplate ? 'Update Template' : 'Create Template'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row">
          {isSuperAdmin && (
            <Select
              value={selectedAgencyId || 'all'}
              onValueChange={(value) => setSelectedAgencyId(value === 'all' ? '' : value)}
            >
              <SelectTrigger className="w-full sm:w-[240px]">
                <SelectValue placeholder="Choose agency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All agencies</SelectItem>
                {agencies.map((agency) => (
                  <SelectItem key={agency.id} value={agency.id}>
                    {agency.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Select value={selectedStatus} onValueChange={setSelectedStatus}>
            <SelectTrigger className="w-full sm:w-[240px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {meta.statuses.map((status) => (
                <SelectItem key={status} value={status}>
                  {status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredTemplates.map((template) => (
          <Card key={template.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <CardTitle className="text-base">{template.name}</CardTitle>
                  <p className="text-xs text-muted-foreground font-mono mt-0.5">{template.status}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {template.description || 'No description added'}
                  </p>
                </div>
                <Badge variant={template.is_active ? 'default' : 'secondary'}>
                  {template.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span className="truncate">{template.subject}</span>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{getScopeLabel(template)}</Badge>
                <Badge variant="secondary">{template.is_html ? 'HTML' : 'Text'}</Badge>
              </div>

              <div className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground whitespace-pre-wrap line-clamp-4 min-h-[112px]">
                {template.body}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <Button variant="outline" size="sm" onClick={() => openPreview(template)}>
                  <Eye className="h-4 w-4 mr-2" />
                  Preview
                </Button>
                <Button variant="outline" size="sm" onClick={() => openEditDialog(template)}>
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredTemplates.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm font-medium">No templates found.</p>
            <p className="text-sm text-muted-foreground mt-1">
              Create a new template or change the current filters.
            </p>
          </CardContent>
        </Card>
      )}

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Preview Template</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div className="space-y-2">
              <Label>Preview Payload JSON</Label>
              <Textarea
                className="min-h-[220px] font-mono text-xs"
                value={previewPayload}
                onChange={(event) => setPreviewPayload(event.target.value)}
              />
            </div>

            <div className="flex justify-end">
              <Button
                variant="outline"
                onClick={() => previewTemplate && renderPreview(previewTemplate.status)}
                disabled={previewLoading || !previewTemplate}
              >
                {previewLoading ? 'Rendering...' : 'Render Again'}
              </Button>
            </div>

            {previewResult && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">Template #{previewResult.template_id || 'N/A'}</Badge>
                  <Badge variant={previewResult.used_default_template ? 'secondary' : 'default'}>
                    {previewResult.used_default_template ? 'Default Fallback Used' : 'Agency Template Used'}
                  </Badge>
                </div>

                <div className="space-y-2">
                  <Label>Subject</Label>
                  <div className="rounded-lg border p-3 text-sm">{previewResult.subject}</div>
                </div>

                <div className="space-y-2">
                  <Label>Body</Label>
                  <div className="rounded-lg border p-3 text-sm whitespace-pre-wrap">
                    {previewResult.body}
                  </div>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
