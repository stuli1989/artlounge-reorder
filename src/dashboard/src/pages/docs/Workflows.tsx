import DocSection from './components/DocSection'
import CalloutBox from './components/CalloutBox'
import FormulaBlock from './components/FormulaBlock'

function Steps({ items }: { items: string[] }) {
  return (
    <ol
      style={{
        margin: '0.75rem 0',
        paddingLeft: '1.5rem',
        color: 'var(--docs-text-secondary)',
        fontSize: '0.9rem',
        lineHeight: 1.9,
      }}
    >
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ol>
  )
}

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

export default function Workflows() {
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
        Daily Workflows
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.05rem',
          marginBottom: '2.5rem',
          marginTop: 0,
        }}
      >
        Practical playbooks — morning check, building POs, and keeping the system tuned.
      </p>

      <DocSection id="morning" title="Morning Check — 5 minutes">
        <p style={{ marginTop: 0 }}>
          One quick loop every morning keeps you on top of the whole catalogue.
        </p>
        <Steps
          items={[
            'Open Home → check the urgent count. Up from yesterday?',
            'Scan Priority SKUs → any IMMEDIATE tier items?',
            'If IMMEDIATE items exist → build a PO or investigate.',
            'Done.',
          ]}
        />
      </DocSection>

      <DocSection id="build-po" title="Building a PO Today">
        <p style={{ marginTop: 0 }}>
          Six steps from "we need to order" to a ready-to-send Excel file.
        </p>
        <Steps
          items={[
            'Navigate to the brand\'s SKU page.',
            'Click "Build PO" button.',
            'Review the suggested quantities — the system has already calculated lead time + coverage + buffer.',
            'Adjust quantities if needed (override any line item).',
            'Click "Export Excel" to download.',
            'Email the Excel to the supplier.',
          ]}
        />
        <CalloutBox type="info">
          The suggested quantity accounts for current stock, burn rate during lead time, coverage
          period after arrival, and safety buffer. If the number looks right, trust it.
        </CalloutBox>
      </DocSection>

      <DocSection id="monthly" title="Monthly Review">
        <p style={{ marginTop: 0 }}>
          Once a month, do a quick pass to keep the system calibrated.
        </p>
        <Steps
          items={[
            'Check Dead Stock page — anything to liquidate or bundle?',
            'Check Overrides page — any stale overrides to remove?',
            'Browse Brands overview — any trends changing (new urgent brands appearing)?',
            'Check Suppliers — are lead times still accurate? Any supplier switched to air freight?',
          ]}
        />
      </DocSection>

      <DocSection id="tuning" title="Tuning Buffers & Coverage">
        <p style={{ marginTop: 0 }}>
          The defaults work for most SKUs. Adjust when your situation is genuinely different.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '1rem',
            margin: '1rem 0',
          }}
        >
          <div
            style={{
              background: 'var(--docs-bg-card)',
              border: '1px solid var(--docs-border)',
              borderTop: '3px solid #f59e0b',
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: '0.85rem',
                color: '#d97706',
                marginBottom: '0.5rem',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Increase buffer when...
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: '1.1rem',
                color: 'var(--docs-text-secondary)',
                fontSize: '0.875rem',
                lineHeight: 1.8,
              }}
            >
              <li>Unreliable supplier (late deliveries)</li>
              <li>Long transit (sea freight with weather risk)</li>
              <li>Critical A-class items you can't afford to stock out</li>
            </ul>
          </div>
          <div
            style={{
              background: 'var(--docs-bg-card)',
              border: '1px solid var(--docs-border)',
              borderTop: '3px solid #22c55e',
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: '0.85rem',
                color: '#16a34a',
                marginBottom: '0.5rem',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Decrease buffer when...
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: '1.1rem',
                color: 'var(--docs-text-secondary)',
                fontSize: '0.875rem',
                lineHeight: 1.8,
              }}
            >
              <li>Fast resupply available (air freight, local supplier)</li>
              <li>Stable X-class demand (predictable sell-through)</li>
              <li>Cash-constrained — reduce buffer to free capital</li>
            </ul>
          </div>
        </div>

        <p
          style={{
            color: 'var(--docs-text-secondary)',
            fontSize: '0.875rem',
            marginBottom: '0.25rem',
          }}
        >
          Coverage auto-calculation:
        </p>
        <FormulaBlock>
          {`turns = min(max(1, 365 ÷ lead_time), 6)  →  coverage = 365 ÷ turns`}
        </FormulaBlock>
      </DocSection>

      <DocSection id="anomalies" title="Investigating Anomalies">
        <p style={{ marginTop: 0 }}>
          Something looks wrong? Start here.
        </p>
        <SimpleTable
          headers={['Symptom', 'Where to Look', 'Likely Cause']}
          rows={[
            [
              'Stock doesn\'t match UC',
              'Check drift log (Architecture docs)',
              'inventoryBlocked or missing PICKLIST',
            ],
            [
              'Velocity seems wrong',
              'SKU Detail → check in-stock days',
              'Long out-of-stock period diluting velocity',
            ],
            [
              'Status doesn\'t make sense',
              'SKU Detail → Calculation tab',
              'Override active, or edge case in formula',
            ],
            [
              'Suggested qty too high',
              'Check lead time + coverage settings',
              'Supplier lead time may be wrong',
            ],
            [
              'Brand shows zero data',
              'Check Parties page → channel rules',
              'New party not classified yet',
            ],
          ]}
        />
      </DocSection>
    </div>
  )
}
