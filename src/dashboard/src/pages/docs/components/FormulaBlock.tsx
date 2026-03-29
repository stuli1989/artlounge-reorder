import React from 'react'

interface FormulaBlockProps {
  children: React.ReactNode
  caption?: string
}

export default function FormulaBlock({ children, caption }: FormulaBlockProps) {
  return (
    <div style={{ margin: '1.25rem 0' }}>
      <pre
        style={{
          background: 'var(--docs-bg-code)',
          color: 'var(--docs-text)',
          border: '1px solid var(--docs-border)',
          borderRadius: '8px',
          padding: '1rem 1.25rem',
          fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", ui-monospace, monospace',
          fontSize: '0.875rem',
          lineHeight: 1.7,
          overflowX: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          margin: 0,
        }}
      >
        {children}
      </pre>
      {caption && (
        <p
          style={{
            color: 'var(--docs-text-muted)',
            fontSize: '0.8rem',
            marginTop: '0.4rem',
            fontStyle: 'italic',
          }}
        >
          {caption}
        </p>
      )}
    </div>
  )
}
