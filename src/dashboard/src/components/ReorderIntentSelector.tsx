import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateReorderIntent } from '@/lib/api'
import type { ReorderIntent } from '@/lib/types'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const INTENT_OPTIONS: { value: ReorderIntent; label: string; className: string }[] = [
  { value: 'normal', label: 'Normal', className: 'text-muted-foreground' },
  { value: 'must_stock', label: 'Must Stock', className: 'text-purple-700' },
  { value: 'do_not_reorder', label: 'Do Not Reorder', className: 'text-gray-500' },
]

interface Props {
  stockItemName: string
  currentIntent: ReorderIntent
  size?: 'sm' | 'default'
}

export default function ReorderIntentSelector({ stockItemName, currentIntent, size = 'sm' }: Props) {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (intent: ReorderIntent) => updateReorderIntent(stockItemName, intent),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['poData'] })
      queryClient.invalidateQueries({ queryKey: ['brands'] })
    },
  })

  const current = INTENT_OPTIONS.find(o => o.value === currentIntent) || INTENT_OPTIONS[0]

  return (
    <Select
      value={currentIntent}
      onValueChange={v => {
        if (v && v !== currentIntent) mutation.mutate(v as ReorderIntent)
      }}
    >
      <SelectTrigger
        className={`${size === 'sm' ? 'h-7 text-xs px-2 w-[130px]' : 'h-9 text-sm w-[160px]'} ${current.className}`}
        onClick={e => e.stopPropagation()}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {INTENT_OPTIONS.map(o => (
          <SelectItem key={o.value} value={o.value} className={o.className}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
