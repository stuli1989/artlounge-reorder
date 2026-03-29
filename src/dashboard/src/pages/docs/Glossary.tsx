import DocSection from './components/DocSection'
import SearchableList from './components/SearchableList'

interface GlossaryEntry {
  term: string
  definition: string
  linkTo?: string
}

const GLOSSARY: GlossaryEntry[] = [
  { term: 'ABC Classification', definition: 'Revenue-based ranking. A = top 80% revenue, B = next 15%, C = bottom 5%.', linkTo: '/docs/calculations#abc' },
  { term: 'Buffer (Safety)', definition: 'Multiplier on coverage demand to protect against uncertainty. Default: A=1.3x, B=1.2x, C=1.1x.', linkTo: '/docs/calculations#buffer' },
  { term: 'Channel', definition: 'Sales channel: wholesale (dealers), online (Magento, Amazon, Flipkart), or store (Kala Ghoda retail).', linkTo: '/docs/calculations#channels' },
  { term: 'Coverage Period', definition: 'How many days of demand the order should cover after arrival. Auto-calculated from turns-per-year.', linkTo: '/docs/calculations#lead-time' },
  { term: 'Dead Stock', definition: 'Status: stock on hand but zero velocity. The product is available but nobody is buying it.', linkTo: '/docs/statuses#status-table' },
  { term: 'Drift', definition: 'Difference between forward-walked stock and UC inventory snapshot. Mostly caused by inventoryBlocked.', linkTo: '/docs/data-sources#drift' },
  { term: 'Facility', definition: 'UC warehouse location. Three facilities: Bhiwandi (main), Kala Ghoda (retail), Ali Bhiwandi (counting).', linkTo: '/docs/data-sources#facilities' },
  { term: 'Forward Walk', definition: 'Reconstructing stock positions day-by-day from Day 0 by applying each transaction.', linkTo: '/docs/calculations#positions' },
  { term: 'GRN', definition: 'Goods Received Note — a purchase receipt. Adds stock when goods arrive from supplier.' },
  { term: 'Healthy', definition: 'Status: stock is well above the reorder point. Pipeline is flowing, order on your normal cycle.', linkTo: '/docs/statuses#status-table' },
  { term: 'In-Stock Days', definition: 'Days when the SKU had stock available for sale. Out-of-stock days are excluded from velocity calculation.', linkTo: '/docs/calculations#velocity' },
  { term: 'Lead Time', definition: 'Days from placing an order to receiving goods. Default 90 days per supplier setting (engine fallback: 180 days if no supplier configured). Configurable per supplier on the Suppliers page.', linkTo: '/docs/calculations#lead-time' },
  { term: 'Lost Sales', definition: 'Status: zero stock with proven demand. You are actively losing revenue every day.', linkTo: '/docs/statuses#status-table' },
  { term: 'No Data', definition: 'Status: insufficient transaction history to make a recommendation.' },
  { term: 'Out of Stock', definition: 'Status: zero stock AND zero velocity. Demand is unknown — might sell if restocked.', linkTo: '/docs/statuses#status-table' },
  { term: 'PICKLIST', definition: 'UC entity recording items picked from warehouse for an order. Primary demand signal at Bhiwandi.', linkTo: '/docs/data-sources#order-lifecycle' },
  { term: 'Reorder', definition: 'Status: approaching the reorder point. Include this SKU in your next purchase order.', linkTo: '/docs/statuses#status-table' },
  { term: 'Shipping Package', definition: 'UC entity for a dispatched package. Used for Kala Ghoda demand since counter sales bypass PICKLIST.', linkTo: '/docs/data-sources#kg-shipping' },
  { term: 'Snapshot', definition: 'UC Inventory Snapshot — current sellable stock. The source of truth for "how much do we have now."', linkTo: '/docs/data-sources#hybrid-formula' },
  { term: 'Stockout', definition: 'When a product runs out of stock. Projected stockout date = today + days_to_stockout.', linkTo: '/docs/calculations#stockout' },
  { term: 'Transaction Ledger', definition: 'UC record of all stock movements — GRNs, picklists, adjustments, gatepasses.', linkTo: '/docs/data-sources#unicommerce' },
  { term: 'Unicommerce', definition: "Art Lounge's warehouse management and order processing system. The primary data source.", linkTo: '/docs/data-sources#unicommerce' },
  { term: 'Urgent', definition: 'Status: will stock out before the next shipment arrives. Order today.', linkTo: '/docs/statuses#status-table' },
  { term: 'Velocity', definition: 'How fast a product sells. Units sold ÷ in-stock days × 30 = monthly velocity.', linkTo: '/docs/calculations#velocity' },
  { term: 'XYZ Classification', definition: 'Demand variability ranking. X = stable (CV<0.5), Y = variable (0.5–1.0), Z = erratic (>1.0).', linkTo: '/docs/calculations#xyz' },
]

export default function Glossary() {
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
        Glossary
      </h1>
      <p
        style={{
          color: 'var(--docs-text-secondary)',
          fontSize: '1.05rem',
          marginBottom: '2.5rem',
          marginTop: 0,
        }}
      >
        A–Z reference for every term used in the system.
      </p>

      <DocSection id="glossary-az" title={`All Terms (${GLOSSARY.length})`}>
        <SearchableList entries={GLOSSARY} />
      </DocSection>
    </div>
  )
}
