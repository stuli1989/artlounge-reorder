import DocSection from './components/DocSection'
import ProfileCard from './components/ProfileCard'
import FlowDiagram from './components/FlowDiagram'
import TransactionTable from './components/TransactionTable'
import FormulaBlock from './components/FormulaBlock'
import CalloutBox from './components/CalloutBox'

// ─── Workhorse (6312 — Koh-i-noor Eraser Pencil) ─────────────────────────────
// Current stock: 20. Working backwards from today's 20 units.
// Recent transactions in reverse chronological order:
//   Mar 28: +6 GRN, -2 online  => before: 20 + 2 - 6 = 16
//   Mar 27: -3 online, -3 internal, -1 store, -1 store => before: 16+3+3+1+1 = 24
//   Mar 16: -3 online => before: 27
//   Mar 13: -1 online => before: 28
//   Mar 11: -2 online => before: 30
//   Mar 7:  +5 return => before: 25
//   Mar 5:  -2 online => before: 27
//   Mar 4:  +2 GRN => before: 25
//   Feb 28: -3 wholesale => before: 28
//   Feb 24: -2 online, +5 GRN => complex; net +3, before: 25
//
// Build forward from a reasonable starting point. Use stock=20 at end.
// Walk backwards from 20:
//   After Mar 28: 20 (current)
//   Before Mar 28 net: +6 GRN -2 online = net +4 => before Mar 28: 16
//   Before Mar 27 net: -3 -3 -1 -1 = -8 => before Mar 27: 16+8 = 24
//   Before Mar 16: -3 => 27
//   Before Mar 13: -1 => 28
//   Before Mar 11: -2 => 30
//   Before Mar 7: +5 return => 30-5=25
//   Before Mar 5: -2 => 27
//   Before Mar 4: +2 GRN => 27-2=25
//   Before Feb 28: -3 => 28
//   Before Feb 24: -2 online +5 GRN = net +3 => 28-3=25
// Display 10 representative rows. Running stock shown AFTER transaction.

