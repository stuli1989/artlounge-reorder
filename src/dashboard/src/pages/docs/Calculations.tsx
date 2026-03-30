import { useState } from 'react'
import DocSection from './components/DocSection'
import FormulaBlock from './components/FormulaBlock'
import TransactionTable from './components/TransactionTable'
import CalloutBox from './components/CalloutBox'

const positionExample = [
  { date: 'Jun 15', type: 'Purchase Received', orderNumber: 'G0412', channel: 'supplier', qty: 50, runningStock: 50 },
  { date: 'Jun 22', type: 'Picked for Order', orderNumber: 'SO-03890', channel: 'wholesale', qty: -12, runningStock: 38 },
  { date: 'Jul 1', type: 'Picked for Order', orderNumber: 'MA-049821', channel: 'online', qty: -3, runningStock: 35 },
  { date: 'Jul 8', type: 'Purchase Received', orderNumber: 'G0445', channel: 'supplier', qty: 20, runningStock: 55 },
  { date: 'Jul 15', type: 'Picked for Order', orderNumber: 'SO-03945', channel: 'wholesale', qty: -15, runningStock: 40 },
]

function SimpleTable({
  headers,
  rows,
}: {
  headers: string[]
  rows: (string | number)[][]
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
                    padding: '0.5rem 0.875rem',
                    color: 'var(--docs-text-secondary)',
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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; color: string }> = {
    Urgent: { bg: 'rgba(220,38,38,0.12)', color: '#dc2626' },
    'Lost Sales': { bg: 'rgba(124,58,237,0.12)', color: '#7c3aed' },
    'Dead Stock': { bg: 'rgba(245,158,11,0.12)', color: '#d97706' },
    'Out of Stock': { bg: 'rgba(107,114,128,0.12)', color: '#6b7280' },
    Reorder: { bg: 'rgba(234,88,12,0.12)', color: '#ea580c' },
    Healthy: { bg: 'rgba(22,163,74,0.12)', color: '#16a34a' },
  }
  const c = colors[status] ?? { bg: 'rgba(107,114,128,0.1)', color: '#6b7280' }
  return (
    <span
      style={{
        display: 'inline-block',
        background: c.bg,
        color: c.color,
        borderRadius: '6px',
        padding: '0.2rem 0.65rem',
        fontWeight: 700,
        fontSize: '0.85rem',
        letterSpacing: '0.02em',
      }}
    >
      {status}
    </span>
  )
}

function FormulaCalculator() {
  const [stock, setStock] = useState(20)
  const [velocity, setVelocity] = useState(4.61)
  const [leadTime, setLeadTime] = useState(90)
  const [coverage, setCoverage] = useState(91)
  const [buffer, setBuffer] = useState(1.3)

  const demandLead = velocity * leadTime
  const orderCoverage = velocity * coverage * buffer
  const suggestedQty = Math.max(0, Math.round(demandLead + orderCoverage - stock))
  const daysLeft = velocity > 0 ? stock / velocity : null

  const status =
    stock <= 0 && velocity > 0
      ? 'Lost Sales'
      : stock <= 0 && velocity <= 0
      ? 'Out of Stock'
      : velocity <= 0
      ? 'Dead Stock'
      : daysLeft! <= leadTime
      ? 'Urgent'
      : daysLeft! <= leadTime + Math.max(30, leadTime * 0.5)
      ? 'Reorder'
      : 'Healthy'

  const inputStyle: React.CSSProperties = {
    background: 'var(--docs-bg-card)',
    border: '1px solid var(--docs-border)',
    color: 'var(--docs-text)',
    borderRadius: '6px',
    padding: '0.45rem 0.75rem',
    fontSize: '0.95rem',
    width: '100%',
    outline: 'none',
    marginTop: '0.3rem',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '0.8rem',
    color: 'var(--docs-text-muted)',
    fontWeight: 600,
    letterSpacing: '0.03em',
    textTransform: 'uppercase',
  }

  function Field({
    label,
    value,
    onChange,
    step = 1,
  }: {
    label: string
    value: number
    onChange: (v: number) => void
    step?: number
  }) {
    return (
      <div>
        <label style={labelStyle}>{label}</label>
        <input
          type="number"
          value={value}
          step={step}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          style={inputStyle}
        />
      </div>
    )
  }

  return (
    <div
      style={{
        background: 'var(--docs-bg-card)',
        border: '1px solid var(--docs-border)',
        borderRadius: '10px',
        padding: '1.5rem',
        margin: '1.5rem 0',
      }}
    >
      <div
        style={{
          fontWeight: 700,
          fontSize: '1rem',
          color: 'var(--docs-text)',
          marginBottom: '1.25rem',
        }}
      >
        Try It — Formula Calculator
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <Field label="Current Stock (units)" value={stock} onChange={setStock} />
        <Field label="Daily Velocity (/day)" value={velocity} onChange={setVelocity} step={0.01} />
        <Field label="Lead Time (days)" value={leadTime} onChange={setLeadTime} />
        <Field label="Coverage Period (days)" value={coverage} onChange={setCoverage} />
        <Field label="Safety Buffer (×)" value={buffer} onChange={setBuffer} step={0.05} />
      </div>

      <div
        style={{
          background: 'var(--docs-bg-code)',
          border: '1px solid var(--docs-border)',
          borderRadius: '8px',
          padding: '1.25rem 1.5rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.25rem',
        }}
      >
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--docs-text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.25rem' }}>
            Days to Stockout
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--docs-text)' }}>
            {daysLeft !== null ? daysLeft.toFixed(1) : '—'}
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--docs-text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.25rem' }}>
            Status
          </div>
          <div style={{ marginTop: '0.15rem' }}>
            <StatusBadge status={status} />
          </div>
        </div>

        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--docs-text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.25rem' }}>
            Suggested Order Qty
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--docs-accent)' }}>
            {suggestedQty.toLocaleString()}
          </div>
        </div>
      </div>

      <FormulaBlock caption="Live calculation with your inputs">
{`demand_during_lead = ${velocity.toFixed(2)} × ${leadTime}          = ${demandLead.toFixed(0)}
order_for_coverage  = ${velocity.toFixed(2)} × ${coverage} × ${buffer.toFixed(2)}    = ${orderCoverage.toFixed(0)}
suggested_qty       = ${demandLead.toFixed(0)} + ${orderCoverage.toFixed(0)} − ${stock}   = ${suggestedQty}`}
      </FormulaBlock>
    </div>
  )
}

