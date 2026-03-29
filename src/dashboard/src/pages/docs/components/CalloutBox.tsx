import React from 'react'
import { Link } from 'react-router-dom'

interface CalloutBoxProps {
  type: 'info' | 'warning' | 'notice'
  title?: string
  linkTo?: string
  linkText?: string
  children: React.ReactNode
}

const TYPE_STYLES = {
  info: {
    bg: 'rgba(59, 130, 246, 0.08)',
    border: 'rgba(59, 130, 246, 0.4)',
    accent: '#3b82f6',
    titleColor: '#2563eb',
  },
  warning: {
    bg: 'rgba(245, 158, 11, 0.08)',
    border: 'rgba(245, 158, 11, 0.4)',
    accent: '#f59e0b',
    titleColor: '#d97706',
  },
  notice: {
    bg: 'rgba(240, 165, 0, 0.08)',
    border: 'rgba(240, 165, 0, 0.4)',
    accent: 'var(--docs-accent)',
    titleColor: 'var(--docs-accent)',
  },
}

export default function CalloutBox({ type, title, linkTo, linkText, children }: CalloutBoxProps) {
  const styles = TYPE_STYLES[type]

  return (
    <div
      style={{
        background: styles.bg,
        borderLeft: `4px solid ${styles.accent}`,
        borderRadius: '0 8px 8px 0',
        padding: '0.875rem 1.125rem',
        margin: '1.25rem 0',
        border: `1px solid ${styles.border}`,
        borderLeftWidth: '4px',
        borderLeftColor: styles.accent,
      }}
    >
      {title && (
        <div
          style={{
            fontWeight: 700,
            fontSize: '0.875rem',
            color: styles.titleColor,
            marginBottom: '0.4rem',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {title}
        </div>
      )}
      <div
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '0.9rem',
          lineHeight: 1.65,
        }}
      >
        {children}
      </div>
      {linkTo && linkText && (
        <div style={{ marginTop: '0.5rem' }}>
          <Link
            to={linkTo}
            style={{
              color: 'var(--docs-link)',
              fontSize: '0.875rem',
              textDecoration: 'none',
              fontWeight: 500,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
            onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
          >
            {linkText} →
          </Link>
        </div>
      )}
    </div>
  )
}
