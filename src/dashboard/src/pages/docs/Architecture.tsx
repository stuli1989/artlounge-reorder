import DocSection from './components/DocSection'
import FlowDiagram from './components/FlowDiagram'
import CalloutBox from './components/CalloutBox'

function SimpleTable({
  headers,
  rows,
}: {
  headers: string[]
  rows: (string | React.ReactNode)[][]
}) {
  return (
    <div style={{ margin: '1.25rem 0', overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.875rem',
          color: 'var(--docs-text)',
          border: '1px solid var(--docs-border)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <thead>
          <tr style={{ background: 'var(--docs-bg-code)', borderBottom: '2px solid var(--docs-border)' }}>
            {headers.map((h) => (
              <th
                key={h}
                style={{
                  padding: '0.6rem 0.875rem',
                  textAlign: 'left',
                  fontWeight: 600,
                  color: 'var(--docs-text)',
                  fontSize: '0.8rem',
                  letterSpacing: '0.02em',
                  whiteSpace: 'nowrap',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{
                borderBottom: '1px solid var(--docs-border)',
                background: i % 2 === 0 ? 'transparent' : 'var(--docs-bg-code)',
              }}
            >
              {row.map((cell, j) => (
                <td
                  key={j}
                  style={{
                    padding: '0.6rem 0.875rem',
                    color: 'var(--docs-text-secondary)',
                    verticalAlign: 'top',
                    lineHeight: 1.6,
                  }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Architecture() {
  return (
    <div>
      <h1
        style={{
          color: 'var(--docs-text)',
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '0.4rem',
          marginTop: 0,
        }}
      >
        System Architecture
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.05rem',
          marginBottom: '2.5rem',
          marginTop: 0,
        }}
      >
        How the pieces fit together — APIs, sync, and data flow.
      </p>

      <DocSection id="data-flow" title="Data Flow">
        <p style={{ marginTop: 0 }}>
          Data flows left to right, once per night. The pipeline recomputes everything from scratch
          each time.
        </p>
        <FlowDiagram
          nodes={[
            { icon: '🔌', title: 'UC APIs',     subtitle: '4 sources',                    color: 'blue'   },
            { icon: '🔄', title: 'Nightly Sync', subtitle: 'Railway cron',                color: 'purple' },
            { icon: '🗄️', title: 'PostgreSQL',  subtitle: 'Transactions + metrics',       color: 'teal'   },
            { icon: '⚙️', title: 'Pipeline',    subtitle: 'Positions → velocity → reorder', color: 'amber' },
            { icon: '🚀', title: 'FastAPI',      subtitle: 'REST API',                    color: 'red'    },
            { icon: '📊', title: 'Dashboard',    subtitle: 'React SPA',                   color: 'green'  },
          ]}
        />
      </DocSection>

      <DocSection id="api-sources" title="API Sources">
        <p style={{ marginTop: 0 }}>
          Four Unicommerce APIs feed the system. Each covers a different piece of the picture.
        </p>
        <SimpleTable
          headers={['API', 'Endpoint', 'What It Provides', 'Pull Frequency']}
          rows={[
            [
              <span style={{ fontWeight: 600, color: 'var(--docs-text)' }}>Transaction Ledger</span>,
              'Export Job API',
              'All stock movements (GRN, PICKLIST, adjustments)',
              'Nightly, per facility',
            ],
            [
              <span style={{ fontWeight: 600, color: 'var(--docs-text)' }}>Shipping Packages</span>,
              'Search API',
              'KG counter sale dispatches',
              'Nightly, KG facility only',
            ],
            [
              <span style={{ fontWeight: 600, color: 'var(--docs-text)' }}>Inventory Snapshot</span>,
              'Snapshot API',
              'Current sellable stock per SKU',
              'Nightly, all facilities',
            ],
            [
              <span style={{ fontWeight: 600, color: 'var(--docs-text)' }}>Catalog</span>,
              'Search API',
              'SKU master, brand, MRP',
              'Nightly',
            ],
          ]}
        />
      </DocSection>

      <DocSection id="sync-schedule" title="Sync Schedule">
        <p style={{ marginTop: 0 }}>
          Runs nightly at 10 PM UTC / 3:30 AM IST (<code style={{ fontFamily: 'monospace', fontSize: '0.875rem', background: 'var(--docs-bg-code)', padding: '0.1rem 0.35rem', borderRadius: '3px', border: '1px solid var(--docs-border)' }}>0 22 * * * UTC</code>) as a Railway cron service. Takes 5–10 minutes. Success/failure notification sent via email.
        </p>
        <CalloutBox type="info" title="If sync fails">
          Check the Railway logs first. Common causes: UC API timeout (retry usually fixes it) or
          the snapshot pull returning stale data.
        </CalloutBox>
      </DocSection>

      <DocSection id="limitations" title="Known Limitations">
        <p style={{ marginTop: 0 }}>
          These are known data gaps — not bugs. Understanding them helps you interpret anomalies.
        </p>
        <ul
          style={{
            margin: '0.5rem 0',
            paddingLeft: '1.25rem',
            color: 'var(--docs-text-secondary)',
            fontSize: '0.9rem',
            lineHeight: 1.9,
          }}
        >
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>INVOICES excluded</strong> — billing
            document bug: quantities inflated 1x–144x per invoice.
          </li>
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>KG PICKLIST incomplete</strong> —
            counter sales bypass it. We use Shipping Packages for KG demand instead.
          </li>
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>Ali Bhiwandi is stock-counting only</strong>{' '}
            — 100% inventory adjustments, no demand signal.
          </li>
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>inventoryBlocked causes ~1.6% drift</strong>{' '}
            — items picked but not yet shipped don't appear in snapshot.
          </li>
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>Export Job API occasionally slow</strong>{' '}
            — UC server-side delays; sync retries automatically.
          </li>
          <li>
            <strong style={{ color: 'var(--docs-text)' }}>No real-time data</strong> — everything
            is nightly batch. Stock movements during the day aren't visible until tomorrow.
          </li>
        </ul>
      </DocSection>
    </div>
  )
}
