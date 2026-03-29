import { Badge } from '@/components/ui/badge'
import type { ReorderStatus } from '@/lib/types'

const statusConfig: Record<ReorderStatus, { label: string; className: string }> = {
  lost_sales: { label: 'Lost Sales', className: 'bg-red-200 text-red-800 hover:bg-red-200' },
  urgent: { label: 'Urgent', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
  reorder: { label: 'Reorder', className: 'bg-amber-100 text-amber-700 hover:bg-amber-100' },
  healthy: { label: 'Healthy', className: 'bg-green-100 text-green-700 hover:bg-green-100' },
  dead_stock: { label: 'Dead Stock', className: 'bg-gray-100 text-gray-500 hover:bg-gray-100' },
  out_of_stock: { label: 'Out of Stock', className: 'bg-gray-50 text-gray-400 hover:bg-gray-50' },
  no_data: { label: 'No Data', className: 'bg-gray-50 text-gray-400 hover:bg-gray-50' },
}

export default function StatusBadge({ status }: { status: ReorderStatus }) {
  const config = statusConfig[status] || statusConfig.no_data
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  )
}
