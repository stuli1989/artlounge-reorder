import DocSection from './components/DocSection'
import FlowDiagram from './components/FlowDiagram'
import CalloutBox from './components/CalloutBox'

export default function Overview() {
  return (
    <div>
      <h1 style={{ color: 'var(--docs-text)', fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>
        Overview
      </h1>
      <p style={{ color: 'var(--docs-text-secondary)', marginBottom: '2rem' }}>
        Coming soon — full system overview.
      </p>

      <DocSection id="intro" title="What is this?">
        <p>
          This documentation explains how the Art Lounge reorder intelligence system works —
          where data comes from, how metrics are calculated, and how to use the dashboard day-to-day.
        </p>
      </DocSection>

      <DocSection id="flow">
        <FlowDiagram
          nodes={[
            { icon: '📦', title: 'Unicommerce', subtitle: 'Orders & stock', color: 'teal' },
            { icon: '⚙️', title: 'Pipeline', subtitle: 'Nightly sync', color: 'amber' },
            { icon: '📊', title: 'Dashboard', subtitle: 'Reorder signals', color: 'green' },
          ]}
        />
      </DocSection>

      <CalloutBox type="notice" title="Work in progress">
        Full chapter content is being written. Check back soon.
      </CalloutBox>
    </div>
  )
}
