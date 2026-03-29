import DocSection from './components/DocSection'
import FlowDiagram from './components/FlowDiagram'
import CalloutBox from './components/CalloutBox'
import FormulaBlock from './components/FormulaBlock'

// ─── Shared table styles ────────────────────────────────────────────────────

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.875rem',
  color: 'var(--docs-text)',
  border: '1px solid var(--docs-border)',
  borderRadius: '8px',
  overflow: 'hidden',
  margin: '1.25rem 0',
}

const thStyle: React.CSSProperties = {
  padding: '0.6rem 0.875rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.8rem',
  letterSpacing: '0.02em',
  color: 'var(--docs-text)',
  background: 'var(--docs-bg-code)',
  borderBottom: '2px solid var(--docs-border)',
  whiteSpace: 'nowrap',
}

function tdStyle(i: number): React.CSSProperties {
  return {
    padding: '0.5rem 0.875rem',
    borderBottom: '1px solid var(--docs-border)',
    background: i % 2 === 0 ? 'transparent' : 'var(--docs-bg-code)',
    color: 'var(--docs-text-secondary)',
    verticalAlign: 'top',
    lineHeight: 1.55,
  }
}

import React from 'react'

export default function DataSources() {
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
        Data Sources
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
        Where the numbers come from — Unicommerce, API sources, and why we built it the way we did.
      </p>

      {/* ── 1. Unicommerce Overview ──────────────────────────────────────── */}
      <DocSection id="unicommerce" title="Unicommerce Overview">
        <p>
          Unicommerce is Art Lounge's warehouse management and order processing system. Every sale,
          purchase receipt, inventory adjustment, and stock count flows through UC. We pull data from
          UC every night to keep the dashboard current.
        </p>
      </DocSection>

      {/* ── 2. Order Lifecycle ───────────────────────────────────────────── */}
      <DocSection id="order-lifecycle" title="The Order Lifecycle">
        <FlowDiagram
          animated
          nodes={[
            { icon: '📋', title: 'Sale Order',        subtitle: 'Customer places order',      color: 'blue'   },
            { icon: '📦', title: 'Picklist',           subtitle: 'Warehouse picks items',      color: 'purple' },
            { icon: '🚚', title: 'Shipping Package',   subtitle: 'Package created & dispatched', color: 'teal' },
            { icon: '📄', title: 'Invoice',            subtitle: 'Billing document generated', color: 'amber'  },
            { icon: '✅', title: 'Dispatch',           subtitle: 'Shipped to customer',        color: 'green'  },
          ]}
        />

        <p>
          This is the journey of every sale. We track where each SKU is in this flow to calculate
          demand.
        </p>

        <CalloutBox type="warning" title="Important">
          We use PICKLIST entries (step 2) to count demand at Bhiwandi — not INVOICES (step 4).
          Invoices have an inflation bug. More on that below.
        </CalloutBox>
      </DocSection>

      {/* ── 3. Three Facilities ──────────────────────────────────────────── */}
      <DocSection id="facilities" title="Three Facilities">
        <div style={{ overflowX: 'auto' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {['Facility Code', 'Name', 'Role', 'How We Pull Demand'].map((col) => (
                  <th key={col} style={thStyle}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                {
                  code: 'ppetpl',
                  name: 'Bhiwandi (Main Warehouse)',
                  role: 'Wholesale + online fulfillment',
                  how: 'Transaction Ledger — PICKLIST entries',
                },
                {
                  code: 'PPETPLKALAGHODA',
                  name: 'Kala Ghoda (Retail Store)',
                  role: 'Retail counter sales',
                  how: 'Shipping Package API',
                },
                {
                  code: 'ALIBHIWANDI',
                  name: 'Ali Bhiwandi',
                  role: 'Stock counting only — no commerce',
                  how: 'Not used for demand (100% inventory adjustments)',
                },
              ].map((row, i) => (
                <tr key={row.code}>
                  <td style={{ ...tdStyle(i), fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--docs-text)', whiteSpace: 'nowrap' }}>
                    {row.code}
                  </td>
                  <td style={{ ...tdStyle(i), fontWeight: 500, color: 'var(--docs-text)', whiteSpace: 'nowrap' }}>
                    {row.name}
                  </td>
                  <td style={tdStyle(i)}>{row.role}</td>
                  <td style={tdStyle(i)}>{row.how}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p>
          Ali Bhiwandi only does weekly stock counts (ADD/REMOVE cycles). No actual buying or selling
          happens there.
        </p>
      </DocSection>

      {/* ── 4. Hybrid Formula ────────────────────────────────────────────── */}
      <DocSection id="hybrid-formula" title="The Hybrid Formula">
        <p>
          No single UC data source gives us everything we need. We combine four sources, each
          covering a different piece of the puzzle.
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {['Source', 'API', 'What It Provides', 'Used For'].map((col) => (
                  <th key={col} style={thStyle}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                {
                  source: 'Transaction Ledger',
                  api: 'Export Job API',
                  provides: 'All stock movements — GRNs, picklists, adjustments, gatepasses',
                  usedFor: 'Supply side + Bhiwandi demand (PICKLIST)',
                },
                {
                  source: 'Shipping Packages',
                  api: 'Search API',
                  provides: 'Dispatched packages with items and channels',
                  usedFor: 'Kala Ghoda demand (counter sales)',
                },
                {
                  source: 'Inventory Snapshot',
                  api: 'Snapshot API',
                  provides: 'Current sellable stock per SKU per facility',
                  usedFor: 'Current stock (ground truth)',
                },
                {
                  source: 'Catalog',
                  api: 'Search API',
                  provides: 'SKU master — names, codes, MRP, brand',
                  usedFor: 'SKU reference data + revenue calc',
                },
              ].map((row, i) => (
                <tr key={row.source}>
                  <td style={{ ...tdStyle(i), fontWeight: 600, color: 'var(--docs-text)', whiteSpace: 'nowrap' }}>
                    {row.source}
                  </td>
                  <td style={{ ...tdStyle(i), fontFamily: 'monospace', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                    {row.api}
                  </td>
                  <td style={tdStyle(i)}>{row.provides}</td>
                  <td style={tdStyle(i)}>{row.usedFor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <CalloutBox type="notice">
          Current stock comes from the UC snapshot — not from forward-walking transactions. The
          snapshot is always the source of truth for "how much do we have right now."
        </CalloutBox>
      </DocSection>

      {/* ── 5. Invoices Bug ──────────────────────────────────────────────── */}
      <DocSection id="invoices-bug" title="Why INVOICES Are Excluded">
        <p>
          UC's Transaction Ledger reports inflated quantities for INVOICES entities. The multiplier
          varies — sometimes 1x (correct), sometimes 4x, sometimes 144x.
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {['What UC Ledger Says', 'What the Actual Invoice Shows', 'Multiplier'].map((col) => (
                  <th key={col} style={thStyle}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                {
                  ledger: 'INS0584: 1,728 units of 8811-2',
                  actual: 'UC Invoice detail: 12 units',
                  multiplier: '144x',
                },
                {
                  ledger: 'INS0233: 4 units of PPET00246',
                  actual: 'UC Invoice detail: 1 unit',
                  multiplier: '4x',
                },
              ].map((row, i) => (
                <tr key={row.ledger}>
                  <td style={{ ...tdStyle(i), fontFamily: 'monospace', fontSize: '0.8rem' }}>{row.ledger}</td>
                  <td style={{ ...tdStyle(i), fontFamily: 'monospace', fontSize: '0.8rem' }}>{row.actual}</td>
                  <td style={{ ...tdStyle(i), fontWeight: 700, color: '#dc2626' }}>{row.multiplier}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p>
          INVOICES are billing documents with packed quantities, not individual unit counts. We
          exclude ALL INVOICES entities from our calculations.
        </p>

        <CalloutBox type="warning" title="Rule">
          If you ever see INVOICES in the Transaction Ledger, ignore the quantities. They are not
          real unit counts.
        </CalloutBox>
      </DocSection>

      {/* ── 6. KG Shipping Packages ──────────────────────────────────────── */}
      <DocSection id="kg-shipping" title="Why KG Uses Shipping Packages">
        <p>
          At Kala Ghoda, counter sales (walk-in customers) are processed as CUSTOM_SHOP orders.
          These don't generate PICKLIST entries in the Transaction Ledger — the only reliable record
          is the Shipping Package. So for KG demand, we pull dispatched Shipping Packages directly
          via the UC API.
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ ...tableStyle, maxWidth: '380px' }}>
            <thead>
              <tr>
                {['UC Channel', 'Our Channel'].map((col) => (
                  <th key={col} style={thStyle}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { uc: 'CUSTOM',      ours: 'Wholesale' },
                { uc: 'CUSTOM_SHOP', ours: 'Store (retail)' },
                { uc: 'MAGENTO2',    ours: 'Online' },
              ].map((row, i) => (
                <tr key={row.uc}>
                  <td style={{ ...tdStyle(i), fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--docs-text)' }}>
                    {row.uc}
                  </td>
                  <td style={tdStyle(i)}>{row.ours}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DocSection>

      {/* ── 7. Nightly Sync ──────────────────────────────────────────────── */}
      <DocSection id="nightly-sync" title="Nightly Sync">
        <p>Every night at 10:30 PM IST, the system runs this pipeline:</p>

        <FlowDiagram
          animated
          nodes={[
            { icon: '📚', title: 'Catalog',    subtitle: 'SKU master + brands',   color: 'blue'   },
            { icon: '📊', title: 'Ledger',     subtitle: 'Per facility',          color: 'purple' },
            { icon: '🏪', title: 'KG Demand',  subtitle: 'Shipping packages',     color: 'teal'   },
            { icon: '📸', title: 'Snapshots',  subtitle: 'Current stock',         color: 'amber'  },
            { icon: '⚙️', title: 'Pipeline',   subtitle: 'Calculations',          color: 'red'    },
            { icon: '🔍', title: 'Drift Check', subtitle: 'Verify accuracy',      color: 'gray'   },
            { icon: '✉️', title: 'Email',      subtitle: 'Success/failure',       color: 'green'  },
          ]}
        />

        <p>If any step fails, the sync stops and sends a failure notification.</p>
      </DocSection>

      {/* ── 8. Drift Monitoring ──────────────────────────────────────────── */}
      <DocSection id="drift" title="Drift Monitoring">
        <p>
          After computing positions, we compare our forward-walked closing stock against the UC
          inventory snapshot. If they don't match, we log the drift.
        </p>

        <FormulaBlock caption="Drift is computed per SKU after each nightly sync.">
          {'drift = forward_walk_closing − (inventory + blocked + bad_inventory)'}
        </FormulaBlock>

        <p>
          Across 23,362 SKUs, <strong style={{ color: 'var(--docs-text)' }}>22,998 (98.4%)</strong> have
          zero drift.
        </p>

        <p style={{ marginTop: '0.75rem' }}>
          The 1.6% with drift are mostly caused by <code style={{ fontSize: '0.85em', background: 'var(--docs-bg-code)', padding: '0.1em 0.4em', borderRadius: '4px', color: 'var(--docs-text)' }}>inventoryBlocked</code> — items
          picked for orders but not yet shipped. This is expected and self-corrects within hours.
        </p>

        <CalloutBox type="info" title="What if drift is large?">
          A drift &gt; 10 units usually means a missing transaction in the ledger (e.g., a dispatch
          without a PICKLIST entry). The operations team investigates these.
        </CalloutBox>
      </DocSection>
    </div>
  )
}
