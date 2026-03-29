interface StatusRow {
  num: number
  status: string
  badgeBg: string
  badgeText: string
  condition: string
  meaning: string
  action: string
}

const STATUSES: StatusRow[] = [
  {
    num: 1,
    status: 'Lost Sales',
    badgeBg: '#7f1d1d',
    badgeText: '#fca5a5',
    condition: 'stock ≤ 0, velocity > 0',
    meaning: 'Bleeding revenue — active demand but nothing to ship',
    action: 'Order ASAP',
  },
  {
    num: 2,
    status: 'Urgent',
    badgeBg: '#991b1b',
    badgeText: '#fecaca',
    condition: 'days to stockout ≤ lead time',
    meaning: 'Will run out before next shipment arrives',
    action: 'Act today',
  },
  {
    num: 3,
    status: 'Reorder',
    badgeBg: '#92400e',
    badgeText: '#fde68a',
    condition: 'days ≤ lead + max(30, 50% of lead)',
    meaning: 'Approaching the reorder point',
    action: 'Include in next PO',
  },
  {
    num: 4,
    status: 'Healthy',
    badgeBg: '#14532d',
    badgeText: '#86efac',
    condition: 'days > lead + max(30, 50% of lead)',
    meaning: 'Pipeline flowing, covered well beyond next shipment',
    action: 'Normal cycle',
  },
  {
    num: 5,
    status: 'Dead Stock',
    badgeBg: '#3f3f46',
    badgeText: '#a1a1aa',
    condition: 'stock > 0, velocity = 0',
    meaning: 'Has inventory but no recent sales',
    action: "Don't order — investigate",
  },
  {
    num: 6,
    status: 'Out of Stock',
    badgeBg: '#27272a',
    badgeText: '#d4d4d8',
    condition: 'stock ≤ 0, velocity = 0',
    meaning: 'Empty and no known demand',
    action: 'Investigate',
  },
  {
    num: 7,
    status: 'No Data',
    badgeBg: '#1c1917',
    badgeText: '#d6d3d1',
    condition: 'No transaction history',
    meaning: 'Insufficient data to evaluate',
    action: 'Investigate',
  },
]

export default function StatusTable() {
  return (
    <div style={{ overflowX: 'auto', margin: '1.25rem 0' }}>
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
            {['#', 'Status', 'Condition', 'Meaning', 'Action'].map((col) => (
              <th
                key={col}
                style={{
                  padding: '0.6rem 0.875rem',
                  textAlign: 'left',
                  fontWeight: 600,
                  color: 'var(--docs-text)',
                  whiteSpace: 'nowrap',
                  fontSize: '0.8rem',
                  letterSpacing: '0.02em',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {STATUSES.map((row, i) => (
            <tr
              key={row.num}
              style={{
                borderBottom: '1px solid var(--docs-border)',
                background: i % 2 === 0 ? 'transparent' : 'var(--docs-bg-code)',
              }}
            >
              <td
                style={{
                  padding: '0.6rem 0.875rem',
                  color: 'var(--docs-text-muted)',
                  fontWeight: 500,
                }}
              >
                {row.num}
              </td>
              <td style={{ padding: '0.6rem 0.875rem', whiteSpace: 'nowrap' }}>
                <span
                  style={{
                    background: row.badgeBg,
                    color: row.badgeText,
                    borderRadius: '4px',
                    padding: '0.2rem 0.55rem',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {row.status}
                </span>
              </td>
              <td
                style={{
                  padding: '0.6rem 0.875rem',
                  color: 'var(--docs-text-secondary)',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  whiteSpace: 'nowrap',
                }}
              >
                {row.condition}
              </td>
              <td style={{ padding: '0.6rem 0.875rem', color: 'var(--docs-text-secondary)' }}>
                {row.meaning}
              </td>
              <td style={{ padding: '0.6rem 0.875rem', whiteSpace: 'nowrap', fontWeight: 500, color: 'var(--docs-text)' }}>
                {row.action}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
