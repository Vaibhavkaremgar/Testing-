import { useEffect, useMemo, useState } from 'react'
import { CalendarIcon, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn, formatDateRangeLabel, getDateRangePreset } from '@/lib/utils'

const PRESETS = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: 'last_7_days', label: 'Last 7 days' },
  { id: 'last_30_days', label: 'Last 30 days' },
  { id: 'custom', label: 'Custom Range' },
]

export default function DateRangeFilter({
  value,
  onChange,
  className,
  buttonClassName,
  align = 'end',
}) {
  const [open, setOpen] = useState(false)
  const [draftRange, setDraftRange] = useState(value || getDateRangePreset('last_7_days'))

  useEffect(() => {
    setDraftRange(value || getDateRangePreset('last_7_days'))
  }, [value])

  const hasActiveRange = Boolean(value?.from && value?.to)
  const label = useMemo(() => formatDateRangeLabel(value), [value])

  const applyPreset = (presetId) => {
    const presetRange = getDateRangePreset(presetId)
    setDraftRange(presetRange)
    if (presetId !== 'custom') {
      onChange?.(presetRange)
      setOpen(false)
    }
  }

  const applyCustomRange = () => {
    if (!draftRange?.from || !draftRange?.to) return
    onChange?.({
      preset: 'custom',
      from: draftRange.from,
      to: draftRange.to,
    })
    setOpen(false)
  }

  const clearRange = () => {
    const defaultRange = getDateRangePreset('last_7_days')
    setDraftRange(defaultRange)
    onChange?.(defaultRange)
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className={cn('w-[250px] justify-start text-left font-normal', buttonClassName)}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            <span className="truncate">{label}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align={align} className="w-[320px] p-4">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {PRESETS.map((preset) => (
                <Button
                  key={preset.id}
                  type="button"
                  variant={draftRange?.preset === preset.id ? 'default' : 'outline'}
                  size="sm"
                  className="justify-start"
                  onClick={() => applyPreset(preset.id)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">From</label>
                <Input
                  type="date"
                  value={draftRange?.from || ''}
                  onChange={(event) => setDraftRange((currentValue) => ({
                    ...(currentValue || getDateRangePreset('custom')),
                    preset: 'custom',
                    from: event.target.value,
                  }))}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">To</label>
                <Input
                  type="date"
                  value={draftRange?.to || ''}
                  min={draftRange?.from || undefined}
                  onChange={(event) => setDraftRange((currentValue) => ({
                    ...(currentValue || getDateRangePreset('custom')),
                    preset: 'custom',
                    to: event.target.value,
                  }))}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Close
              </Button>
              <Button
                type="button"
                onClick={applyCustomRange}
                disabled={!draftRange?.from || !draftRange?.to}
              >
                Apply
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {hasActiveRange ? (
        <Button type="button" variant="ghost" size="icon" onClick={clearRange}>
          <X className="h-4 w-4" />
        </Button>
      ) : null}
    </div>
  )
}
