interface AbcBadgeProps {
  value: string | null | undefined
}

const colors: Record<string, string> = {
  A: 'bg-red-100 text-red-700 border-red-200',
  B: 'bg-amber-100 text-amber-700 border-amber-200',
  C: 'bg-gray-100 text-gray-500 border-gray-200',
}

export default function AbcBadge({ value }: AbcBadgeProps) {
  if (!value) return <span className="text-gray-300">-</span>
  const cls = colors[value] || colors.C
  return (
    <span className={`inline-flex items-center justify-center w-6 h-5 rounded text-[10px] font-bold border ${cls}`}>
      {value}
    </span>
  )
}
