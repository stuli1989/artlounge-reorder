import { Badge } from '@/components/ui/badge'
import type { ReorderStatus } from '@/lib/types'

const statusConfig: Record<ReorderStatus, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
  warning: { label: 'Warning', className: 'bg-amber-100 text-amber-700 hover:bg-amber-100' },
  ok: { label: 'OK', className: 'bg-green-100 text-green-700 hover:bg-green-100' },
  out_of_stock: { label: 'Out of Stock', className: 'bg-red-50 text-red-600 hover:bg-red-50' },
  no_data: { label: 'No Data', className: 'bg-gray-100 text-gray-500 hover:bg-gray-100' },
}

export default function StatusBadge({ status }: { status: ReorderStatus }) {
  const config = statusConfig[status] || statusConfig.no_data
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  )
}
