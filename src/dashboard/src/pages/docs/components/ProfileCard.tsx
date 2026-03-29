interface ProfileCardProps {
  name: string
  partNo: string
  archetype: string
  archetypeDescription: string
  stats: { label: string; value: string; color?: string }[]
}

const ARCHETYPE_COLORS: Record<string, { bg: string; text: string }> = {
  default: { bg: 'rgba(240, 165, 0, 0.15)', text: 'var(--docs-accent)' },
}

export default function ProfileCard({ name, partNo, archetype, archetypeDescription, stats }: ProfileCardProps) {
  return (
    <div
      style={{
        background: 'var(--docs-bg-card)',
        border: '1px solid var(--docs-border)',
        borderRadius: '12px',
        padding: '1.5rem',
        margin: '1.25rem 0',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
        <div>
          <h3
            style={{
              color: 'var(--docs-text)',
              fontSize: '1.25rem',
              fontWeight: 700,
              margin: 0,
              lineHeight: 1.3,
            }}
          >
            {name}
          </h3>
          <div
            style={{
              color: 'var(--docs-text-muted)',
              fontSize: '0.8rem',
              fontFamily: 'monospace',
              marginTop: '0.25rem',
            }}
          >
            {partNo}
          </div>
        </div>
        <span
          style={{
            background: ARCHETYPE_COLORS.default.bg,
            color: ARCHETYPE_COLORS.default.text,
            border: `1px solid ${ARCHETYPE_COLORS.default.text}`,
            borderRadius: '6px',
            padding: '0.25rem 0.75rem',
            fontSize: '0.8rem',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          }}
        >
          {archetype}
        </span>
      </div>

      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '0.9rem',
          lineHeight: 1.6,
          margin: '0 0 1.25rem',
        }}
      >
        {archetypeDescription}
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
          gap: '0.75rem',
        }}
      >
        {stats.map((stat, i) => (
          <div
            key={i}
            style={{
              background: 'var(--docs-bg-code)',
              border: '1px solid var(--docs-border)',
              borderRadius: '8px',
              padding: '0.625rem 0.875rem',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                fontSize: '1.1rem',
                fontWeight: 700,
                color: stat.color ?? 'var(--docs-text)',
                lineHeight: 1.2,
              }}
            >
              {stat.value}
            </div>
            <div
              style={{
                fontSize: '0.7rem',
                color: 'var(--docs-text-muted)',
                marginTop: '0.2rem',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {stat.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
