import AbcBadge from '@/components/AbcBadge'
import XyzBadge from '@/components/XyzBadge'
import { Flame } from 'lucide-react'

interface SkuSecondaryLineProps {
  abc_class: string | null | undefined
  xyz_class: string | null | undefined
  part_no: string | null | undefined
  is_hazardous?: boolean
}

export default function SkuSecondaryLine({ abc_class, xyz_class, part_no, is_hazardous }: SkuSecondaryLineProps) {
  const hasContent = abc_class || xyz_class || part_no || is_hazardous
  if (!hasContent) return null

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <AbcBadge value={abc_class} />
      <XyzBadge value={xyz_class} />
      {part_no && <span className="text-muted-foreground">PN: {part_no}</span>}
      {is_hazardous && <Flame className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />}
    </div>
  )
}