export default function Calculations() {
  return (
    <div>
      <h1
        style={{
          color: 'var(--docs-text)',
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '0.5rem',
        }}
      >
        How We Calculate
      </h1>
      <p style={{ color: 'var(--docs-text-secondary)', marginBottom: '2.5rem', fontSize: '1.05rem' }}>
        From raw transactions to reorder recommendations — every formula, step by step.
      </p>

      {/* ── Stock Positions ── */}
      <DocSection id="positions" title="Stock Positions">
        <p>
          We rebuild each SKU's stock history day by day from the very first transaction. Each GRN (purchase receipt) adds stock; each PICKLIST (order pick) removes stock.
        </p>

        <TransactionTable
          transactions={positionExample}
          caption="Example: running stock position rebuilt from individual transactions"
        />

        <CalloutBox type="notice">
          Current sellable stock comes from the UC Inventory Snapshot — not from this forward walk. The forward walk gives us history and velocity. The snapshot gives us right now.
        </CalloutBox>
      </DocSection>

      {/* ── Velocity ── */}
      <DocSection id="velocity" title="Velocity">
        <p>Velocity = how fast a product is selling, measured in units per month.</p>

        <FormulaBlock>
          {`units sold ÷ in-stock days × 30 = monthly velocity`}
        </FormulaBlock>

        <FormulaBlock caption="Worked example">
          {`Total units sold:      1,246
In-stock days:         270  (out of 295 — 25 days were out-of-stock)
Daily velocity:        1,246 ÷ 270 = 4.61 /day
Monthly velocity:      4.61 × 30 = 138.4 /mo`}
        </FormulaBlock>

        <CalloutBox type="info" title="Why exclude out-of-stock days?">
          If a product was out of stock for 3 months, counting those days would halve the real demand. We only count days when stock was available — this gives the true selling rate.
        </CalloutBox>
      </DocSection>

      {/* ── Channel Breakdown ── */}
      <DocSection id="channels" title="Channel Breakdown">
        <p>Velocity is split into three channels: wholesale, online, and store.</p>

        <SimpleTable
          headers={['Channel', 'How It\'s Identified', 'Typical Examples']}
          rows={[
            ['Wholesale', 'Sale order patterns + Sundry Debtors', 'Dealer orders from Bhiwandi'],
            ['Online', 'MAGENTO2, AMAZON_IN_API, Flipkart', 'E-commerce marketplace orders'],
            ['Store', 'KG Shipping Packages (CUSTOM_SHOP)', 'Kala Ghoda walk-in customers'],
          ]}
        />

        <p>Total velocity = wholesale + online + store.</p>
      </DocSection>

      {/* ── ABC Classification ── */}
      <DocSection id="abc" title="ABC Classification">
        <SimpleTable
          headers={['Class', 'Revenue Share', 'Meaning']}
          rows={[
            ['A', 'Top 80%', 'Your money-makers — highest priority'],
            ['B', 'Next 15%', 'Solid contributors'],
            ['C', 'Bottom 5%', 'Low revenue — watch for dead stock'],
          ]}
        />

        <p>
          Revenue = quantity sold × MRP from the UC catalog. An SKU selling 2 units at ₹10,000 MRP outranks one selling 100 units at ₹50.
        </p>
      </DocSection>

      {/* ── XYZ Classification ── */}
      <DocSection id="xyz" title="XYZ Classification">
        <SimpleTable
          headers={['Class', 'CV (Coefficient of Variation)', 'Meaning']}
          rows={[
            ['X', '< 0.5', 'Stable, predictable demand'],
            ['Y', '0.5 – 1.0', 'Variable, somewhat predictable'],
            ['Z', '> 1.0', 'Erratic, hard to forecast'],
          ]}
        />

        <p>
          XYZ tells you how much to trust the velocity number. An X-class item with 10/mo velocity will likely sell 8–12. A Z-class item might sell 0 or 30.
        </p>
      </DocSection>

      {/* ── Stockout Projection ── */}
      <DocSection id="stockout" title="Stockout Projection">
        <FormulaBlock>
          {`days_to_stockout = current_stock ÷ daily_velocity`}
        </FormulaBlock>

        <FormulaBlock caption="Worked example">
          {`Stock: 20 units    Velocity: 4.61 /day
Days left: 20 ÷ 4.61 = 4.3 days`}
        </FormulaBlock>

        <SimpleTable
          headers={['Scenario', 'Velocity', 'Stock', 'Days Left', 'Status']}
          rows={[
            ['Selling, stock available', '4.61/day', '20', '4.3', 'Urgent'],
            ['Selling, no stock', '4.61/day', '0', '0', 'Lost Sales'],
            ['Not selling, has stock', '0/day', '50', '—', 'Dead Stock'],
            ['Not selling, no stock', '0/day', '0', '—', 'Out of Stock'],
          ]}
        />
      </DocSection>

      {/* ── Lead Time & Coverage ── */}
      <DocSection id="lead-time" title="Lead Time & Coverage">
        <p>
          Lead time = how many days from placing an order to receiving the goods. Default is 90 days per supplier setting (engine fallback: 180 days if no supplier configured). For air freight, 15–20 days. Configurable per supplier on the Suppliers page.
        </p>

        <p>Coverage period = how long the order should last after it arrives.</p>

        <FormulaBlock>
          {`turns_per_year = min(max(1, ⌊365 ÷ lead_time⌋), 6)
coverage_days  = ⌊365 ÷ turns_per_year⌋   (integer division, rounded down)

Example: lead_time = 90 days
  turns = min(max(1, ⌊365 ÷ 90⌋), 6) = min(4, 6) = 4
  coverage = ⌊365 ÷ 4⌋ = 91 days`}
        </FormulaBlock>

        <p>So with 90-day lead time, each order should cover about 91 days of demand.</p>
      </DocSection>

      {/* ── Safety Buffer ── */}
      <DocSection id="buffer" title="Safety Buffer">
        <p>
          The safety buffer is a multiplier that adds extra stock to protect against demand spikes or delivery delays.
        </p>

        <SimpleTable
          headers={['ABC Class', 'Default Buffer']}
          rows={[
            ['A (top revenue)', '1.3×'],
            ['B (mid revenue)', '1.2×'],
            ['C (low revenue)', '1.1×'],
          ]}
        />

        <CalloutBox type="notice" title="Buffer applies to coverage only">
          The buffer multiplies coverage demand — NOT lead time demand. Buffering lead time would double-count uncertainty. You need enough to survive the lead time (exact), plus extra for the coverage period (buffered).
        </CalloutBox>
      </DocSection>

      {/* ── The Reorder Formula ── */}
      <DocSection id="reorder-formula" title="The Reorder Formula">
        <FormulaBlock>
          {`demand_during_lead  = velocity × lead_time           (no buffer)
order_for_coverage  = velocity × coverage × buffer   (buffer here)
suggested_qty       = demand_lead + order_coverage − current_stock`}
        </FormulaBlock>

        <FormulaBlock caption="SKU 6312 — Koh-i-noor Eraser Pencil">
          {`Velocity:     4.61 /day (138.4 /mo)
Lead time:    90 days
Coverage:     91 days
Buffer:       1.3x
Stock:        20 units

demand_during_lead = 4.61 × 90        = 415
order_for_coverage = 4.61 × 91 × 1.3  = 546
suggested_qty      = 415 + 546 − 20   = 941 units`}
        </FormulaBlock>

        <FormulaCalculator />

        <CalloutBox type="info" title="Two ordering modes">
          Each supplier can be set to one of two modes on the Suppliers page:
          <br /><br />
          <strong>Full (default):</strong> suggested = demand_lead + order_coverage − stock.
          Orders enough for the lead time wait plus the coverage period. Larger orders, less frequent reordering.
          <br /><br />
          <strong>Coverage only:</strong> suggested = order_coverage − stock.
          Orders only for the post-arrival coverage period. Smaller orders — useful when capital is tight or lead times are short.
        </CalloutBox>
      </DocSection>
    </div>
  )
}
