import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { LoadingCard } from '@/components/ui/loading'
import { cn } from '@/lib/utils'

export default function ExpandableList({
  items = [],
  initialCount = 5,
  loading = false,
  className,
  listClassName,
  controlsClassName,
  buttonVariant = 'outline',
  emptyState = null,
  loadingMessage = 'Loading...',
  showMoreLabel,
  showLessLabel = 'Show Less',
  renderItems,
  renderItem,
  getItemKey,
}) {
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setExpanded(false)
  }, [items, initialCount])

  const visibleItems = useMemo(() => {
    if (expanded) return items
    return items.slice(0, initialCount)
  }, [expanded, initialCount, items])

  const remainingCount = Math.max(items.length - initialCount, 0)
  const canExpand = items.length > initialCount
  const resolvedShowMoreLabel = showMoreLabel || `Show More (${remainingCount} remaining)`

  if (loading) {
    return <LoadingCard message={loadingMessage} className={className} />
  }

  if (!items.length) {
    return emptyState ? <div className={className}>{emptyState}</div> : null
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div className={listClassName}>
        {typeof renderItems === 'function'
          ? renderItems({ items: visibleItems, expanded })
          : visibleItems.map((item, index) => (
            <div key={getItemKey ? getItemKey(item, index) : index}>
              {renderItem ? renderItem(item, index) : null}
            </div>
          ))}
      </div>

      {canExpand ? (
        <div className={cn('flex justify-center', controlsClassName)}>
          <Button
            type="button"
            variant={buttonVariant}
            onClick={() => setExpanded((currentValue) => !currentValue)}
          >
            {expanded ? showLessLabel : resolvedShowMoreLabel}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
