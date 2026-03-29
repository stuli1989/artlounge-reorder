import React from 'react'

interface FlowNode {
  icon?: string
  title: string
  subtitle?: string
  color: 'teal' | 'amber' | 'red' | 'purple' | 'green' | 'blue' | 'gray'
}

interface FlowDiagramProps {
  nodes: FlowNode[]
  animated?: boolean
}

const COLOR_MAP: Record<FlowNode['color'], { bg: string; border: string; text: string }> = {
  teal:   { bg: 'rgba(20, 184, 166, 0.12)', border: 'rgba(20, 184, 166, 0.35)', text: '#0d9488' },
  amber:  { bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.35)', text: '#d97706' },
  red:    { bg: 'rgba(239, 68, 68, 0.12)',  border: 'rgba(239, 68, 68, 0.35)',  text: '#dc2626' },
  purple: { bg: 'rgba(168, 85, 247, 0.12)', border: 'rgba(168, 85, 247, 0.35)', text: '#9333ea' },
  green:  { bg: 'rgba(34, 197, 94, 0.12)',  border: 'rgba(34, 197, 94, 0.35)',  text: '#16a34a' },
  blue:   { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.35)', text: '#2563eb' },
  gray:   { bg: 'rgba(113, 113, 122, 0.12)', border: 'rgba(113, 113, 122, 0.35)', text: '#71717a' },
}

const KEYFRAMES = `
@keyframes dotsFlow {
  0%   { opacity: 0; transform: translateX(-8px); }
  30%  { opacity: 1; }
  70%  { opacity: 1; }
  100% { opacity: 0; transform: translateX(8px); }
}
`

export default function FlowDiagram({ nodes, animated = false }: FlowDiagramProps) {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const shouldAnimate = animated && !prefersReduced

  return (
    <>
      {shouldAnimate && <style>{KEYFRAMES}</style>}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.5rem',
          margin: '1.25rem 0',
        }}
      >
        {nodes.map((node, i) => {
          const colors = COLOR_MAP[node.color]
          return (
            <React.Fragment key={i}>
              <div
                style={{
                  background: colors.bg,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '10px',
                  padding: '0.75rem 1rem',
                  minWidth: '120px',
                  textAlign: 'center',
                  flexShrink: 0,
                }}
              >
                {node.icon && (
                  <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>
                    {node.icon}
                  </div>
                )}
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: '0.875rem',
                    color: colors.text,
                    lineHeight: 1.3,
                  }}
                >
                  {node.title}
                </div>
                {node.subtitle && (
                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--docs-text-muted)',
                      marginTop: '0.2rem',
                      lineHeight: 1.3,
                    }}
                  >
                    {node.subtitle}
                  </div>
                )}
              </div>

              {i < nodes.length - 1 && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '2px',
                    color: 'var(--docs-text-muted)',
                    flexShrink: 0,
                    position: 'relative',
                  }}
                >
                  {shouldAnimate ? (
                    <span
                      style={{
                        display: 'inline-block',
                        animation: 'dotsFlow 1.4s ease-in-out infinite',
                        animationDelay: `${i * 0.2}s`,
                        fontSize: '1rem',
                        lineHeight: 1,
                      }}
                    >
                      →
                    </span>
                  ) : (
                    <span style={{ fontSize: '1rem', lineHeight: 1 }}>→</span>
                  )}
                </div>
              )}
            </React.Fragment>
          )
        })}
      </div>
    </>
  )
}
