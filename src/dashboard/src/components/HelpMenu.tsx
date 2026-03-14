import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { HelpCircle, BookOpen, Play, type LucideIcon } from 'lucide-react'

interface HelpMenuProps {
  onReplayTour: () => void
}

const ITEM_CLASS = 'flex items-center gap-2 w-full rounded px-3 py-2 text-sm hover:bg-muted transition-colors text-left'

function MenuItem({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button className={ITEM_CLASS} onClick={onClick}>
      <Icon className="h-4 w-4 text-muted-foreground" />
      {label}
    </button>
  )
}

export default function HelpMenu({ onReplayTour }: HelpMenuProps) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const items = [
    { icon: BookOpen, label: 'Help Guide', action: () => navigate('/help') },
    { icon: Play, label: 'Replay Tour', action: () => onReplayTour() },
  ]

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center justify-center h-8 w-8 p-0 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        aria-label="Help"
      >
        <HelpCircle className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-1" align="end">
        {items.map(item => (
          <MenuItem
            key={item.label}
            icon={item.icon}
            label={item.label}
            onClick={() => { setOpen(false); item.action() }}
          />
        ))}
      </PopoverContent>
    </Popover>
  )
}
