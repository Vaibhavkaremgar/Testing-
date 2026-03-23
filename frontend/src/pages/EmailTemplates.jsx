import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { Copy, Edit, Mail, Plus, Sparkles, Trash2, Zap } from 'lucide-react'

const TEMPLATE_TYPES = [
  { value: 'general', label: 'General' },
  { value: 'application_received', label: 'Application Received' },
  { value: 'shortlist', label: 'Shortlist' },
  { value: 'interview_invite', label: 'Interview Invite' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejection', label: 'Rejection' },
]

const emptyForm = {
  name: '',
  subject: '',
  body: '',
  template_type: 'general',
  variables: '',
  automation_enabled: false,
  trigger_stage: '',
  description: '',
  is_active: true,
}

export default function EmailTemplates() {
  const [templates, setTemplates] = useState([])
  const [meta, setMeta] = useState({ default_variables: [], candidate_stages: [], can_manage: false })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState(null)
  const [formData, setFormData] = useState(emptyForm)
  const [previewCandidateId, setPreviewCandidateId] = useState('')
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const automationCount = useMemo(
    () => templates.filter((template) => template.automation_enabled && template.is_active).length,
    [templates]
  )

  const fetchData = async () => {
    try {
      const [templateData, metaData] = await Promise.all([
        api.getEmailTemplates(),
        api.getEmailTemplateMeta(),
      ])
      setTemplates(templateData)
      setMeta(metaData)
    } catch (error) {
      console.error('Failed to load email templates:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const resetForm = () => {
    setEditingTemplate(null)
    setFormData(emptyForm)
    setPreview(null)
    setPreviewCandidateId('')
  }

  const handleOpenCreate = () => {
    resetForm()
    setDialogOpen(true)
  }

  const handleEdit = (template) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name || '',
      subject: template.subject || '',
      body: template.body || '',
      template_type: template.template_type || 'general',
      variables: template.variables?.join(', ') || '',
      automation_enabled: !!template.automation_enabled,
      trigger_stage: template.trigger_stage || '',
      description: template.description || '',
      is_active: template.is_active !== false,
    })
    setPreview(null)
    setPreviewCandidateId('')
    setDialogOpen(true)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = {
        ...formData,
        variables: formData.variables.split(',').map((item) => item.trim()).filter(Boolean),
        trigger_stage: formData.automation_enabled ? formData.trigger_stage || null : null,
      }

      if (editingTemplate) {
        await api.updateEmailTemplate(editingTemplate.id, payload)
      } else {
        await api.createEmailTemplate(payload)
      }

      setDialogOpen(false)
      resetForm()
      await fetchData()
    } catch (error) {
      console.error('Failed to save template:', error)
      alert(error.message || 'Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this email template?')) return
    try {
      await api.deleteEmailTemplate(id)
      await fetchData()
    } catch (error) {
      console.error('Failed to delete template:', error)
      alert(error.message || 'Failed to delete template')
    }
  }

  const handleDuplicate = async (template) => {
    try {
      await api.createEmailTemplate({
        name: `${template.name} Copy`,
        subject: template.subject,
        body: template.body,
        template_type: template.template_type,
        variables: template.variables || [],
        automation_enabled: false,
        trigger_stage: null,
        description: template.description || '',
      })
      await fetchData()
    } catch (error) {
      console.error('Failed to duplicate template:', error)
      alert(error.message || 'Failed to duplicate template')
    }
  }

  const handlePreview = async () => {
    if (!editingTemplate?.id || !previewCandidateId) {
      alert('Enter a candidate ID to preview variable replacement.')
      return
    }

    setPreviewLoading(true)
    try {
      const data = await api.previewEmailTemplate(editingTemplate.id, previewCandidateId)
      setPreview(data)
    } catch (error) {
      console.error('Failed to preview template:', error)
      alert(error.message || 'Failed to preview template')
    } finally {
      setPreviewLoading(false)
    }
  }

  const getTypeColor = (type) => {
    const colors = {
      interview_invite: 'bg-blue-100 text-blue-700',
      offer: 'bg-green-100 text-green-700',
      rejection: 'bg-red-100 text-red-700',
      application_received: 'bg-amber-100 text-amber-700',
      shortlist: 'bg-cyan-100 text-cyan-700',
      general: 'bg-slate-100 text-slate-700',
    }
    return colors[type] || colors.general
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1.5fr,1fr]">
        <Card className="border-0 bg-gradient-to-br from-slate-900 via-slate-800 to-cyan-950 text-white shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Mail className="h-6 w-6" />
              Custom Email Templates
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-200">
            <p>Create reusable candidate emails with variables like <span className="font-mono text-cyan-300">{'{{candidate_name}}'}</span> and trigger them automatically when pipeline stages change.</p>
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-white/10 text-white hover:bg-white/10">{templates.length} templates</Badge>
              <Badge className="bg-cyan-400/20 text-cyan-100 hover:bg-cyan-400/20">{automationCount} live automations</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-amber-500" />
              Supported Variables
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {meta.default_variables.map((variable) => (
              <Badge key={variable} variant="outline" className="font-mono text-xs">
                {'{{'}{variable}{'}}'}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Template Library</h1>
          <p className="text-muted-foreground">Manage branded candidate communication and stage-based automation.</p>
        </div>
        {meta.can_manage && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={handleOpenCreate}>
                <Plus className="mr-2 h-4 w-4" />
                New Template
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{editingTemplate ? 'Edit Email Template' : 'Create Email Template'}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="mt-4 space-y-5">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Template Name</label>
                    <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Template Type</label>
                    <Select value={formData.template_type} onValueChange={(value) => setFormData({ ...formData, template_type: value })}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent>
                        {TEMPLATE_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Description</label>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Example: rejection email for candidates who do not clear screening"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Subject</label>
                  <Input value={formData.subject} onChange={(e) => setFormData({ ...formData, subject: e.target.value })} required />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Body</label>
                  <Textarea
                    className="min-h-[220px] font-mono"
                    value={formData.body}
                    onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Variables</label>
                  <Input
                    value={formData.variables}
                    onChange={(e) => setFormData({ ...formData, variables: e.target.value })}
                    placeholder="candidate_name, job_title, company_name"
                  />
                </div>

                <div className="rounded-xl border bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold">Enable Automation</p>
                      <p className="text-sm text-muted-foreground">Automatically send this template when a candidate enters a selected stage.</p>
                    </div>
                    <Switch
                      checked={formData.automation_enabled}
                      onCheckedChange={(checked) => setFormData({ ...formData, automation_enabled: checked })}
                    />
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Trigger Stage</label>
                      <Select
                        value={formData.trigger_stage || '__none__'}
                        onValueChange={(value) => setFormData({ ...formData, trigger_stage: value === '__none__' ? '' : value })}
                        disabled={!formData.automation_enabled}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select stage" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">No trigger</SelectItem>
                          {meta.candidate_stages.map((stage) => (
                            <SelectItem key={stage} value={stage}>{stage}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border bg-white px-3 py-2">
                      <div>
                        <p className="text-sm font-medium">Active Template</p>
                        <p className="text-xs text-muted-foreground">Inactive templates stay saved without being used.</p>
                      </div>
                      <Switch
                        checked={formData.is_active}
                        onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                      />
                    </div>
                  </div>
                </div>

                {editingTemplate && (
                  <div className="rounded-xl border p-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-end">
                      <div className="flex-1 space-y-2">
                        <label className="text-sm font-medium">Preview With Candidate ID</label>
                        <Input
                          value={previewCandidateId}
                          onChange={(e) => setPreviewCandidateId(e.target.value)}
                          placeholder="Paste a candidate UUID"
                        />
                      </div>
                      <Button type="button" variant="outline" onClick={handlePreview} disabled={previewLoading}>
                        {previewLoading ? 'Loading...' : 'Preview Render'}
                      </Button>
                    </div>

                    {preview && (
                      <div className="mt-4 space-y-3 rounded-lg bg-slate-50 p-4">
                        <div>
                          <p className="text-xs text-muted-foreground">Rendered Subject</p>
                          <p className="font-medium">{preview.subject}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Rendered Body</p>
                          <pre className="whitespace-pre-wrap text-sm">{preview.body}</pre>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={saving}>{saving ? 'Saving...' : editingTemplate ? 'Update Template' : 'Create Template'}</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {templates.map((template) => (
          <Card key={template.id} className="overflow-hidden">
            <CardHeader className="border-b bg-slate-50/70">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-lg">{template.name}</CardTitle>
                    {!template.is_active && <Badge variant="secondary">Inactive</Badge>}
                    {template.automation_enabled && <Badge className="bg-cyan-100 text-cyan-700 hover:bg-cyan-100"><Zap className="mr-1 h-3 w-3" />Auto</Badge>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge className={getTypeColor(template.template_type)}>{template.template_type}</Badge>
                    {template.trigger_stage && <Badge variant="outline">Stage: {template.trigger_stage}</Badge>}
                  </div>
                </div>
                {meta.can_manage && (
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => handleDuplicate(template)} title="Duplicate">
                      <Copy className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(template)} title="Edit">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(template.id)} title="Delete">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4 p-5">
              {template.description && <p className="text-sm text-muted-foreground">{template.description}</p>}
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">Subject</p>
                <p className="font-medium">{template.subject}</p>
              </div>
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">Preview</p>
                <p className="line-clamp-4 whitespace-pre-wrap text-sm text-muted-foreground">{template.body}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(template.variables || []).map((variable) => (
                  <Badge key={variable} variant="outline" className="font-mono text-xs">
                    {'{{'}{variable}{'}}'}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {templates.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <Mail className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            <h3 className="text-lg font-semibold">No templates yet</h3>
            <p className="mt-1 text-sm text-muted-foreground">Create your first template to start automating candidate communication.</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
