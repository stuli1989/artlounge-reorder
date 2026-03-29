import DocSection from './components/DocSection'
import CalloutBox from './components/CalloutBox'

function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: '0.5rem',
        marginTop: '0.6rem',
        color: 'var(--docs-text-muted)',
        fontSize: '0.82rem',
        lineHeight: 1.55,
      }}
    >
      <span style={{ flexShrink: 0, fontWeight: 600 }}>Tip:</span>
      <span>{children}</span>
    </div>
  )
}

export default function DashboardGuide() {
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
        Using the Dashboard
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.05rem',
          marginBottom: '2.5rem',
          marginTop: 0,
        }}
      >
        Page by page — what each screen shows and what you can do.
      </p>

      <DocSection id="page-home" title="Home">
        <p style={{ marginTop: 0 }}>
          Command center. Shows the urgent count, priority brands, and quick access to what needs
          attention today.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Click the <strong>Urgent</strong> card to jump to Priority SKUs.</li>
          <li>Click any brand row to drill into its SKUs.</li>
        </ul>
        <Tip>The number in the red card is your most important daily metric.</Tip>
      </DocSection>

      <DocSection id="page-brands" title="Brands">
        <p style={{ marginTop: 0 }}>
          All 172 brands sorted by urgency — most urgent first. One row per brand, showing its
          urgent + reorder counts at a glance.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Click a brand to see all its SKUs.</li>
          <li>Filter by name. Toggle sort columns to re-rank.</li>
        </ul>
        <Tip>Brands with zero urgent + zero reorder are fully stocked.</Tip>
      </DocSection>

      <DocSection id="page-sku" title="SKU Detail">
        <p style={{ marginTop: 0 }}>
          Expand any SKU row to see velocity breakdown, stock timeline, and raw transactions.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Click the <strong>Calculation</strong> tab for a full formula walkthrough.</li>
          <li>Set overrides for stock or velocity. Change reorder intent.</li>
        </ul>
        <Tip>The timeline chart lets you drag to filter transactions by date range.</Tip>
      </DocSection>

      <DocSection id="page-priority" title="Priority SKUs">
        <p style={{ marginTop: 0 }}>
          Triage view — all urgent + reorder items grouped into IMMEDIATE / URGENT / WATCH tiers.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Filter by status or ABC class to narrow focus.</li>
          <li>Click any item to navigate to its brand.</li>
        </ul>
        <Tip>
          IMMEDIATE tier = A-class items with &lt;7 days of stock. These are your top revenue
          drivers about to run out.
        </Tip>
      </DocSection>

      <DocSection id="page-po" title="Build PO">
        <p style={{ marginTop: 0 }}>
          Generate a purchase order for a brand with system-suggested quantities.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Select brand → review suggestions → adjust quantities → Export Excel → send to supplier.</li>
          <li>Adjust any line item quantity before exporting.</li>
        </ul>
        <Tip>
          Use "Custom Date Range" to recalculate velocity based on a specific period (e.g., last 90
          days only).
        </Tip>
      </DocSection>

      <DocSection id="page-dead-stock" title="Dead Stock">
        <p style={{ marginTop: 0 }}>
          Items with stock on hand but no recent sales. Something is wrong — or intentional.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Review and mark as do-not-reorder if the slowdown is intentional.</li>
          <li>Flag slow movers for investigation — pricing, listing, or product issues.</li>
        </ul>
      </DocSection>

      <DocSection id="page-overrides" title="Overrides">
        <p style={{ marginTop: 0 }}>
          Manual adjustments to stock or velocity for specific SKUs. All active overrides in one
          place.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>See every active override and when it was set.</li>
          <li>Check for stale overrides where reality has drifted from your adjustment.</li>
        </ul>
        <Tip>Stale overrides are flagged with an amber warning. Review and remove them regularly.</Tip>
      </DocSection>

      <DocSection id="page-suppliers" title="Suppliers">
        <p style={{ marginTop: 0 }}>
          Manage supplier lead times per brand. This drives every reorder recommendation.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Set default lead time for sea or air freight per supplier.</li>
          <li>Set typical order months to control the coverage period calculation.</li>
        </ul>
        <Tip>
          Getting lead time right is crucial — a wrong number here flows through to every SKU in that
          brand.
        </Tip>
      </DocSection>

      <DocSection id="page-parties" title="Parties">
        <p style={{ marginTop: 0 }}>
          Channel classification rules. Maps transaction parties to wholesale / online / store /
          supplier channels.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Review auto-classifications to check they're correct.</li>
          <li>Add custom rules for any new party that appears as unclassified.</li>
        </ul>
      </DocSection>

      <DocSection id="page-settings" title="Settings">
        <p style={{ marginTop: 0 }}>
          System-wide configuration that affects all calculations.
        </p>
        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', lineHeight: 1.8, color: 'var(--docs-text-secondary)', fontSize: '0.9rem' }}>
          <li>Set the analysis period (how many months of history to use for velocity).</li>
          <li>Toggle buffer mode: ABC only vs ABC × XYZ.</li>
          <li>Set default velocity type: flat average vs weighted moving average.</li>
        </ul>
        <CalloutBox type="warning" title="Changes affect all SKUs">
          Settings changes recalculate the entire system on the next sync. If something looks
          off after changing a setting, that's likely why.
        </CalloutBox>
      </DocSection>
    </div>
  )
}
