import DocSection from './components/DocSection'
import StatusTable from './components/StatusTable'
import CalloutBox from './components/CalloutBox'

// Status badge colors matching StatusTable.tsx
const STATUS_COLORS = {
  'Lost Sales':   { bg: '#7f1d1d', text: '#fca5a5', border: '#ef4444' },
  'Urgent':       { bg: '#991b1b', text: '#fecaca', border: '#f87171' },
  'Reorder':      { bg: '#92400e', text: '#fde68a', border: '#f59e0b' },
  'Healthy':      { bg: '#14532d', text: '#86efac', border: '#22c55e' },
  'Dead Stock':   { bg: '#3f3f46', text: '#a1a1aa', border: '#71717a' },
  'Out of Stock': { bg: '#27272a', text: '#d4d4d8', border: '#52525b' },
  'No Data':      { bg: '#1c1917', text: '#d6d3d1', border: '#44403c' },
}

function StatusBadge({ name }: { name: keyof typeof STATUS_COLORS }) {
  const c = STATUS_COLORS[name]
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        borderRadius: '4px',
        padding: '0.2rem 0.55rem',
        fontSize: '0.8rem',
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      {name}
    </span>
  )
}

const PRIORITY_ITEMS = [
  {
    num: 1,
    name: 'Lost Sales' as const,
    action: 'Plug the bleeding. Proven demand, zero stock.',
  },
  {
    num: 2,
    name: 'Urgent' as const,
    action: 'Prevent the next bleed. Will run out before shipment arrives.',
  },
  {
    num: 3,
    name: 'Reorder' as const,
    action: 'Keep the pipeline flowing. Time to include in next PO.',
  },
  {
    num: 4,
    name: 'Healthy' as const,
    action: 'Maintain on normal cycle. No rush.',
  },
  {
    num: 5,
    name: 'Dead Stock' as const,
    action: "Don't spend here. Not moving.",
  },
  {
    num: 6,
    name: 'Out of Stock' as const,
    action: 'Investigate first. Demand unknown.',
  },
  {
    num: 7,
    name: 'No Data' as const,
    action: 'Needs more history before deciding.',
  },
]

const ACTION_ROWS = [
  {
    name: 'Lost Sales' as const,
    priority: '🔴 1',
    todo: 'Order immediately. Every day without stock costs revenue.',
  },
  {
    name: 'Urgent' as const,
    priority: '🔴 2',
    todo: 'Order today. You\'ll stock out before the shipment arrives. Consider air freight for critical items.',
  },
  {
    name: 'Reorder' as const,
    priority: '🟡 3',
    todo: 'Include in your next PO. You have time, but the window is closing.',
  },
  {
    name: 'Healthy' as const,
    priority: '🟢 4',
    todo: "No rush. Keep ordering on your normal cycle. Don't skip it — healthy doesn't mean \"ignore.\"",
  },
  {
    name: 'Dead Stock' as const,
    priority: '⚫ 5',
    todo: "Don't order more. Investigate why it's not selling. Consider liquidating or bundling.",
  },
  {
    name: 'Out of Stock' as const,
    priority: '⚫ 6',
    todo: 'Research whether to restock. Demand might exist — you just can\'t measure it without inventory.',
  },
  {
    name: 'No Data' as const,
    priority: '⚫ 7',
    todo: 'Wait for more transaction history, or check if this is a new product that needs manual review.',
  },
]

const INTENT_ROWS = [
  {
    intent: 'Must Stock',
    effect: 'Forces minimum Reorder status + fallback qty even with zero velocity',
    when: 'Seasonal items, new launches, strategic products',
  },
  {
    intent: 'Do Not Reorder',
    effect: 'Shows calculated status but suppresses suggested qty to zero',
    when: 'Discontinued items, intentional phase-outs',
  },
  {
    intent: 'Normal (default)',
    effect: 'Formula decides everything',
    when: 'Most SKUs',
  },
]

function SimpleTable({
  headers,
  rows,
}: {
  headers: string[]
  rows: React.ReactNode[][]
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

// Decision tree node primitives
function TreeNode({
  label,
  children,
  isTerminal = false,
  statusName,
}: {
  label: React.ReactNode
  children?: React.ReactNode
  isTerminal?: boolean
  statusName?: keyof typeof STATUS_COLORS
}) {
  if (isTerminal && statusName) {
    return (
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          background: 'var(--docs-bg-card)',
          border: `1px solid ${STATUS_COLORS[statusName].border}`,
          borderLeft: `4px solid ${STATUS_COLORS[statusName].border}`,
          borderRadius: '6px',
          padding: '0.45rem 0.75rem',
          fontSize: '0.8rem',
          color: 'var(--docs-text-secondary)',
        }}
      >
        {label}
        <StatusBadge name={statusName} />
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'inline-block',
        background: 'var(--docs-bg-card)',
        border: '1px solid var(--docs-border)',
        borderRadius: '6px',
        padding: '0.45rem 0.875rem',
        fontSize: '0.85rem',
        fontWeight: 600,
        color: 'var(--docs-text)',
      }}
    >
      {label}
      {children}
    </div>
  )
}

function Branch({
  label,
  children,
  isLast = false,
}: {
  label: string
  children: React.ReactNode
  isLast?: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginTop: '0.6rem' }}>
      {/* Connector line */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginRight: '0.5rem', flexShrink: 0 }}>
        <div
          style={{
            width: '1px',
            height: isLast ? '1.1rem' : '1.1rem',
            background: 'var(--docs-border)',
          }}
        />
        <div style={{ width: '1.25rem', height: '1px', background: 'var(--docs-border)' }} />
      </div>
      {/* Branch content */}
      <div style={{ paddingTop: '0.55rem' }}>
        <span
          style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color: 'var(--docs-text-muted)',
            marginRight: '0.4rem',
            fontFamily: 'monospace',
            background: 'var(--docs-bg-code)',
            border: '1px solid var(--docs-border)',
            borderRadius: '3px',
            padding: '0.1rem 0.35rem',
          }}
        >
          {label}
        </span>
        {children}
      </div>
    </div>
  )
}

