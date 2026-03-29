import { useState } from 'react'
import { Link } from 'react-router-dom'

interface GlossaryEntry {
  term: string
  definition: string
  linkTo?: string
}

interface SearchableListProps {
  entries: GlossaryEntry[]
}

export default function SearchableList({ entries }: SearchableListProps) {
  const [query, setQuery] = useState('')

  const filtered = query.trim()
    ? entries.filter((e) => e.term.toLowerCase().includes(query.toLowerCase()))
    : entries

  return (
    <div>
      <input
        type="text"
        placeholder="Filter terms..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{
          width: '100%',
          padding: '0.625rem 0.875rem',
          background: 'var(--docs-bg-code)',
          border: '1px solid var(--docs-border)',
          borderRadius: '8px',
          color: 'var(--docs-text)',
          fontSize: '0.9rem',
          outline: 'none',
          marginBottom: '1rem',
          boxSizing: 'border-box',
        }}
      />

      {filtered.length === 0 ? (
        <p style={{ color: 'var(--docs-text-muted)', fontStyle: 'italic', fontSize: '0.9rem' }}>
          No terms match "{query}"
        </p>
      ) : (
        <dl style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          {filtered.map((entry, i) => (
            <div
              key={i}
              style={{
                borderBottom: '1px solid var(--docs-border)',
                paddingBottom: '0.875rem',
              }}
            >
              <dt
                style={{
                  fontWeight: 700,
                  color: 'var(--docs-text)',
                  fontSize: '0.95rem',
                  marginBottom: '0.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                {entry.term}
                {entry.linkTo && (
                  <Link
                    to={entry.linkTo}
                    style={{
                      color: 'var(--docs-link)',
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      textDecoration: 'none',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                    onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                  >
                    see more →
                  </Link>
                )}
              </dt>
              <dd
                style={{
                  margin: 0,
                  color: 'var(--docs-text-secondary)',
                  fontSize: '0.875rem',
                  lineHeight: 1.65,
                }}
              >
                {entry.definition}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