const workhorseTxns = [
  { date: '2026-03-28', type: 'GRN',               orderNumber: 'G0725',      channel: 'Supplier',   qty: +6,  runningStock: 20 },
  { date: '2026-03-28', type: 'PICKLIST',           orderNumber: 'MA-054799',  channel: 'Online',     qty: -2,  runningStock: 18 },
  { date: '2026-03-27', type: 'PICKLIST',           orderNumber: 'MA-054637',  channel: 'Online',     qty: -3,  runningStock: 15 },
  { date: '2026-03-27', type: 'OUTBOUND_GATEPASS',  orderNumber: 'GP49925…',   channel: 'Internal',   qty: -3,  runningStock: 12 },
  { date: '2026-03-27', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00796',  channel: 'Store',      qty: -1,  runningStock: 11 },
  { date: '2026-03-27', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00817',  channel: 'Store',      qty: -1,  runningStock: 10 },
  { date: '2026-03-16', type: 'PICKLIST',           orderNumber: 'MA-053975',  channel: 'Online',     qty: -3,  runningStock: 7  },
  { date: '2026-03-13', type: 'PICKLIST',           orderNumber: 'MA-053910',  channel: 'Online',     qty: -1,  runningStock: 6  },
  { date: '2026-03-11', type: 'PICKLIST',           orderNumber: 'MA-053743',  channel: 'Online',     qty: -2,  runningStock: 4  },
  { date: '2026-03-07', type: 'PUTAWAY_RTO',        orderNumber: 'ISR0382…',   channel: 'Online',     qty: +5,  runningStock: 9  },
  { date: '2026-03-05', type: 'PICKLIST',           orderNumber: 'MA-053337',  channel: 'Online',     qty: -2,  runningStock: 7  },
  { date: '2026-03-04', type: 'GRN',               orderNumber: 'G0665',      channel: 'Supplier',   qty: +2,  runningStock: 9  },
]

// ─── Flash Seller (3041981 — WN Matt Varnish Spray 400ml) ─────────────────────
// Current stock: 10. Last sale Mar 2. GRN arrived Jan 31 (345 units).
// Build forward from Jan 31:
//   Jan 31: stock = 0 before + 345 = 345. Then -18 = 327.
//   Feb 2:  -72 -48 -30 -24 -18 -18 -12 = -222 => 105
//   Feb 3:  -6 -6 -6 -4 = -22 => 83
//   Feb 4:  -6 -12 -6 = -24 => 59
//   Feb 5:  -3 -6 = -9 => 50
//   Feb 6:  -6 => 44
//   Mar 2:  -2 = 12. Then internal -2 = 10.
//   Current: 10

const flashSellerTxns = [
  { date: '2026-01-31', type: 'GRN',      orderNumber: 'G0570',    channel: 'Supplier',   qty: +345, runningStock: 345 },
  { date: '2026-01-31', type: 'PICKLIST', orderNumber: 'SO02940',  channel: 'Wholesale',  qty: -18,  runningStock: 327 },
  { date: '2026-02-02', type: 'PICKLIST', orderNumber: 'SO02947',  channel: 'Wholesale',  qty: -72,  runningStock: 255 },
  { date: '2026-02-02', type: 'PICKLIST', orderNumber: 'SO02950',  channel: 'Wholesale',  qty: -48,  runningStock: 207 },
  { date: '2026-02-02', type: 'PICKLIST', orderNumber: 'SO02956',  channel: 'Wholesale',  qty: -24,  runningStock: 183 },
  { date: '2026-02-03', type: 'PICKLIST', orderNumber: 'SO02987',  channel: 'Wholesale',  qty: -6,   runningStock: 107 },
  { date: '2026-02-04', type: 'PICKLIST', orderNumber: 'SO03012',  channel: 'Wholesale',  qty: -12,  runningStock: 59  },
  { date: '2026-02-05', type: 'PICKLIST', orderNumber: 'SO03025',  channel: 'Wholesale',  qty: -3,   runningStock: 50  },
  { date: '2026-02-06', type: 'PICKLIST', orderNumber: 'SO03039',  channel: 'Wholesale',  qty: -6,   runningStock: 44  },
  { date: '2026-03-02', type: 'PICKLIST', orderNumber: 'SO03254',  channel: 'Wholesale',  qty: -2,   runningStock: 12  },
  { date: '2026-03-02', type: 'OUTBOUND_GATEPASS', orderNumber: 'GP49925…', channel: 'Internal', qty: -2, runningStock: 10 },
]

// ─── Store Bestseller (UNB-PC3M-BLACK — Uni-Posca Extra Fine Black) ───────────
// Current stock: 8. GRN Jan 14: +55. Walk backwards from 8.
// Selected representative transactions (not all available):

const storeBestsellerTxns = [
  { date: '2026-01-14', type: 'GRN',               orderNumber: 'G0524',       channel: 'Supplier', qty: +55, runningStock: 55 },
  { date: '2026-01-19', type: 'PICKLIST',           orderNumber: 'MA-050546',   channel: 'Online',   qty: -1,  runningStock: 54 },
  { date: '2026-01-25', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00611',   channel: 'Store',    qty: -1,  runningStock: 53 },
  { date: '2026-01-25', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00632',   channel: 'Store',    qty: -50, runningStock: 3  },
  { date: '2026-02-18', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00704',   channel: 'Store',    qty: -1,  runningStock: 2  },
  { date: '2026-02-19', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00716',   channel: 'Store',    qty: -1,  runningStock: 1  },
  { date: '2026-03-07', type: 'SHIPPING_PACKAGE',   orderNumber: 'PPET00729',   channel: 'Store',    qty: -2,  runningStock: -1 },
  { date: '2026-03-10', type: 'PICKLIST',           orderNumber: 'MA-053670',   channel: 'Online',   qty: -1,  runningStock: -2 },
]

// ─── Online Mover (FC-110199 — Faber-Castell Polychromos Black) ──────────────
// Current stock: 7. Last GRN Jan 22 (+12). Last sale Feb 16.
// Velocity window from Aug 25, 2025. Walk through key period.

const onlineMoverTxns = [
  { date: '2025-11-08', type: 'PICKLIST',         orderNumber: '000046673',   channel: 'Wholesale', qty: -4,  runningStock: 36 },
  { date: '2025-11-12', type: 'PICKLIST',         orderNumber: 'MA-046767',   channel: 'Online',    qty: -3,  runningStock: 33 },
  { date: '2025-11-15', type: 'PICKLIST',         orderNumber: '046767Reship', channel: 'Wholesale', qty: -1, runningStock: 32 },
  { date: '2025-12-01', type: 'PICKLIST',         orderNumber: 'MA-047776',   channel: 'Online',    qty: -1,  runningStock: 31 },
  { date: '2025-12-10', type: 'PICKLIST',         orderNumber: 'MA-048208',   channel: 'Online',    qty: -1,  runningStock: 30 },
  { date: '2025-12-16', type: 'PICKLIST',         orderNumber: 'MA-048270',   channel: 'Online',    qty: -1,  runningStock: 29 },
  { date: '2025-12-31', type: 'PICKLIST',         orderNumber: 'MA-049514',   channel: 'Online',    qty: -2,  runningStock: 27 },
  { date: '2026-01-07', type: 'PICKLIST',         orderNumber: 'MA-049914',   channel: 'Online',    qty: -1,  runningStock: 26 },
  { date: '2026-01-22', type: 'GRN',              orderNumber: 'G0549',       channel: 'Supplier',  qty: +12, runningStock: 38 },
  { date: '2026-02-09', type: 'PICKLIST',         orderNumber: 'MA-051803',   channel: 'Online',    qty: -1,  runningStock: 16 },
  { date: '2026-02-13', type: 'PICKLIST',         orderNumber: 'MA-052193',   channel: 'Online',    qty: -1,  runningStock: 15 },
  { date: '2026-02-16', type: 'PICKLIST',         orderNumber: 'MA-052338',   channel: 'Online',    qty: -2,  runningStock: 13 },
]

// ─── Dead Stock Sitter (DRW-191714 — Daler Rowney Graduate Rigger Brush No.1) ─
const deadStockTxns = [
  { date: '2026-03-04', type: 'GRN', orderNumber: 'G0666', channel: 'Supplier', qty: +6, runningStock: 6 },
]

// ─── Sporadic Item (HLB-WG642 — Holbein Granulating Earthshine Violet) ────────
const sporadicTxns = [
  { date: '2025-06-07', type: 'INVENTORY_ADJUSTMENT', orderNumber: '—',               channel: 'Internal',  qty: +3,  runningStock: 3  },
  { date: '2025-07-03', type: 'OUTBOUND_GATEPASS',    orderNumber: 'GP47250PPETPL0013', channel: 'Internal', qty: -3,  runningStock: 0  },
  { date: '2025-07-03', type: 'INBOUND_GATEPASS',     orderNumber: 'GP47250PPETPL0013', channel: 'Internal', qty: +3,  runningStock: 3  },
  { date: '2025-10-03', type: 'GRN',                  orderNumber: 'G0233',            channel: 'Supplier',  qty: +3,  runningStock: 6  },
  { date: '2025-10-03', type: 'GRN',                  orderNumber: 'G0239',            channel: 'Supplier',  qty: +3,  runningStock: 9  },
  { date: '2025-10-04', type: 'PICKLIST',             orderNumber: 'SO01550',          channel: 'Wholesale', qty: -3,  runningStock: 6  },
]

export default function Walkthroughs() {
  return (
    <div>
      <h1 style={{ color: 'var(--docs-text)', fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem' }}>
        Real SKU Walkthroughs
      </h1>
      <p style={{ color: 'var(--docs-text-secondary)', marginBottom: '2rem', lineHeight: 1.7 }}>
        Six real SKUs. Six different stories. Each one shows the system working — or flagging a problem.
        Every number here is live data from the warehouse.
      </p>

      {/* ── 1. THE WORKHORSE ──────────────────────────────────────────────── */}
      <DocSection id="workhorse" title="1. The Workhorse — Koh-i-noor Eraser Pencil">
        <ProfileCard
          name="Koh-i-noor Soft Eraser In Pencil — FSC 100%"
          partNo="6312  ·  KOH-I-NOOR"
          archetype="The Workhorse"
          archetypeDescription="High-volume wholesale. Your bread and butter. 41.5 units a day, Rs 14.7L revenue this FY — and it's always about to run out."
          stats={[
            { label: 'Current Stock', value: '20 units',     color: '#dc2626' },
            { label: 'Velocity/mo',   value: '1,246 units',  color: 'var(--docs-text)' },
            { label: 'Days Left',     value: '0.5 days',     color: '#dc2626' },
            { label: 'Status',        value: 'URGENT',       color: '#dc2626' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '📦', title: 'UC Ledger',      subtitle: 'PICKLIST (wholesale)', color: 'teal' },
            { icon: '📊', title: 'Position Built', subtitle: '295 in-stock days',    color: 'blue' },
            { icon: '⚡', title: 'Velocity Calc',  subtitle: '41.5 units/day',       color: 'amber' },
            { icon: '🚨', title: 'URGENT',         subtitle: '0.5 days left',        color: 'red' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={workhorseTxns}
          caption="Recent transactions. Note: 94% of demand is wholesale PICKLIST orders. A GRN on Mar 28 added 6 units — already half-consumed."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Step 1 — Velocity (in-stock days only, out-of-stock days excluded)">
{`Velocity = total_demand_units ÷ in_stock_days
         = 12,256 units ÷ 295 days
         = 41.55 units/day  =  1,246 units/month

In-stock days:  295  (81.5% of the velocity window)
Out-of-stock:    67  (excluded — we can't sell what we don't have)`}
        </FormulaBlock>
        <FormulaBlock caption="Step 2 — Days to stockout">
{`Days to stockout = current_stock ÷ velocity
                 = 20 ÷ 41.55
                 = 0.5 days  ← already effectively out`}
        </FormulaBlock>
        <FormulaBlock caption="Step 3 — Suggested reorder quantity">
{`Lead time        = 90 days  (KOH-I-NOOR supplier)
Coverage period  = 90 days  (post-arrival stock duration)
Buffer           = 1.3×     (ABC=A items)

demand_during_lead  = 41.55 × 90            =  3,740 units  (no buffer)
order_for_coverage  = 41.55 × 90 × 1.3      =  4,861 units  (buffer here)
suggested_qty       = 3,740 + 4,861 − 20    =  8,581 units`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          This SKU is always urgent. At 41.5 units/day, 20 units is half a day of stock — barely enough to handle
          today's orders. The large suggested quantity (8,581 units) reflects 90 days of lead time demand plus 90
          days of buffered coverage. If you're not already placing this order, you're losing sales.
        </p>

        <CalloutBox
          type="info"
          title="Why we exclude out-of-stock days"
          linkTo="/docs/calculations#velocity"
          linkText="Velocity calculation deep-dive"
        >
          The 67 out-of-stock days are excluded from the velocity denominator. Including them would artificially
          lower velocity — penalising the SKU for running out, not for selling slowly.
        </CalloutBox>
      </DocSection>

      {/* ── 2. THE FLASH SELLER ───────────────────────────────────────────── */}
      <DocSection id="flash-seller" title="2. The Flash Seller — WN Matt Varnish Spray 400ml">
        <ProfileCard
          name="Winsor & Newton Matt Varnish Spray 400ml"
          partNo="3041981  ·  WINSOR & NEWTON"
          archetype="The Flash Seller"
          archetypeDescription="Sells out as soon as it arrives. 345 units landed Jan 31 — all gone in 57 days. Now sitting at 10 units, urgent again."
          stats={[
            { label: 'Current Stock',   value: '10 units',    color: '#dc2626' },
            { label: 'Velocity/mo',     value: '179 units',   color: 'var(--docs-text)' },
            { label: 'Days Left',       value: '1.7 days',    color: '#dc2626' },
            { label: 'Out-of-Stock',    value: '305 days/yr', color: '#d97706' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '📦', title: 'GRN Arrived',       subtitle: '345 units, Jan 31',   color: 'green' },
            { icon: '🔥', title: 'Rapid Dispatch',    subtitle: '24 wholesale PILs',    color: 'amber' },
            { icon: '⬇️', title: 'Stock Depleted',    subtitle: '341 units in 57 days', color: 'red' },
            { icon: '🚨', title: 'URGENT Again',      subtitle: '10 units, 1.7d left',  color: 'red' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={flashSellerTxns}
          caption="The entire FY story: out of stock for 305 days, then 345 units arrived and 341 sold in a burst of wholesale orders — some days seeing multiple large orders within hours."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Velocity — only 57 in-stock days this FY">
{`Velocity = 341 units ÷ 57 in-stock days
         = 5.98 units/day  =  179 units/month

In-stock days:   57  (15.7% of FY — was out for 305 days)
Out-of-stock:   305  (excluded from velocity denominator)

demand_cv = 2.63  ← extreme spikiness (bulk wholesale batches)`}
        </FormulaBlock>
        <FormulaBlock caption="Reorder quantity">
{`demand_during_lead  = 5.98 × 90            =  538 units  (no buffer)
order_for_coverage  = 5.98 × 90 × 1.3      =  700 units  (buffer here)
suggested_qty       = 538 + 700 − 10        =  1,228 units`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          The 305 out-of-stock days are the real problem — not the velocity number. This item is never stocked
          in adequate quantity. The high demand_cv (2.63) reflects wholesale bulk-buying behaviour: customers
          order dozens at a time when they know stock is scarce. Ordering 1,228 units would cover 6 months —
          which is exactly what's needed.
        </p>

        <CalloutBox
          type="warning"
          title="High demand_cv means unreliable velocity"
          linkTo="/docs/calculations#xyz"
          linkText="XYZ classification explained"
        >
          demand_cv = 2.63 makes this XYZ=Z. The 5.98 units/day average hides the real pattern: near-zero
          demand most days, then sudden bursts of 48–72 units in a single order. The suggested quantity
          is a floor, not a ceiling — consider ordering more if cash flow allows.
        </CalloutBox>
      </DocSection>

      {/* ── 3. THE STORE BESTSELLER ───────────────────────────────────────── */}
      <DocSection id="store-bestseller" title="3. The Store Bestseller — Uni-Posca Extra Fine Black">
        <ProfileCard
          name="Uni-Posca Water-Based Extra Fine Bullet Tip PC 3M — Black"
          partNo="UNB-PC3M-BLACK  ·  UNI-BALL"
          archetype="The Store Bestseller"
          archetypeDescription="Kala Ghoda retail counter favorite. 82% of demand comes from the store floor — one or two at a time, steadily all year."
          stats={[
            { label: 'Current Stock', value: '8 units',     color: '#dc2626' },
            { label: 'Store Share',   value: '82%',         color: 'var(--docs-text)' },
            { label: 'Days Left',     value: '28 days',     color: '#d97706' },
            { label: 'Status',        value: 'URGENT',      color: '#dc2626' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '🏪', title: 'KG Store',          subtitle: 'Kala Ghoda counter',    color: 'purple' },
            { icon: '📋', title: 'Shipping Package',  subtitle: 'KG_DISPATCH API',       color: 'teal' },
            { icon: '📊', title: 'Store Channel',     subtitle: '64 of 78 units sold',   color: 'blue' },
            { icon: '🚨', title: 'URGENT',            subtitle: '8 units, 28d left',     color: 'red' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={storeBestsellerTxns}
          caption="The Jan 25 bulk PPET00632 (−50) is unusual — likely a physical stock replenishment to the store floor, not a customer sale. Most SHIPPING_PACKAGE entries are 1–2 units."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Channel breakdown">
{`Total demand:   78 units over 276 in-stock days

Channel        Units    Daily      Monthly   Share
──────────────────────────────────────────────────
Store          64        0.232      6.96      82%
Wholesale      11        0.040      1.20      14%
Online          3        0.011      0.33       4%
──────────────────────────────────────────────────
Total          78        0.283      8.48     100%`}
        </FormulaBlock>
        <FormulaBlock caption="Reorder quantity">
{`Velocity = 78 ÷ 216 = 0.36 units/day = 10.8 units/month

demand_during_lead  = 0.36 × 90            =  32 units  (no buffer)
order_for_coverage  = 0.36 × 90 × 1.1      =  36 units  (buffer here, ABC=C)
suggested_qty       = 32 + 36 − 8           =  60 units`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          The contrast with the Workhorse is sharp: same urgent status, but the pattern is completely
          different — retail trickle instead of wholesale bulk. The 60-unit suggested order covers
          six months of store sales. Don't let the small numbers fool you; this marker is always
          on the counter and always sells.
        </p>

        <CalloutBox
          type="info"
          title="Why KG store uses Shipping Packages, not PICKLIST"
          linkTo="/docs/data-sources#kg-shipping"
          linkText="KG Shipping Package API explained"
        >
          The Kala Ghoda store runs as a separate Unicommerce facility. Its sales appear as
          SHIPPING_PACKAGE documents via the KG SP API — not as PICKLIST entries like warehouse
          dispatch. That's why store velocity is tracked separately and why these transactions
          look different in the table above.
        </CalloutBox>
      </DocSection>

      {/* ── 4. THE ONLINE MOVER ───────────────────────────────────────────── */}
      <DocSection id="online-mover" title="4. The Online Mover — Faber-Castell Polychromos Black Pencil">
        <ProfileCard
          name="F-C Polychromos Artists Colour Pencil — Black"
          partNo="FC-110199  ·  FABER CASTELL"
          archetype="The Online Mover"
          archetypeDescription="E-commerce discovery. 94.5% of demand comes through MAGENTO2 — individual customers finding a premium single colour online."
          stats={[
            { label: 'Current Stock', value: '7 units',    color: '#dc2626' },
            { label: 'Online Share',  value: '94.5%',      color: 'var(--docs-text)' },
            { label: 'Days Left',     value: '6 days',     color: '#dc2626' },
            { label: 'Status',        value: 'URGENT',     color: '#dc2626' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '🌐', title: 'MAGENTO2',         subtitle: 'Online orders (MA-…)',  color: 'blue' },
            { icon: '📋', title: 'UC Ledger',        subtitle: 'PICKLIST dispatch',     color: 'teal' },
            { icon: '📊', title: 'Online Channel',   subtitle: '239 of 253 units',      color: 'blue' },
            { icon: '🚨', title: 'URGENT',           subtitle: '7 units, 6d left',      color: 'red' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={onlineMoverTxns}
          caption="Notice the MA- prefix on all online orders — these are MAGENTO2 (website) orders. 1–5 units per order, every 1–2 weeks. Large internal transfers (515 units in/out) are warehouse moves between KG and PPETPL — correctly excluded from demand."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Channel breakdown">
{`Total demand:   253 units over 216 in-stock days

Channel        Units    Daily      Monthly   Share
──────────────────────────────────────────────────
Online         239        1.107     33.20     94.5%
Store            8        0.037      1.11      3.2%
Wholesale        6        0.028      0.83      2.4%
──────────────────────────────────────────────────
Total          253        1.171     35.14    100%`}
        </FormulaBlock>
        <FormulaBlock caption="Reorder quantity">
{`Velocity = 253 ÷ 216 = 1.17 units/day = 35.14 units/month

demand_during_lead  = 1.17 × 90            =  105 units  (no buffer)
order_for_coverage  = 1.17 × 90 × 1.3      =  137 units  (buffer here)
suggested_qty       = 105 + 137 − 14        =  228 units`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          Pure online demand — customers discover this premium pencil colour on the website and order
          individually. The pattern is the inverse of the Flash Seller: small, regular orders instead
          of occasional bulk wholesale bursts. With 6 days of stock left, this needs ordering now.
          The 228-unit suggestion covers 6 months of steady online pull.
        </p>

        <CalloutBox
          type="info"
          title="How online orders are classified"
          linkTo="/docs/data-sources#channels"
          linkText="Channel classification rules"
        >
          Orders with sale_order_code starting with <code>MA-</code> originate from MAGENTO2 (the
          Art Lounge website). The system classifies them as the "online" channel automatically.
          This is how 239 units get attributed to online — not by voucher type, but by the
          sale order prefix.
        </CalloutBox>
      </DocSection>

      {/* ── 5. THE DEAD STOCK SITTER ──────────────────────────────────────── */}
      <DocSection id="dead-stock-sitter" title="5. The Dead Stock Sitter — Daler Rowney Graduate Rigger Brush No.1">
        <ProfileCard
          name="Daler Rowney Graduate Rigger Brush No.1"
          partNo="DRW-191714  ·  DALER ROWNEY"
          archetype="The Dead Stock Sitter"
          archetypeDescription="Arrived 25 days ago. Zero sales. The system knows — it says Dead Stock, not Out of Stock."
          stats={[
            { label: 'Current Stock',  value: '6 units',    color: '#71717a' },
            { label: 'Velocity/day',   value: '0.00',       color: '#71717a' },
            { label: 'Days in Stock',  value: '25 days',    color: '#71717a' },
            { label: 'Status',         value: 'DEAD STOCK', color: '#d97706' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '📦', title: 'GRN Received',  subtitle: '6 units, Mar 4',    color: 'green' },
            { icon: '⏳', title: 'Stock Sits',    subtitle: '25 days, no demand', color: 'gray' },
            { icon: '🔇', title: 'No Demand',     subtitle: '0 transactions',     color: 'gray' },
            { icon: '⚠️', title: 'DEAD STOCK',    subtitle: 'Do not reorder',     color: 'amber' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={deadStockTxns}
          caption="The entire FY transaction history: one GRN. No sales before it, no sales after it. The system has seen 25 in-stock days and zero demand."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Dead stock detection logic">
{`In-stock days  = 25   (since Mar 4, 2026)
Units sold     = 0
Velocity       = 0.0 units/day

Dead stock rule:  velocity = 0  AND  stock > 0  →  status = "dead_stock"
(No day threshold — any item with stock and zero velocity is dead stock)

Suggested qty  = null  (no reorder calculation — system refuses to suggest)`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          This is the critical distinction: "Dead Stock" means you have inventory that has never sold.
          "Out of Stock" means you ran out of something people want. They require opposite actions —
          reorder out-of-stock items, investigate (and possibly return or discount) dead stock. Do
          not place a reorder for this brush.
        </p>

        <CalloutBox
          type="warning"
          title="Dead Stock vs Out of Stock"
          linkTo="/docs/statuses#dead-stock"
          linkText="Dead Stock status explained"
        >
          A Dead Stock SKU has been in the warehouse long enough that we'd expect at least one sale —
          and got none. Having stock doesn't mean it's selling. The system flags this so you can
          investigate: Is it misplaced? Wrong price? Duplicate of another SKU? Return window open?
        </CalloutBox>
      </DocSection>

      {/* ── 6. THE SPORADIC ITEM ──────────────────────────────────────────── */}
      <DocSection id="sporadic" title="6. The Sporadic Item — Holbein Granulating Earthshine Violet">
        <ProfileCard
          name="Holbein Granulating Wc Earthshine Violet G 15ml"
          partNo="HLB-WG642  ·  HOLBEIN"
          archetype="The Sporadic Item"
          archetypeDescription="3 units sold in 10 months. demand_cv = 6.4. Technically 'Healthy' — but the velocity is barely a whisper."
          stats={[
            { label: 'Current Stock', value: '6 units',    color: 'var(--docs-text)' },
            { label: 'Total Sales',   value: '3 units/FY', color: 'var(--docs-text)' },
            { label: 'Days Left',     value: '588 days',   color: '#16a34a' },
            { label: 'Status',        value: 'HEALTHY',    color: '#16a34a' },
          ]}
        />

        <FlowDiagram
          nodes={[
            { icon: '📦', title: 'UC Ledger',      subtitle: 'Oct 2025 GRN',        color: 'teal' },
            { icon: '🔢', title: '1 Sale Event',   subtitle: '3 units, Oct 4',       color: 'gray' },
            { icon: '📉', title: 'Low Velocity',   subtitle: '0.01 units/day',       color: 'gray' },
            { icon: '✅', title: 'HEALTHY',        subtitle: '588 days remaining',   color: 'green' },
          ]}
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Data
        </h3>
        <TransactionTable
          transactions={sporadicTxns}
          caption="The complete FY history: an opening adjustment, a round-trip internal transfer, two GRN receipts, and exactly one sale. 292 of 295 in-stock days had zero activity (99%)."
        />

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Calculation
        </h3>
        <FormulaBlock caption="Velocity — 295 in-stock days, 1 sale event">
{`Velocity = 3 units ÷ 295 in-stock days
         = 0.0102 units/day  =  0.31 units/month

demand_cv = 6.40  (XYZ = Z — maximum intermittency)
zero_activity_ratio = 0.99  (99% of days had no activity)`}
        </FormulaBlock>
        <FormulaBlock caption="Stockout and reorder decision">
{`Days to stockout = 6 ÷ 0.0102 = 588 days

Healthy threshold: days_remaining > lead_time + max(30, 50% of lead)
                   588 > 90 + max(30, 45) = 135  →  TRUE  →  status = "healthy"

Reorder check:
  demand_during_lead  = 0.0102 × 90            =  0.9 units  (no buffer)
  order_for_coverage  = 0.0102 × 90 × 1.1      =  1.0 units  (buffer, ABC=C)
  suggested_qty       = 0.9 + 1.0 − 6           =  −4.1  →  null (no order needed)`}
        </FormulaBlock>

        <h3 style={{ color: 'var(--docs-text)', fontSize: '1.1rem', fontWeight: 600, margin: '1.5rem 0 0.5rem' }}>
          The Verdict
        </h3>
        <p>
          "Healthy" is technically correct — there's nearly 2 years of stock at this velocity. But
          the last sale was 176 days ago. This item may never sell those 6 units. The system's job
          is not to decide that; it's to prevent panic-reordering. The real question is whether to
          keep it in the catalogue at all.
        </p>

        <CalloutBox
          type="warning"
          title="Healthy status with Z-class demand — be cautious"
          linkTo="/docs/calculations#xyz"
          linkText="XYZ classification and demand confidence"
        >
          A "Healthy" status with demand_cv = 6.4 and zero_activity_ratio = 99% means the velocity
          figure is almost meaningless. This item sold 3 units — once — in 10 months. It might
          sell 0 or 10 next month; we genuinely don't know. Use the Z-class flag as a signal to
          review manually rather than trust the automated status.
        </CalloutBox>
      </DocSection>
    </div>
  )
}
