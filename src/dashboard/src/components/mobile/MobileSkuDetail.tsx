import { useEffect, useCallback, useState } from 'react'
import type { SkuMetrics } from '@/lib/types'
import { ArrowLeft } from 'lucide-react'
import StatusBadge from '@/components/StatusBadge'
import AbcBadge from '@/components/AbcBadge'
import StockTimeline from '@/components/StockTimeline'
import CalculationBreakdown from '@/components/CalculationBreakdown'
import { BottomSheet } from '@/components/mobile/BottomSheet'
import { vel, daysColor } from '@/lib/formatters'

interface MobileSkuDetailProps {
  sku: SkuMetrics
  categoryName: string
  velocityType: 'flat' | 'wma'
  analysisRange: { from: string; to: string } | null
  onBack: () => void
}

export default function MobileSkuDetail({
  sku,
  categoryName,
  velocityType,
  analysisRange,
  onBack,
}: MobileSkuDetailProps) {
  const [showCalculation, setShowCalculation] = useState(false)

  // Push history state so back button works
  useEffect(() => {
    window.history.pushState({ mobileSkuDetail: true }, '')
    const handlePopState = () => {
      onBack()
    }
    window.addEventListener('popstate', handlePopState)
    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [onBack])

  const handleBack = useCallback(() => {
    window.history.back()
  }, [])

  const stock = sku.effective_stock ?? sku.current_stock
  const daysLeft = sku.effective_days_to_stockout ?? sku.days_to_stockout
  const totalVel = velocityType === 'wma' ? (sku.wma_total_velocity ?? 0) : (sku.effective_velocity ?? sku.total_velocity)
  const wholesaleVel = velocityType === 'wma' ? (sku.wma_wholesale_velocity ?? 0) : (sku.effective_wholesale_velocity ?? sku.wholesale_velocity)
  const onlineVel = velocityType === 'wma' ? (sku.wma_online_velocity ?? 0) : (sku.effective_online_velocity ?? sku.online_velocity)
  const storeVel = sku.effective_store_velocity ?? sku.store_velocity
  const suggestedQty = sku.effective_suggested_qty ?? sku.reorder_qty_suggested
  const status = sku.effective_status ?? sku.reorder_status

  return (
    <div className="fixed inset-0 z-50 bg-background overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-background border-b px-3 py-2.5 z-10">
        <div className="flex items-center gap-2">
          <button
            onClick={handleBack}
            className="p-1.5 -ml-1 rounded-md hover:bg-muted transition-colors"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-sm truncate">{sku.stock_item_name}</div>
            {sku.part_no && (
              <div className="text-xs text-muted-foreground">{sku.part_no}</div>
            )}
          </div>
          <StatusBadge status={status} />
        </div>
      </div>

      <div className="px-4 py-4 space-y-5">
        {/* 2x2 Metric Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground">Current Stock</div>
            <div className={`text-xl font-bold ${stock <= 0 ? 'text-red-600' : ''}`}>
              {stock.toLocaleString()}
            </div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground">Days to Stockout</div>
            <div className={`text-xl font-bold ${daysColor(daysLeft)}`}>
              {daysLeft === null ? 'N/A' : daysLeft === 0 ? 'OUT' : `${daysLeft}d`}
            </div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground">Total Velocity</div>
            <div className="text-xl font-bold">{vel(totalVel)}/mo</div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-xs text-muted-foreground">Suggested Qty</div>
            <div className="text-xl font-bold">{suggestedQty ?? '\u2014'}</div>
          </div>
        </div>

        {/* Channel Velocity Breakdown */}
        <div className="bg-muted/30 rounded-lg border p-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Velocity by Channel</h4>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
                Wholesale
              </span>
              <span className="font-medium">{vel(wholesaleVel)}/mo</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500 inline-block" />
                Online
              </span>
              <span className="font-medium">{vel(onlineVel)}/mo</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                Store
              </span>
              <span className="font-medium">{vel(storeVel)}/mo</span>
            </div>
            <div className="flex items-center justify-between text-sm border-t pt-1.5 mt-1.5">
              <span className="font-semibold">Total</span>
              <span className="font-semibold">{vel(totalVel)}/mo</span>
            </div>
          </div>
        </div>

        {/* ABC / XYZ / Buffer badges */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-muted/50 rounded-lg px-3 py-2">
            <span className="text-xs text-muted-foreground">ABC:</span>
            <AbcBadge value={sku.abc_class} />
          </div>
          <div className="flex items-center gap-1.5 bg-muted/50 rounded-lg px-3 py-2">
            <span className="text-xs text-muted-foreground">XYZ:</span>
            <span className="text-sm font-medium">{sku.xyz_class ?? '\u2014'}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-muted/50 rounded-lg px-3 py-2">
            <span className="text-xs text-muted-foreground">Buffer:</span>
            <span className="text-sm font-medium">{sku.safety_buffer}x</span>
          </div>
        </div>

        {/* Stock Timeline Chart */}
        <div>
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Stock Timeline</h4>
          <StockTimeline
            categoryName={categoryName}
            stockItemName={sku.stock_item_name}
            disableDragSelect
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setShowCalculation(true)}
            className="flex-1 bg-muted rounded-lg px-3 py-2.5 text-sm font-medium text-center"
          >
            View Calculations
          </button>
        </div>
      </div>

      {/* Calculation Bottom Sheet */}
      <BottomSheet open={showCalculation} onOpenChange={setShowCalculation} title="Calculation Breakdown">
        <CalculationBreakdown
          categoryName={categoryName}
          stockItemName={sku.stock_item_name}
          fromDate={analysisRange?.from}
          toDate={analysisRange?.to}
        />
      </BottomSheet>
    </div>
  )
}
