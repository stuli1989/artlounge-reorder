import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

const STATUS_BORDER: Record<string, string> = {
  urgent: 'border-l-red-500',
  reorder: 'border-l-amber-500',
  healthy: 'border-l-green-500',
  lost_sales: 'border-l-red-600',
  dead_stock: 'border-l-gray-400',
  out_of_stock: 'border-l-gray-400',
  no_data: 'border-l-gray-400',
}

const STATUS_BADGE: Record<string, string> = {
  urgent: 'bg-red-900/60 text-red-300',
  reorder: 'bg-amber-900/60 text-amber-300',
  healthy: 'bg-green-900/60 text-green-300',
  lost_sales: 'bg-red-900/80 text-red-200',
  dead_stock: 'bg-gray-800 text-gray-400',
  out_of_stock: 'bg-gray-800 text-gray-400',
  no_data: 'bg-gray-800 text-gray-400',
}

interface MobileListRowProps {
  title: string
  subtitle?: string
  status?: string
  statusLabel?: string
  metrics?: { label: string; value: string; color?: string }[]
  badges?: ReactNode
  onClick?: () => void
  rightContent?: ReactNode
  className?: string
  children?: ReactNode
}

export function MobileListRow({
  title,
  subtitle,
  status,
  statusLabel,
  metrics,
  badges,
  onClick,
  rightContent,
  className,
  children,
}: MobileListRowProps) {
  const borderClass = status ? STATUS_BORDER[status] ?? 'border-l-gray-300' : 'border-l-transparent'

  return (
    <div
      className={cn(
        'border-l-[3px] px-4 py-3 border-b border-border/50 active:bg-muted/50 transition-colors',
        borderClass,
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <div className="min-w-0 flex-1">
          <span className="font-semibold text-sm truncate block">{title}</span>
          {subtitle && (
            <span className="text-xs text-muted-foreground">{subtitle}</span>
          )}
        </div>
        {statusLabel && status && (
          <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap', STATUS_BADGE[status] ?? 'bg-gray-800 text-gray-400')}>
            {statusLabel}
          </span>
        )}
        {rightContent}
      </div>
      {(metrics || badges) && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
          {metrics?.map((m, i) => (
            <span key={i}>
              {m.label}: <b className={cn('text-foreground', m.color)}>{m.value}</b>
            </span>
          ))}
          {badges}
        </div>
      )}
      {children}
    </div>
  )
}

export function MobileListRowSkeleton() {
  return (
    <div className="border-l-[3px] border-l-transparent px-4 py-3 border-b border-border/50 animate-pulse">
      <div className="flex items-center justify-between mb-1">
        <div className="h-4 w-48 bg-muted rounded" />
        <div className="h-4 w-16 bg-muted rounded-full" />
      </div>
      <div className="flex gap-3">
        <div className="h-3 w-16 bg-muted rounded" />
        <div className="h-3 w-16 bg-muted rounded" />
        <div className="h-3 w-16 bg-muted rounded" />
      </div>
    </div>
  )
}
