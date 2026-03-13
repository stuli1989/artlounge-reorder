interface VelocityToggleProps {
  value: 'flat' | 'wma'
  onChange: (value: 'flat' | 'wma') => void
}

export default function VelocityToggle({ value, onChange }: VelocityToggleProps) {
  return (
    <div className="inline-flex rounded-md border bg-muted p-0.5">
      <button
        className={`px-2.5 py-1 text-xs rounded-sm transition-colors ${
          value === 'flat'
            ? 'bg-background shadow-sm font-medium'
            : 'text-muted-foreground hover:text-foreground'
        }`}
        onClick={() => onChange('flat')}
      >
        Flat
      </button>
      <button
        className={`px-2.5 py-1 text-xs rounded-sm transition-colors ${
          value === 'wma'
            ? 'bg-background shadow-sm font-medium'
            : 'text-muted-foreground hover:text-foreground'
        }`}
        onClick={() => onChange('wma')}
      >
        WMA (90d)
      </button>
    </div>
  )
}
