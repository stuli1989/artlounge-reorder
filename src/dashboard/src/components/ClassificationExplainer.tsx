import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchBrandSummary, fetchSettings, updateSetting } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { HelpCircle, ChevronDown, ChevronRight } from 'lucide-react'
import AbcBadge from '@/components/AbcBadge'
import XyzBadge from '@/components/XyzBadge'

function MatrixTable({ data, className }: { data: string[][]; className?: string }) {
  return (
    <table className={`w-full text-xs border-collapse ${className ?? ''}`}>
      <tbody>
        {data.map((row, i) => (
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
  )
}

export default function ClassificationExplainer() {
  const [open, setOpen] = useState(false)
  const [showFullMatrix, setShowFullMatrix] = useState(false)
  const queryClient = useQueryClient()

  const { data: summary } = useQuery({
    queryKey: ['brandSummary'],
    queryFn: fetchBrandSummary,
    enabled: open,
  })

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    enabled: open,
  })

  const useXyzBuffer = settings?.use_xyz_buffer === 'true'

  const a = summary?.total_a_class_skus ?? 0
  const b = summary?.total_b_class_skus ?? 0
  const c = summary?.total_c_class_skus ?? 0
  const total = a + b + c || 1

  const abcOnlyTable = [
    ['', 'Buffer'],
    ['A (80% rev)', `${settings?.buffer_a ?? '1.5'}x`],
    ['B (15% rev)', `${settings?.buffer_b ?? '1.3'}x`],
    ['C (5% rev)', `${settings?.buffer_c ?? '1.1'}x`],
  ]

  const fullMatrix = [
    ['', 'X (Steady)', 'Y (Variable)', 'Z (Sporadic)'],
    ['A (80% rev)', '1.3x', '1.5x', '1.8x'],
    ['B (15% rev)', '1.2x', '1.3x', '1.5x'],
    ['C (5% rev)', '1.1x', '1.2x', '1.3x'],
  ]

  const [toggleError, setToggleError] = useState(false)
  const handleToggleXyz = async (checked: boolean) => {
    try {
      setToggleError(false)
      await updateSetting('use_xyz_buffer', checked ? 'true' : 'false')
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    } catch {
      setToggleError(true)
    }
  }

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
            <h3 className="font-semibold mb-2">Safety Buffer {useXyzBuffer ? '(ABC×XYZ Matrix)' : '(ABC Only)'}</h3>

            {!useXyzBuffer ? (
              <>
                <p className="text-muted-foreground mb-2 text-xs">
                  Buffers are based on ABC revenue class only. XYZ demand variability is computed and shown for reference, but does not affect buffer calculations.
                </p>
                <MatrixTable data={abcOnlyTable} className="mb-3" />
                <p className="text-muted-foreground text-xs italic">
                  99.6% of classifiable SKUs are Z-class, so the XYZ dimension provides no useful discrimination for art supplies.
                </p>

                {/* Collapsed full matrix */}
                <button
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-2"
                  onClick={() => setShowFullMatrix(v => !v)}
                >
                  {showFullMatrix ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  Full ABC×XYZ matrix (reference)
                </button>
                {showFullMatrix && <MatrixTable data={fullMatrix} className="mt-2" />}
              </>
            ) : (
              <>
                <p className="text-muted-foreground mb-2 text-xs">
                  Higher buffer = order more. A+Z gets 1.8x because it's high-revenue AND unpredictable.
                </p>
                <MatrixTable data={fullMatrix} />
              </>
            )}

            {/* Global toggle */}
            <div className="flex items-center gap-3 mt-4 p-3 rounded-lg border bg-muted/30">
              <Switch
                checked={useXyzBuffer}
                onCheckedChange={handleToggleXyz}
              />
              <div>
                <div className="text-sm font-medium">Use XYZ-adjusted buffers</div>
                <div className="text-xs text-muted-foreground">
                  Changes take effect after next nightly sync. Per-item overrides are unaffected.
                </div>
                {toggleError && (
                  <div className="text-xs text-red-600 mt-1">Failed to update setting</div>
                )}
              </div>
            </div>
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
