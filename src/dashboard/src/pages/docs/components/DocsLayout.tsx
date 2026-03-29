import './theme.css'
import { useState, useEffect, useCallback } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Sun, Moon, Menu, X, ArrowLeft, ArrowRight } from 'lucide-react'

// ---------------------------------------------------------------------------
// Navigation data
// ---------------------------------------------------------------------------

interface NavSection {
  id: string
  label: string
}

interface NavChapter {
  title: string
  path: string
  sections: NavSection[]
}

const DOCS_NAV: NavChapter[] = [
  { title: 'Overview', path: '/docs/overview', sections: [] },
  {
    title: 'Data Sources', path: '/docs/data-sources', sections: [
      { id: 'unicommerce', label: 'Unicommerce' },
      { id: 'order-lifecycle', label: 'Order Lifecycle' },
      { id: 'facilities', label: 'Three Facilities' },
      { id: 'hybrid-formula', label: 'Hybrid Formula' },
      { id: 'invoices-bug', label: 'Why INVOICES Excluded' },
      { id: 'kg-shipping', label: 'KG Shipping Packages' },
      { id: 'nightly-sync', label: 'Nightly Sync' },
      { id: 'drift', label: 'Drift Monitoring' },
    ],
  },
  {
    title: 'How We Calculate', path: '/docs/calculations', sections: [
      { id: 'positions', label: 'Stock Positions' },
      { id: 'velocity', label: 'Velocity' },
      { id: 'channels', label: 'Channel Breakdown' },
      { id: 'abc', label: 'ABC Classification' },
      { id: 'xyz', label: 'XYZ Classification' },
      { id: 'stockout', label: 'Stockout Projection' },
      { id: 'lead-time', label: 'Lead Time & Coverage' },
      { id: 'buffer', label: 'Safety Buffer' },
      { id: 'reorder-formula', label: 'The Reorder Formula' },
    ],
  },
  {
    title: 'Understanding Statuses', path: '/docs/statuses', sections: [
      { id: 'status-table', label: 'The 7 Statuses' },
      { id: 'priority-stack', label: 'Capital Priority' },
      { id: 'decision-tree', label: 'Decision Tree' },
      { id: 'actions', label: 'What To Do' },
      { id: 'intents', label: 'Intent Overrides' },
    ],
  },
  {
    title: 'SKU Walkthroughs', path: '/docs/walkthroughs', sections: [
      { id: 'workhorse', label: 'The Workhorse' },
      { id: 'flash-seller', label: 'The Flash Seller' },
      { id: 'store-bestseller', label: 'Store Bestseller' },
      { id: 'online-mover', label: 'Online Mover' },
      { id: 'dead-stock-sitter', label: 'Dead Stock Sitter' },
      { id: 'sporadic', label: 'Sporadic Item' },
    ],
  },
  {
    title: 'Using the Dashboard', path: '/docs/dashboard-guide', sections: [
      { id: 'page-home', label: 'Home' },
      { id: 'page-brands', label: 'Brands' },
      { id: 'page-sku', label: 'SKU Detail' },
      { id: 'page-priority', label: 'Priority SKUs' },
      { id: 'page-po', label: 'Build PO' },
      { id: 'page-dead-stock', label: 'Dead Stock' },
      { id: 'page-overrides', label: 'Overrides' },
      { id: 'page-suppliers', label: 'Suppliers' },
      { id: 'page-parties', label: 'Parties' },
      { id: 'page-settings', label: 'Settings' },
    ],
  },
  {
    title: 'Daily Workflows', path: '/docs/workflows', sections: [
      { id: 'morning', label: 'Morning Check' },
      { id: 'build-po', label: 'Building a PO' },
      { id: 'monthly', label: 'Monthly Review' },
      { id: 'tuning', label: 'Tuning Buffers' },
      { id: 'anomalies', label: 'Investigating Anomalies' },
    ],
  },
  {
    title: 'System Architecture', path: '/docs/architecture', sections: [
      { id: 'data-flow', label: 'Data Flow' },
      { id: 'api-sources', label: 'API Sources' },
      { id: 'sync-schedule', label: 'Sync Schedule' },
      { id: 'limitations', label: 'Known Limitations' },
    ],
  },
  { title: 'Glossary', path: '/docs/glossary', sections: [] },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTheme(): 'light' | 'dark' {
  try {
    const stored = localStorage.getItem('docs-theme')
    if (stored === 'dark' || stored === 'light') return stored
  } catch {
    // ignore
  }
  return 'light'
}

function setThemeStorage(theme: 'light' | 'dark') {
  try {
    localStorage.setItem('docs-theme', theme)
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Sidebar content (extracted so it can be used in both desktop + mobile)
// ---------------------------------------------------------------------------

interface SidebarContentProps {
  currentPath: string
  onLinkClick?: () => void
}

function SidebarContent({ currentPath, onLinkClick }: SidebarContentProps) {
  return (
    <nav style={{ padding: '1rem 0' }}>
      {/* Back to dashboard */}
      <div style={{ padding: '0 0.75rem 0.75rem' }}>
        <Link
          to="/"
          onClick={onLinkClick}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            color: 'var(--docs-text-muted)',
            fontSize: '0.8rem',
            textDecoration: 'none',
            padding: '0.375rem 0.5rem',
            borderRadius: '6px',
            transition: 'color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--docs-text)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--docs-text-muted)')}
        >
          <ArrowLeft size={13} />
          Back to Dashboard
        </Link>
      </div>

      <div style={{ height: '1px', background: 'var(--docs-border)', margin: '0 0.75rem 0.75rem' }} />

      {/* Chapter list */}
      {DOCS_NAV.map((chapter) => {
        const isActive = currentPath === chapter.path || currentPath.startsWith(chapter.path + '/')
        return (
          <div key={chapter.path} style={{ marginBottom: '0.125rem' }}>
            <NavLink
              to={chapter.path}
              onClick={onLinkClick}
              style={({ isActive: navActive }) => ({
                display: 'block',
                padding: '0.45rem 0.875rem',
                marginInline: '0.375rem',
                borderRadius: '6px',
                fontSize: '0.875rem',
                fontWeight: navActive ? 600 : 500,
                color: navActive ? 'var(--docs-text)' : 'var(--docs-text-secondary)',
                background: navActive ? 'var(--docs-sidebar-active)' : 'transparent',
                textDecoration: 'none',
                transition: 'background 0.15s, color 0.15s',
              })}
            >
              {chapter.title}
            </NavLink>

            {/* Sub-sections — only show when chapter is active */}
            {isActive && chapter.sections.length > 0 && (
              <div style={{ marginLeft: '1.125rem', borderLeft: '2px solid var(--docs-border)', paddingLeft: '0.625rem', marginBottom: '0.25rem' }}>
                {chapter.sections.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    onClick={onLinkClick}
                    style={{
                      display: 'block',
                      padding: '0.3rem 0.5rem',
                      fontSize: '0.8rem',
                      color: 'var(--docs-text-muted)',
                      textDecoration: 'none',
                      borderRadius: '4px',
                      transition: 'color 0.15s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--docs-text)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--docs-text-muted)')}
                  >
                    {section.label}
                  </a>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )
}

// ---------------------------------------------------------------------------
// Prev / Next navigation
// ---------------------------------------------------------------------------

function PrevNextNav({ currentPath }: { currentPath: string }) {
  const currentIndex = DOCS_NAV.findIndex((c) => c.path === currentPath)
  if (currentIndex === -1) return null

  const prev = currentIndex > 0 ? DOCS_NAV[currentIndex - 1] : null
  const next = currentIndex < DOCS_NAV.length - 1 ? DOCS_NAV[currentIndex + 1] : null

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        borderTop: '1px solid var(--docs-border)',
        marginTop: '3rem',
        paddingTop: '1.5rem',
        gap: '1rem',
      }}
    >
      <div style={{ flex: 1 }}>
        {prev && (
          <Link
            to={prev.path}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              color: 'var(--docs-link)',
              textDecoration: 'none',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--docs-text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <ArrowLeft size={12} /> Previous
            </span>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{prev.title}</span>
          </Link>
        )}
      </div>
      <div style={{ flex: 1, textAlign: 'right' }}>
        {next && (
          <Link
            to={next.path}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              alignItems: 'flex-end',
              color: 'var(--docs-link)',
              textDecoration: 'none',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--docs-text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              Next <ArrowRight size={12} />
            </span>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{next.title}</span>
          </Link>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main layout
// ---------------------------------------------------------------------------

export default function DocsLayout() {
  const [theme, setTheme] = useState<'light' | 'dark'>(getTheme)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Sync theme to localStorage
  useEffect(() => {
    setThemeStorage(theme)
  }, [theme])

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'))
  }, [])

  const themeClass = theme === 'dark' ? 'docs-dark' : 'docs-light'

  return (
    <div
      className={themeClass}
      style={{
        minHeight: '100vh',
        background: 'var(--docs-bg)',
        color: 'var(--docs-text)',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
      }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Top header bar                                                       */}
      {/* ------------------------------------------------------------------ */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          height: '56px',
          background: 'var(--docs-sidebar-bg)',
          borderBottom: '1px solid var(--docs-border)',
          display: 'flex',
          alignItems: 'center',
          paddingInline: '1rem',
          gap: '0.75rem',
        }}
      >
        {/* Hamburger — visible on mobile only */}
        <button
          onClick={() => setMobileOpen((o) => !o)}
          aria-label="Toggle menu"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            border: '1px solid var(--docs-border)',
            borderRadius: '6px',
            background: 'transparent',
            color: 'var(--docs-text)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
          className="docs-hamburger"
        >
          {mobileOpen ? <X size={18} /> : <Menu size={18} />}
        </button>

        {/* Title */}
        <Link
          to="/docs/overview"
          style={{
            fontWeight: 700,
            fontSize: '1rem',
            color: 'var(--docs-text)',
            textDecoration: 'none',
            letterSpacing: '-0.01em',
          }}
        >
          Art Lounge Docs
        </Link>

        <div style={{ flex: 1 }} />

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            border: '1px solid var(--docs-border)',
            borderRadius: '6px',
            background: 'transparent',
            color: 'var(--docs-text)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Body: sidebar + content                                             */}
      {/* ------------------------------------------------------------------ */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>

        {/* ---- Desktop sidebar ---- */}
        <aside
          style={{
            width: '260px',
            flexShrink: 0,
            background: 'var(--docs-sidebar-bg)',
            borderRight: '1px solid var(--docs-border)',
            overflowY: 'auto',
            position: 'sticky',
            top: '56px',
            height: 'calc(100vh - 56px)',
          }}
          className="docs-sidebar-desktop"
        >
          <SidebarContent currentPath={location.pathname} />
        </aside>

        {/* ---- Mobile sidebar drawer ---- */}
        {mobileOpen && (
          <>
            {/* Backdrop */}
            <div
              onClick={() => setMobileOpen(false)}
              style={{
                position: 'fixed',
                inset: 0,
                top: '56px',
                background: 'rgba(0,0,0,0.45)',
                zIndex: 40,
              }}
            />
            {/* Drawer */}
            <div
              style={{
                position: 'fixed',
                left: 0,
                top: '56px',
                bottom: 0,
                width: '280px',
                background: 'var(--docs-sidebar-bg)',
                borderRight: '1px solid var(--docs-border)',
                overflowY: 'auto',
                zIndex: 41,
              }}
            >
              <SidebarContent
                currentPath={location.pathname}
                onLinkClick={() => setMobileOpen(false)}
              />
            </div>
          </>
        )}

        {/* ---- Main content ---- */}
        <main
          style={{
            flex: 1,
            minWidth: 0,
            overflowY: 'auto',
          }}
        >
          <div
            style={{
              maxWidth: '820px',
              margin: '0 auto',
              padding: '2.5rem 2rem 4rem',
            }}
          >
            <Outlet />
            <PrevNextNav currentPath={location.pathname} />
          </div>
        </main>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Responsive styles injected via a style tag                          */}
      {/* ------------------------------------------------------------------ */}
      <style>{`
        .docs-sidebar-desktop {
          display: block;
        }
        .docs-hamburger {
          display: none;
        }
        @media (max-width: 768px) {
          .docs-sidebar-desktop {
            display: none;
          }
          .docs-hamburger {
            display: flex;
          }
        }
      `}</style>
    </div>
  )
}
