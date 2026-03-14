import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Info } from 'lucide-react'
import { Link } from 'react-router-dom'

interface HelpTipProps {
  tip: string
  helpAnchor?: string
}

export default function HelpTip({ tip, helpAnchor }: HelpTipProps) {
  return (
    <Popover>
      <PopoverTrigger
        className="inline-flex items-center justify-center h-5 w-5 rounded-full text-muted-foreground hover:text-foreground transition-colors"
        aria-label="More info"
      >
        <Info className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent className="w-72 text-sm" side="top" align="start">
        <p className="text-muted-foreground leading-relaxed">{tip}</p>
        {helpAnchor && (
          <Link
            to={`/help#${helpAnchor}`}
            className="inline-block mt-2 text-xs font-medium text-primary hover:underline"
          >
            Learn more &rarr;
          </Link>
        )}
      </PopoverContent>
    </Popover>
  )
}
