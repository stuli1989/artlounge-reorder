import { BottomSheet } from '@/components/mobile/BottomSheet'
import { X } from 'lucide-react'

export interface FilterChip {
  key: string
  label: string
  onRemove: () => void
}

interface FilterDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function FilterDrawer({ open, onOpenChange, children }: FilterDrawerProps) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Filters">
      <div className="space-y-4">{children}</div>
    </BottomSheet>
  )
}

export function FilterChips({ chips }: { chips: FilterChip[] }) {
  if (chips.length === 0) return null
  return (
    <div className="flex gap-1.5 flex-wrap">
      {chips.map((chip) => (
        <button
          key={chip.key}
          onClick={chip.onRemove}
          className="inline-flex items-center gap-1 bg-primary/20 text-primary text-xs px-2.5 py-1 rounded-full"
        >
          {chip.label}
          <X className="h-3 w-3 opacity-60" />
        </button>
      ))}
    </div>
  )
}

export function FilterButton({
  activeCount,
  onClick,
}: {
  activeCount: number
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="bg-muted rounded-lg px-3 py-2.5 text-xs flex items-center gap-1.5"
    >
      Filters
      {activeCount > 0 && (
        <span className="bg-primary text-primary-foreground text-[9px] rounded-full w-4 h-4 flex items-center justify-center font-semibold">
          {activeCount}
        </span>
      )}
    </button>
  )
}
