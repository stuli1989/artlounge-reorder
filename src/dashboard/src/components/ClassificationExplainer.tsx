import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBrandSummary } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { HelpCircle } from 'lucide-react'
import AbcBadge from '@/components/AbcBadge'
import XyzBadge from '@/components/XyzBadge'

export default function ClassificationExplainer() {
  const [open, setOpen] = useState(false)
  const { data: summary } = useQuery({
    queryKey: ['brandSummary'],
    queryFn: fetchBrandSummary,
    enabled: open,
  })

  const a = summary?.total_a_class_skus ?? 0
  const b = summary?.total_b_class_skus ?? 0
  const c = summary?.total_c_class_skus ?? 0
  const total = a + b + c || 1

  const bufferMatrix = [
    ['', 'X (Steady)', 'Y (Variable)', 'Z (Sporadic)'],
    ['A (80% rev)', '1.3x', '1.5x', '1.8x'],
    ['B (15% rev)', '1.2x', '1.3x', '1.5x'],
    ['C (5% rev)', '1.1x', '1.2x', '1.3x'],
  ]

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground" />
        }
      >
        <HelpCircle className="h-4 w-4" />
        <span className="hidden sm:inline">Learn more</span>
      </SheetTrigger>
      <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Classification Guide</SheetTitle>
        </SheetHeader>

        <div className="space-y-6 mt-4 text-sm">
          {/* ABC */}
          <section>
            <h3 className="font-semibold mb-2">ABC Classification (Revenue)</h3>
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <AbcBadge value="A" />
                <span>Top 80% of revenue — {a.toLocaleString()} items ({((a / total) * 100).toFixed(0)}%). Stockout here costs ~50x more than C-class.</span>
              </div>
              <div className="flex items-start gap-2">
                <AbcBadge value="B" />
                <span>Next 15% of revenue — {b.toLocaleString()} items ({((b / total) * 100).toFixed(0)}%). Order regularly.</span>
              </div>
              <div className="flex items-start gap-2">
                <AbcBadge value="C" />
                <span>Bottom 5% + zero revenue — {c.toLocaleString()} items ({((c / total) * 100).toFixed(0)}%). Minimal buffers.</span>
              </div>
            </div>
          </section>

          {/* XYZ */}
          <section>
            <h3 className="font-semibold mb-2">XYZ Classification (Demand Predictability)</h3>
            <p className="text-muted-foreground mb-2">
              CV = coefficient of variation = how "spiky" demand is relative to the average.
            </p>
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <XyzBadge value="X" />
                <span>CV &lt; 0.5 — Steady weekly demand, easy to forecast.</span>
              </div>
              <div className="flex items-start gap-2">
                <XyzBadge value="Y" />
                <span>CV 0.5–1.0 — Moderate swings week to week.</span>
              </div>
              <div className="flex items-start gap-2">
                <XyzBadge value="Z" />
                <span>CV &gt; 1.0 — Demand in bursts. Some weeks nothing, then a big order.</span>
              </div>
            </div>
            <p className="text-muted-foreground mt-2 text-xs">
              Most art supplies are Z-class. This is normal — demand comes from workshops, wholesale orders, and seasonal buying.
            </p>
          </section>

          {/* Buffer Matrix */}
          <section>
            <h3 className="font-semibold mb-2">Safety Buffer Matrix</h3>
            <p className="text-muted-foreground mb-2 text-xs">
              Higher buffer = order more. A+Z gets 1.8x because it's high-revenue AND unpredictable.
            </p>
            <table className="w-full text-xs border-collapse">
              <tbody>
                {bufferMatrix.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        className={`border px-2 py-1.5 ${i === 0 || j === 0 ? 'font-medium bg-muted' : ''}`}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Trends */}
          <section>
            <h3 className="font-semibold mb-2">Trend Arrows</h3>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-green-600 font-medium">↗</span>
                <span>Recent 90-day demand &gt; yearly average (ratio &gt; 1.2)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400 font-medium">→</span>
                <span>Recent ≈ yearly average</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-red-600 font-medium">↘</span>
                <span>Recent 90-day demand &lt; yearly average (ratio &lt; 0.8)</span>
              </div>
            </div>
          </section>

          {/* Status */}
          <section>
            <h3 className="font-semibold mb-2">Status Definitions</h3>
            <div className="space-y-1.5 text-xs">
              <div><span className="inline-block w-16 font-medium text-red-600">Critical</span> Stock covers less than lead time days</div>
              <div><span className="inline-block w-16 font-medium text-amber-600">Warning</span> Stock covers less than lead time + buffer</div>
              <div><span className="inline-block w-16 font-medium text-green-600">OK</span> Sufficient stock</div>
              <div><span className="inline-block w-16 font-medium text-red-500">Out</span> Zero or negative stock balance</div>
            </div>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
