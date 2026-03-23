import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Eye,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
} from 'lucide-react'

const EMPTY_FORM = {
  name: '',
  status: '',
  subject: '',
  body: '',
  description: '',
  variables: [],
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
  const canManage = isAdmin || isSuperAdmin

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [templates, setTemplates] = useState([])
  const [meta, setMeta] = useState({ statuses: [], placeholders: [], can_manage: false })
  const [agencies, setAgencies] = useState([])
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [selectedAgencyId, setSelectedAgencyId] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const [editingTemplateId, setEditingTemplateId] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [previewStatus, setPreviewStatus] = useState('')
  const [previewPayload, setPreviewPayload] = useState(PREVIEW_PAYLOAD_TEMPLATE)
  const [previewResult, setPreviewResult] = useState(null)

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
      setPreviewStatus(metaResponse.statuses?.[0] || '')
      setFormData((current) => ({
        ...current,
        status: current.status || metaResponse.statuses?.[0] || '',
        variables: current.variables?.length ? current.variables : metaResponse.placeholders || [],
      }))

      if (isSuperAdmin) {
        setAgencies(agencyResponse || [])
      }
    } catch (error) {
      toast({
        title: 'Failed to load email settings',
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

  const openCreateDialog = () => {
    setEditingTemplateId(null)
    setFormData({
      ...EMPTY_FORM,
      status: meta.statuses?.[0] || '',
      variables: meta.placeholders || [],
    })
    setIsDialogOpen(true)
  }

  const openEditDialog = (template) => {
    setEditingTemplateId(template.id)
    setFormData({
      name: template.name || '',
      status: template.status || '',
      subject: template.subject || '',
      body: template.body || '',
      description: template.description || '',
      variables: template.variables || [],
      is_html: template.is_html ?? true,
      is_active: template.is_active ?? true,
    })
    setIsDialogOpen(true)
  }

  const handleSave = async (event) => {
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

      if (editingTemplateId) {
        await api.updateEmailTemplate(editingTemplateId, payload)
      } else {
        await api.createEmailTemplate(payload)
      }

      toast({
        title: editingTemplateId ? 'Template updated' : 'Template created',
        description: 'The email template is ready to use.',
      })

      setIsDialogOpen(false)
      setEditingTemplateId(null)
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

  const handlePreview = async () => {
    if (!previewStatus) {
      toast({
        title: 'Choose a status',
        description: 'Select a recruitment status before previewing.',
        variant: 'destructive',
      })
      return
    }

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
        status: previewStatus,
        payload: parsedPayload,
        user_id: user?.id,
      })
      setPreviewResult(result)
      setIsPreviewOpen(true)
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

  const getTemplateScopeLabel = (template) => {
    if (template.is_default) {
      return 'Default'
    }
    return template.agency_id ? 'Agency' : 'Shared'
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!canManage || meta.can_manage === false) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Email Customization</h1>
          <p className="text-muted-foreground">Template management is available for admins.</p>
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Your account can view recruitment data, but email template management is restricted.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Email Customization</h1>
          <p className="text-muted-foreground">
            Manage status-based notification templates with secure placeholder rendering.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {isSuperAdmin && (
            <Select value={selectedAgencyId || 'all'} onValueChange={(value) => setSelectedAgencyId(value === 'all' ? '' : value)}>
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
          <Button variant="outline" onClick={loadTemplates}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={openCreateDialog}>
            <Plus className="mr-2 h-4 w-4" />
            New Template
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.6fr,1fr]">
        <Card>
          <CardHeader className="gap-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>Templates</CardTitle>
                <CardDescription>
                  Each recruitment status can have an agency-specific template, with default fallback support.
                </CardDescription>
              </div>
              <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                <SelectTrigger className="w-full md:w-[240px]">
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
          </CardHeader>
          <CardContent className="space-y-4">
            {filteredTemplates.length === 0 && (
              <div className="rounded-lg border border-dashed p-8 text-center">
                <p className="text-sm font-medium">No templates found for this scope.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Create an agency template or switch filters to inspect defaults.
                </p>
              </div>
            )}

            {filteredTemplates.map((template) => (
              <div key={template.id} className="rounded-xl border p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">{template.name}</h3>
                      <Badge variant="outline">{template.status}</Badge>
                      <Badge variant={template.is_active ? 'default' : 'secondary'}>
                        {template.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      <Badge variant="secondary">{getTemplateScopeLabel(template)}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{template.description || 'No description added yet.'}</p>
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Subject</p>
                      <p className="mt-1 text-sm">{template.subject}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Body Preview</p>
                      <div className="mt-1 max-h-24 overflow-hidden whitespace-pre-wrap text-sm text-muted-foreground">
                        {template.body}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(template)}>
                      <Pencil className="mr-2 h-4 w-4" />
                      Edit
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Supported Placeholders
              </CardTitle>
              <CardDescription>
                These variables can be used in your subject or body. The backend replaces them securely at send time.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {meta.placeholders.map((placeholder) => (
                <Badge key={placeholder} variant="outline" className="font-mono text-xs">
                  {placeholder}
                </Badge>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-primary" />
                Preview Renderer
              </CardTitle>
              <CardDescription>
                Test a status against sample payload data and see the rendered result before sending.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Recruitment Status</Label>
                <Select value={previewStatus} onValueChange={setPreviewStatus}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a status" />
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
              <div className="space-y-2">
                <Label>Preview Payload JSON</Label>
                <Textarea
                  className="min-h-[260px] font-mono text-xs"
                  value={previewPayload}
                  onChange={(event) => setPreviewPayload(event.target.value)}
                />
              </div>
              <Button className="w-full" onClick={handlePreview} disabled={previewLoading}>
                {previewLoading ? 'Rendering Preview...' : 'Render Preview'}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingTemplateId ? 'Edit Email Template' : 'Create Email Template'}</DialogTitle>
            <DialogDescription>
              Build a recruitment-status template for {isSuperAdmin ? 'the selected agency scope' : 'your agency'}.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSave} className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="template-name">Template Name</Label>
                <Input
                  id="template-name"
                  value={formData.name}
                  onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                  placeholder="Shortlisted Candidate Email"
                />
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={formData.status} onValueChange={(value) => setFormData({ ...formData, status: value })}>
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
              <Label htmlFor="template-description">Description</Label>
              <Input
                id="template-description"
                value={formData.description}
                onChange={(event) => setFormData({ ...formData, description: event.target.value })}
                placeholder="Used when a resume passes AI screening."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-subject">Subject</Label>
              <Input
                id="template-subject"
                value={formData.subject}
                onChange={(event) => setFormData({ ...formData, subject: event.target.value })}
                placeholder="Your profile is shortlisted for {{job_title}}"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-body">Body</Label>
              <Textarea
                id="template-body"
                className="min-h-[260px] whitespace-pre-wrap font-mono text-sm"
                value={formData.body}
                onChange={(event) => setFormData({ ...formData, body: event.target.value })}
                placeholder={`Hi {{candidate_name}},\n\nWe are pleased to move you forward for {{job_title}}.\nUse this slot link: {{slot_link}}`}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div>
                  <p className="text-sm font-medium">Send as HTML</p>
                  <p className="text-xs text-muted-foreground">Enable HTML formatting for branded emails.</p>
                </div>
                <Switch
                  checked={formData.is_html}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_html: checked })}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div>
                  <p className="text-sm font-medium">Template Active</p>
                  <p className="text-xs text-muted-foreground">Inactive templates stay stored but should not be used.</p>
                </div>
                <Switch
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                />
              </div>
            </div>

            <div className="rounded-lg bg-muted/50 p-4">
              <p className="text-sm font-medium">Available placeholders</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {meta.placeholders.map((placeholder) => (
                  <Badge key={placeholder} variant="outline" className="font-mono text-xs">
                    {placeholder}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                <Save className="mr-2 h-4 w-4" />
                {saving ? 'Saving...' : editingTemplateId ? 'Update Template' : 'Create Template'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              Rendered Email Preview
            </DialogTitle>
            <DialogDescription>
              This shows the final template after placeholders are replaced by backend payload values.
            </DialogDescription>
          </DialogHeader>

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
        </DialogContent>
      </Dialog>
    </div>
  )
}
