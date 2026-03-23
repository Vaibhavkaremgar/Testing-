import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { api } from '@/lib/api'
import { Plus, Mail, Edit, Trash2, Copy } from 'lucide-react'

export default function EmailTemplates() {
  const [templates, setTemplates] = useState([])
  const [availableVariables, setAvailableVariables] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    subject: '',
    body: '',
    template_type: 'resume_shortlisted_slot_selection',
    variables: ''
  })

  const templateTypeOptions = [
    { value: 'resume_shortlisted_slot_selection', label: 'Resume Shortlisted With Slot Selection' },
    { value: 'resume_rejected', label: 'Resume Rejected' },
    { value: 'interview_scheduled', label: 'Interview Scheduled' },
    { value: 'selected', label: 'Selected' },
    { value: 'rejected', label: 'Rejected' },
  ]

  const fetchTemplates = async () => {
    try {
      const data = await api.getEmailTemplates()
      setTemplates(data)
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
    api.getEmailTemplateVariables()
      .then((data) => setAvailableVariables(data.variables || []))
      .catch(() => setAvailableVariables([]))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const templateData = {
        ...formData,
        variables: formData.variables.split(',').map(s => s.trim()).filter(Boolean)
      }
      
      if (editingTemplate) {
        await api.updateEmailTemplate(editingTemplate.id, templateData)
      } else {
        await api.createEmailTemplate(templateData)
      }
      
      setDialogOpen(false)
      setEditingTemplate(null)
      setFormData({ name: '', subject: '', body: '', template_type: 'resume_shortlisted_slot_selection', variables: '' })
      await fetchTemplates()
    } catch (error) {
      console.error('Failed to save template:', error)
    }
  }

  const handleEdit = (template) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      subject: template.subject,
      body: template.body,
      template_type: template.template_type,
      variables: template.variables?.join(', ') || ''
    })
    setDialogOpen(true)
  }

  const handleDelete = async (id) => {
    if (confirm('Are you sure you want to delete this template?')) {
      try {
        await api.deleteEmailTemplate(id)
        await fetchTemplates()
      } catch (error) {
        console.error('Failed to delete template:', error)
      }
    }
  }

  const getTypeColor = (type) => {
    const colors = {
      interview_invite: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      offer: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      rejection: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
      application_received: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
      resume_shortlisted_slot_selection: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      resume_rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
      interview_scheduled: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      selected: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
      rejected: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
      general: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    }
    return colors[type] || colors.general
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
          <h1 className="text-2xl font-bold">Email Templates</h1>
          <p className="text-muted-foreground">Manage agency-specific templates for automated and user-triggered candidate emails</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => {
              setEditingTemplate(null)
              setFormData({ name: '', subject: '', body: '', template_type: 'resume_shortlisted_slot_selection', variables: '' })
            }}>
              <Plus className="h-4 w-4 mr-2" />
              Add Template
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingTemplate ? 'Edit Template' : 'Create New Template'}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Template Name *</label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Type</label>
                  <select
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    value={formData.template_type}
                    onChange={(e) => setFormData({ ...formData, template_type: e.target.value })}
                  >
                    {templateTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Subject *</label>
                <Input
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Body *</label>
                <textarea
                  className="flex min-h-[200px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
                  value={formData.body}
                  onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Candidate and job details are auto-filled using placeholders like {'{{candidate_name}}'} and {'{{job_title}}'}
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Variables (comma-separated)</label>
                <Input
                  value={formData.variables}
                  onChange={(e) => setFormData({ ...formData, variables: e.target.value })}
                  placeholder="candidate_name, job_title, interview_date"
                />
              </div>
              {availableVariables.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Available Variables</label>
                  <div className="flex flex-wrap gap-2">
                    {availableVariables.map((variable) => (
                      <Badge key={variable} variant="outline" className="text-xs font-mono">
                        {'{{'}{variable}{'}}'}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">
                  {editingTemplate ? 'Update' : 'Create'} Template
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {templates.map((template) => (
          <Card key={template.id}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Mail className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-base">{template.name}</CardTitle>
                    <Badge className={getTypeColor(template.template_type)}>
                      {template.template_type.replace('_', ' ')}
                    </Badge>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => handleEdit(template)}>
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(template.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Subject</p>
                <p className="text-sm font-medium">{template.subject}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Preview</p>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {template.body}
                </p>
              </div>
              {template.variables?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {template.variables.map((variable) => (
                    <Badge key={variable} variant="outline" className="text-xs font-mono">
                      {'{{'}{variable}{'}}'}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