function DecisionTree() {
  return (
    <div
      style={{
        background: 'var(--docs-bg-code)',
        border: '1px solid var(--docs-border)',
        borderRadius: '10px',
        padding: '1.5rem 1.75rem',
        margin: '1.25rem 0',
        overflowX: 'auto',
      }}
    >
      {/* Root */}
      <TreeNode label="Is stock > 0?" />

      {/* NO branch */}
      <Branch label="NO">
        <TreeNode label="Is velocity > 0?" />
        <Branch label="YES">
          <TreeNode isTerminal statusName="Lost Sales" label="stock = 0, selling →" />
        </Branch>
        <Branch label="NO" isLast>
          <TreeNode isTerminal statusName="Out of Stock" label="stock = 0, no sales →" />
        </Branch>
      </Branch>

      {/* YES branch */}
      <Branch label="YES" isLast>
        <TreeNode label="Is velocity > 0?" />
        <Branch label="NO">
          <TreeNode isTerminal statusName="Dead Stock" label="has stock, not selling →" />
        </Branch>
        <Branch label="YES" isLast>
          <TreeNode label="Days left ≤ lead time?" />
          <Branch label="YES">
            <TreeNode isTerminal statusName="Urgent" label="→" />
          </Branch>
          <Branch label="NO" isLast>
            <TreeNode label="Days left ≤ lead + max(30, 50% of lead)?" />
            <Branch label="YES">
              <TreeNode isTerminal statusName="Reorder" label="→" />
            </Branch>
            <Branch label="NO" isLast>
              <TreeNode isTerminal statusName="Healthy" label="→" />
            </Branch>
          </Branch>
        </Branch>
      </Branch>
    </div>
  )
}

export default function Statuses() {
  return (
    <div>
      {/* Page header */}
      <h1
        style={{
          color: 'var(--docs-text)',
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '0.4rem',
          marginTop: 0,
        }}
      >
        Understanding Statuses
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.05rem',
          marginBottom: '2.5rem',
          marginTop: 0,
        }}
      >
        Seven statuses. One priority stack. What each means and what to do about it.
      </p>

      {/* Section 1: The 7 Statuses */}
      <DocSection id="status-table" title="The 7 Statuses">
        <p style={{ marginTop: 0 }}>Every SKU gets exactly one status, updated nightly.</p>
        <StatusTable />
      </DocSection>

      {/* Section 2: Capital Priority Stack */}
      <DocSection id="priority-stack" title="Capital Priority Stack">
        <p style={{ marginTop: 0 }}>
          When you have limited capital, fund items in this order. Lost Sales first — you're already
          losing money. Healthy last — those items can wait.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', margin: '1.25rem 0' }}>
          {PRIORITY_ITEMS.map((item) => {
            const c = STATUS_COLORS[item.name]
            return (
              <div
                key={item.num}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  background: 'var(--docs-bg-card)',
                  border: '1px solid var(--docs-border)',
                  borderLeft: `4px solid ${c.border}`,
                  borderRadius: '0 8px 8px 0',
                  padding: '0.65rem 1rem',
                }}
              >
                <span
                  style={{
                    color: 'var(--docs-text-muted)',
                    fontWeight: 700,
                    fontSize: '0.95rem',
                    minWidth: '1.5rem',
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                >
                  {item.num}
                </span>
                <StatusBadge name={item.name} />
                <span
                  style={{
                    color: 'var(--docs-text-secondary)',
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                  }}
                >
                  {item.action}
                </span>
              </div>
            )
          })}
        </div>
      </DocSection>

      {/* Section 3: Status Decision Tree */}
      <DocSection id="decision-tree" title="Status Decision Tree">
        <p style={{ marginTop: 0 }}>The system follows this logic to assign each status.</p>
        <DecisionTree />
        <CalloutBox type="info" title="Where is No Data?">
          No Data is assigned before this tree runs — items with no transaction history never enter the
          status logic. They are flagged as No Data at the pipeline level.
        </CalloutBox>
      </DocSection>

      {/* Section 4: What To Do */}
      <DocSection id="actions" title="What To Do">
        <SimpleTable
          headers={['Status', 'Priority', 'What To Do']}
          rows={ACTION_ROWS.map((row) => [
            <StatusBadge name={row.name} />,
            <span style={{ whiteSpace: 'nowrap', color: 'var(--docs-text)' }}>{row.priority}</span>,
            row.todo,
          ])}
        />
      </DocSection>

      {/* Section 5: Intent Overrides */}
      <DocSection id="intents" title="Intent Overrides">
        <p style={{ marginTop: 0 }}>
          You can override the formula's judgment on specific SKUs.
        </p>
        <SimpleTable
          headers={['Intent', 'Effect', 'When To Use']}
          rows={INTENT_ROWS.map((row) => [
            <span style={{ fontWeight: 600, color: 'var(--docs-text)' }}>{row.intent}</span>,
            row.effect,
            row.when,
          ])}
        />
        <CalloutBox type="info">
          Set intent per SKU on the SKU detail page. <strong>Must Stock</strong> is useful for items
          you know will sell but don't have velocity data yet — like a brand-new product.
        </CalloutBox>
      </DocSection>
    </div>
  )
}
