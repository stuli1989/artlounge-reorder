import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { HelpCircle, BookOpen, Play } from 'lucide-react'

interface HelpMenuProps {
  onReplayTour: () => void
}

export default function HelpMenu({ onReplayTour }: HelpMenuProps) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center justify-center h-8 w-8 p-0 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        aria-label="Help"
      >
        <HelpCircle className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-1" align="end">
        <button
          className="flex items-center gap-2 w-full rounded px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
          onClick={() => {
            setOpen(false)
            navigate('/help')
          }}
        >
          <BookOpen className="h-4 w-4 text-muted-foreground" />
          Help Guide
        </button>
        <button
          className="flex items-center gap-2 w-full rounded px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
          onClick={() => {
            setOpen(false)
            onReplayTour()
          }}
        >
          <Play className="h-4 w-4 text-muted-foreground" />
          Replay Tour
        </button>
      </PopoverContent>
    </Popover>
  )
}
