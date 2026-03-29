import React from 'react'

interface DocSectionProps {
  id: string
  title?: string
  children: React.ReactNode
}

export default function DocSection({ id, title, children }: DocSectionProps) {
  return (
    <section
      id={id}
      style={{ scrollMarginTop: '80px', marginBottom: '2.5rem' }}
    >
      {title && (
        <h2
          style={{
            color: 'var(--docs-text)',
            fontSize: '1.5rem',
            fontWeight: 700,
            marginBottom: '1rem',
            paddingBottom: '0.5rem',
            borderBottom: '1px solid var(--docs-border)',
          }}
        >
          {title}
        </h2>
      )}
      <div style={{ color: 'var(--docs-text-secondary)', lineHeight: 1.75 }}>
        {children}
      </div>
    </section>
  )
}
