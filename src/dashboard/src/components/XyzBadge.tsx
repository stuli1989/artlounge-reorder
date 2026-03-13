interface XyzBadgeProps {
  value: string | null | undefined
}

const colors: Record<string, string> = {
  X: 'bg-green-100 text-green-700 border-green-200',
  Y: 'bg-amber-100 text-amber-700 border-amber-200',
  Z: 'bg-red-100 text-red-700 border-red-200',
}

export default function XyzBadge({ value }: XyzBadgeProps) {
  if (!value) return <span className="text-gray-300">-</span>
  const cls = colors[value] || colors.Z
  return (
    <span className={`inline-flex items-center justify-center w-6 h-5 rounded text-[10px] font-bold border ${cls}`}>
      {value}
    </span>
  )
}
