import { Link } from 'react-router-dom'
import DocSection from './components/DocSection'
import FlowDiagram from './components/FlowDiagram'
import CalloutBox from './components/CalloutBox'

const statCards = [
  { value: '23,000+', label: 'SKUs tracked' },
  { value: '172', label: 'Brands' },
  { value: '3', label: 'Facilities' },
  { value: 'Nightly', label: 'Data refresh' },
  { value: '7', label: 'Reorder statuses' },
  { value: '98.4%', label: 'Stock accuracy' },
]

const chapters = [
  { path: '/docs/data-sources',    num: 1, title: 'Data Sources',          desc: 'Where the data comes from and how we pull it.' },
  { path: '/docs/calculations',    num: 2, title: 'How We Calculate',       desc: 'Velocity, stockout projection, and the reorder formula.' },
  { path: '/docs/statuses',        num: 3, title: 'Understanding Statuses', desc: 'What each status means and what action to take.' },
  { path: '/docs/walkthroughs',    num: 4, title: 'SKU Walkthroughs',       desc: '6 real products traced end-to-end through the system.' },
  { path: '/docs/dashboard-guide', num: 5, title: 'Using the Dashboard',    desc: 'Page-by-page guide to every screen.' },
  { path: '/docs/workflows',       num: 6, title: 'Daily Workflows',        desc: 'Morning check, building POs, and the monthly review.' },
  { path: '/docs/architecture',    num: 7, title: 'System Architecture',    desc: 'Data flow, APIs, sync schedule, and Railway setup.' },
  { path: '/docs/glossary',        num: 8, title: 'Glossary',               desc: 'A–Z definitions for every term used in these docs.' },
]

export default function Overview() {
  return (
    <div>
      {/* Page header */}
      <h1
        style={{
          color: 'var(--docs-text)',
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '0.5rem',
          lineHeight: 1.2,
        }}
      >
        How It All Works
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.1rem',
          lineHeight: 1.6,
          marginBottom: '2.5rem',
          maxWidth: '640px',
        }}
      >
        Everything you need to know about Art Lounge's stock intelligence system — from raw data to
        purchase orders.
      </p>

      {/* The Problem */}
      <DocSection id="problem" title="The Problem">
        <p>
          Art Lounge imports art supplies in bulk — minimum orders of 250+ units with 3–6 month sea
          freight lead times — and sells through wholesale, online (Magento, Amazon, Flipkart), and
          the Kala Ghoda retail store. With 23,000+ SKUs across 172 brands, knowing <em>what</em> to
          reorder and <em>when</em> is genuinely hard.
        </p>
        <p style={{ marginTop: '0.75rem' }}>
          Order too early and you tie up capital. Order too late and a product sells out for months
          while the shipment is at sea. This system exists to take the guesswork out of that call.
        </p>
      </DocSection>

      {/* The Solution */}
      <DocSection id="solution" title="The Solution">
        <p>
          Every night, we pull fresh data from Unicommerce (the warehouse management system),
          calculate how fast each product is selling, project when it'll run out, and recommend how
          much to order. Demand is broken down by channel — wholesale, online, and store — so you
          can see exactly where the movement is coming from.
        </p>

        <FlowDiagram
          nodes={[
            { icon: '🏭', title: 'Unicommerce',   subtitle: 'Orders & stock',    color: 'blue'   },
            { icon: '🔄', title: 'Nightly Sync',  subtitle: 'Data pipeline',     color: 'purple' },
            { icon: '⚙️', title: 'Calculations',  subtitle: 'Velocity & stockout', color: 'amber' },
            { icon: '📊', title: 'Dashboard',     subtitle: 'Reorder signals',   color: 'teal'   },
            { icon: '📋', title: 'Purchase Orders', subtitle: 'Ready to send',   color: 'green'  },
          ]}
        />

        <CalloutBox type="info" title="Three facilities">
          We track stock across Bhiwandi (main warehouse), Kala Ghoda (retail store), and Ali
          Bhiwandi (overflow). Velocity is calculated per facility so reorder quantities stay
          accurate.
        </CalloutBox>
      </DocSection>

      {/* Key Numbers */}
      <DocSection id="key-numbers" title="Key Numbers">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: '1rem',
            marginTop: '0.5rem',
          }}
        >
          {statCards.map(({ value, label }) => (
            <div
              key={label}
              style={{
                background: 'var(--docs-bg-card)',
                border: '1px solid var(--docs-border)',
                borderRadius: '10px',
                padding: '1rem 1.25rem',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  color: 'var(--docs-accent)',
                  lineHeight: 1.1,
                }}
              >
                {value}
              </div>
              <div
                style={{
                  fontSize: '0.8rem',
                  color: 'var(--docs-text-muted)',
                  marginTop: '0.35rem',
                  lineHeight: 1.3,
                }}
              >
                {label}
              </div>
            </div>
          ))}
        </div>
      </DocSection>

      {/* What's in these docs */}
      <DocSection id="whats-here" title="What's in These Docs">
        <p style={{ marginBottom: '1.25rem' }}>
          Eight chapters cover everything from raw API data to daily workflows. Jump straight to what
          you need.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {chapters.map(({ path, num, title, desc }) => (
            <Link
              key={path}
              to={path}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: '1rem',
                padding: '0.75rem 1rem',
                background: 'var(--docs-bg-card)',
                border: '1px solid var(--docs-border)',
                borderRadius: '8px',
                textDecoration: 'none',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--docs-accent)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--docs-border)'
              }}
            >
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: 'var(--docs-text-muted)',
                  minWidth: '1.5rem',
                  flexShrink: 0,
                }}
              >
                {String(num).padStart(2, '0')}
              </span>
              <span
                style={{
                  fontWeight: 600,
                  color: 'var(--docs-text)',
                  fontSize: '0.9rem',
                  minWidth: '190px',
                  flexShrink: 0,
                }}
              >
                {title}
              </span>
              <span
                style={{
                  color: 'var(--docs-text-secondary)',
                  fontSize: '0.875rem',
                }}
              >
                {desc}
              </span>
            </Link>
          ))}
        </div>
      </DocSection>
    </div>
  )
}
