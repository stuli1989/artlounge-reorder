import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { fetchPositions } from '@/lib/api'

interface Props {
  categoryName: string
  stockItemName: string
}

export default function StockTimelineChart({ categoryName, stockItemName }: Props) {
  const { data: positions, isLoading } = useQuery({
    queryKey: ['positions', categoryName, stockItemName],
    queryFn: () => fetchPositions(categoryName, stockItemName),
  })

  // Sample data for performance (every 3rd day if > 100 points)
  // Must be before early returns to satisfy rules of hooks
  const chartData = useMemo(() => {
    if (!positions?.length) return []
    return positions.length > 100
      ? positions.filter((_, i) => i % 3 === 0 || i === positions.length - 1)
      : positions
  }, [positions])

  if (isLoading) return <div className="h-[200px] flex items-center justify-center text-muted-foreground">Loading chart...</div>
  if (!chartData.length) return <div className="h-[200px] flex items-center justify-center text-muted-foreground">No position data</div>

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <XAxis
          dataKey="position_date"
          tickFormatter={(v: string) => new Date(v).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}
          fontSize={11}
          tick={{ fill: '#888' }}
          interval="preserveStartEnd"
        />
        <YAxis fontSize={11} tick={{ fill: '#888' }} />
        <Tooltip
          labelFormatter={(v) => new Date(String(v)).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}
          formatter={(value, name) => {
            const labels: Record<string, string> = {
              closing_qty: 'Stock',
              inward_qty: 'In',
              outward_qty: 'Out',
            }
            return [value, labels[String(name)] || String(name)]
          }}
        />
        <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" />
        <Area
          type="monotone"
          dataKey="closing_qty"
          stroke="#3b82f6"
          fill="#93c5fd"
          fillOpacity={0.3}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
