interface Transaction {
  date: string
  type: string
  orderNumber: string
  channel: string
  qty: number
  runningStock: number
}

interface TransactionTableProps {
  transactions: Transaction[]
  caption?: string
}

export default function TransactionTable({ transactions, caption }: TransactionTableProps) {
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
          <tr
            style={{
              background: 'var(--docs-bg-code)',
              borderBottom: '2px solid var(--docs-border)',
            }}
          >
            {['Date', 'Type', 'Order #', 'Channel', 'Qty', 'Running Stock'].map((col) => (
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
          {transactions.map((txn, i) => (
            <tr
              key={i}
              style={{
                borderBottom: '1px solid var(--docs-border)',
                background: i % 2 === 0 ? 'transparent' : 'var(--docs-bg-code)',
              }}
            >
              <td style={{ padding: '0.5rem 0.875rem', whiteSpace: 'nowrap', color: 'var(--docs-text-secondary)' }}>
                {txn.date}
              </td>
              <td style={{ padding: '0.5rem 0.875rem', whiteSpace: 'nowrap' }}>
                {txn.type}
              </td>
              <td style={{ padding: '0.5rem 0.875rem', whiteSpace: 'nowrap', color: 'var(--docs-text-secondary)', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                {txn.orderNumber}
              </td>
              <td style={{ padding: '0.5rem 0.875rem', whiteSpace: 'nowrap' }}>
                {txn.channel}
              </td>
              <td
                style={{
                  padding: '0.5rem 0.875rem',
                  whiteSpace: 'nowrap',
                  fontWeight: 600,
                  color: txn.qty > 0 ? '#16a34a' : txn.qty < 0 ? '#dc2626' : 'var(--docs-text-muted)',
                }}
              >
                {txn.qty > 0 ? `+${txn.qty}` : txn.qty}
              </td>
              <td style={{ padding: '0.5rem 0.875rem', whiteSpace: 'nowrap', fontWeight: 700 }}>
                {txn.runningStock}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
