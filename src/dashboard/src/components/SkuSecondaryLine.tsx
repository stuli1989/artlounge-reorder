import AbcBadge from '@/components/AbcBadge'
import XyzBadge from '@/components/XyzBadge'
import { Flame } from 'lucide-react'

interface SkuSecondaryLineProps {
  abc_class: string | null | undefined
  xyz_class: string | null | undefined
  /** The numeric SKU code (e.g. "20838624") to display as "Part No" */
  sku_code: string | null | undefined
  is_hazardous?: boolean
}

export default function SkuSecondaryLine({ abc_class, xyz_class, sku_code, is_hazardous }: SkuSecondaryLineProps) {
  const hasContent = abc_class || xyz_class || sku_code || is_hazardous
  if (!hasContent) return null

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <AbcBadge value={abc_class} />
      <XyzBadge value={xyz_class} />
      {sku_code && <span className="text-muted-foreground">Part No: {sku_code}</span>}
      {is_hazardous && <Flame className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />}
    </div>
  )
}
