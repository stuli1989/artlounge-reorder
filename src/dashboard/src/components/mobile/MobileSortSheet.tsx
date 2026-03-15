import { BottomSheet } from '@/components/mobile/BottomSheet'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SortOption {
  value: string
  label: string
}

interface MobileSortSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  options: SortOption[]
  value: string
  direction: 'asc' | 'desc'
  onSort: (value: string) => void
  onToggleDirection: () => void
}

export function MobileSortSheet({
  open,
  onOpenChange,
  options,
  value,
  direction,
  onSort,
  onToggleDirection,
}: MobileSortSheetProps) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Sort by">
      <div className="space-y-1">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => {
              onSort(opt.value)
              onOpenChange(false)
            }}
            className={cn(
              'w-full text-left px-3 py-2.5 rounded-lg text-sm flex items-center justify-between transition-colors',
              value === opt.value ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
            )}
          >
            {opt.label}
            {value === opt.value && <Check className="h-4 w-4" />}
          </button>
        ))}
      </div>
      <button
        onClick={onToggleDirection}
        className="w-full mt-3 px-3 py-2.5 rounded-lg text-sm bg-muted text-center"
      >
        Direction: {direction === 'asc' ? '\u2191 Ascending' : '\u2193 Descending'}
      </button>
    </BottomSheet>
  )
}
