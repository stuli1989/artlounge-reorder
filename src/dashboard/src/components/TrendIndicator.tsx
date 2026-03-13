import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface TrendIndicatorProps {
  direction: string | null | undefined
  ratio: number | null | undefined
}

export default function TrendIndicator({ direction, ratio }: TrendIndicatorProps) {
  if (!direction || direction === 'flat') {
    return <Minus className="h-3.5 w-3.5 text-gray-400 inline-block" />
  }

  const ratioText = ratio ? `${ratio.toFixed(2)}x` : ''

  if (direction === 'up') {
    return (
      <Tooltip>
        <TooltipTrigger>
          <TrendingUp className="h-3.5 w-3.5 text-green-600 inline-block" />
        </TooltipTrigger>
        <TooltipContent>Trending up — WMA/flat ratio: {ratioText}</TooltipContent>
      </Tooltip>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger>
        <TrendingDown className="h-3.5 w-3.5 text-red-600 inline-block" />
      </TooltipTrigger>
      <TooltipContent>Trending down — WMA/flat ratio: {ratioText}</TooltipContent>
    </Tooltip>
  )
}
