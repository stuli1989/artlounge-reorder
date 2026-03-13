// ═══════════════════════════════════════════════════════
// SKU DATA — all from real database queries (March 2026)
// Active days = days with stock > 0 OR real sales occurred
// ═══════════════════════════════════════════════════════
var SKUS = [
  {
    id: 'burnt-sienna',
    name: 'WN AOC 37ML BURNT SIENNA',
    short: 'Burnt Sienna',
    desc: 'Winsor & Newton oil colour, 37ml tube',
    brand: 'WINSOR & NEWTON',
    scenario: '94% wholesale',
    stock: 18, isd: 121, totalDays: 347, lastSale: 'Feb 26',
    wv: 1.2810, ov: 0.0909, sv: 0.0083,
    wsDemand: 155, onDemand: 11, stDemand: 1,
    wsTxns: 39, onTxns: 10, stTxns: 1,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 2257, inStock: 1030, critical: 275 },
    txns: [
      { dt:'Feb 26', vt:'Sales-Tally', party:'Himalaya Stationary Mart', ch:'wholesale', qty:6 },
      { dt:'Feb 19', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Feb 16', vt:'Sales-Tally', party:'JIneshwar Tradelink', ch:'wholesale', qty:1 },
      { dt:'Feb 13', vt:'Credit Note', party:'United Paper And Stationers', ch:'excluded', qty:1, note:'return' },
      { dt:'Feb 05', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'Elefant Enterprise', ch:'wholesale', qty:1 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 03', vt:'Sales-Flipkart', party:'FLIPKART', ch:'online', qty:1 },
      { dt:'Feb 02', vt:'Sales-Tally', party:'MG Enterprises', ch:'wholesale', qty:3 },
      { dt:'Jan 19', vt:'Sales-Tally', party:'A N Commtrade LLP', ch:'wholesale', qty:3 },
      { dt:'Dec 25', vt:'Sales-Tally', party:'Bhaskar Arts Center', ch:'wholesale', qty:9 }
    ],
    txnCallout: '<strong>Notice the Credit Note on Feb 13:</strong> United Paper returned 1 tube. This adds stock back, but we do NOT count it as a sale. Returns don\'t represent customer demand.',
    channelExamples: {
      ws: 'Bhaskar Arts Center ordered 9 tubes on Dec 25. Himalaya Stationary Mart ordered 6 on Feb 26. Both count as active-day demand.',
      on: 'MAGENTO2 sold 1 tube on Feb 5. A Flipkart sale of 1 tube on Feb 3 also counts.',
      st: 'Counter Collection - QR sold 1 tube on Feb 19. That\'s it for the whole year &mdash; this product sells mostly wholesale.'
    },
    whyAddExample: 'When Himalaya Stationary orders 6 tubes wholesale AND someone buys 1 tube on artloungeindia.com on the same day, that\'s <strong>7 tubes gone</strong> from your stock. To predict when you\'ll run out, we need the <strong>combined</strong> drain rate:'
  },
  {
    id: 'manuscript-nib',
    name: 'Manuscript EF Principal Nib',
    short: 'Manuscript Nib',
    desc: 'Manuscript calligraphy nib, extra fine',
    brand: 'MANUSCRIPT',
    scenario: '56% wholesale, 31% online, 13% store',
    stock: 492, isd: 347, totalDays: 347, lastSale: 'Feb 27',
    wv: 1.1585, ov: 0.6340, sv: 0.2651,
    wsDemand: 402, onDemand: 220, stDemand: 92,
    wsTxns: 58, onTxns: 142, stTxns: 36,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 247, inStock: 130, critical: 38 },
    txns: [
      { dt:'Feb 27', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:4 },
      { dt:'Feb 26', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5 },
      { dt:'Feb 24', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 23', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5 },
      { dt:'Feb 21', vt:'Sales-Tally', party:"Syed's Calligraphy", ch:'wholesale', qty:24 },
      { dt:'Feb 20', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:3 },
      { dt:'Feb 19', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Feb 17', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 16', vt:'Sales-Tally', party:'Aakash osale', ch:'wholesale', qty:1 },
      { dt:'Feb 16', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 13', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5 },
      { dt:'Feb 11', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:3 }
    ],
    txnCallout: '<strong>Notice the mix:</strong> MAGENTO2 (online) appears 8 times in these 12 transactions, but Syed\'s Calligraphy ordered 24 nibs in one wholesale order. Wholesale has fewer transactions but bigger quantities. Online is steady drip of 1-5 per order.',
    channelExamples: {
      ws: 'Syed\'s Calligraphy ordered 24 nibs on Feb 21 in one go. Wholesale orders tend to be large but infrequent for this nib.',
      on: 'MAGENTO2 orders come daily &mdash; 1 to 5 nibs at a time. 142 online transactions this year, making up 31% of demand.',
      st: 'Counter Collection sold 92 nibs in-store this year across 36 transactions &mdash; the store channel is meaningful here (13% of demand).'
    },
    whyAddExample: 'When Syed\'s Calligraphy orders 24 nibs wholesale AND MAGENTO2 sells 5 online AND the store counter sells 1 &mdash; that\'s <strong>30 nibs gone</strong> in a day. All three channels eat from the same 492-nib pile:'
  },
  {
    id: 'pebeo-gutta',
    name: 'PEBEO WATERBASED GUTTA 20ML COLOURLESS',
    short: 'Pebeo Gutta',
    desc: 'Pebeo silk painting gutta outliner, 20ml',
    brand: 'PEBEO',
    scenario: 'OUT OF STOCK (-11 units)',
    stock: -11, isd: 191, totalDays: 347, lastSale: 'Feb 24',
    wv: 5.7068, ov: 0.1990, sv: 0.0837,
    wsDemand: 1090, onDemand: 38, stDemand: 16,
    wsTxns: 52, onTxns: 23, stTxns: 12,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 1403, inStock: 396, critical: 104 },
    txns: [
      { dt:'Feb 24', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Feb 19', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Jan 31', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:2 },
      { dt:'Jan 25', vt:'Sales Store', party:'New Bombay Stationery Stores', ch:'store', qty:1 },
      { dt:'Jan 23', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:2 },
      { dt:'Jan 19', vt:'Sales-Tally', party:'A N Commtrade LLP', ch:'wholesale', qty:1 },
      { dt:'Jan 14', vt:'Sales-Tally', party:'Bharti Prajapati', ch:'wholesale', qty:1 },
      { dt:'Jan 07', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Jan 07', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Jan 05', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Dec 29', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Dec 27', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Dec 25', vt:'Sales-Tally', party:'A N Commtrade LLP', ch:'wholesale', qty:2 },
      { dt:'Dec 19', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:2 }
    ],
    txnCallout: '<strong>This product is OUT OF STOCK (balance: -11).</strong> The negative balance means Tally recorded more outward than inward &mdash; likely a data mismatch from SKU renames or the company merger. But if a sale happened, the item was physically on the shelf. So days with real sales count as "active" even when the book balance is negative.',
    channelExamples: {
      ws: 'A N Commtrade ordered 2 on Dec 25 and 1 on Jan 19. Wholesale is massive: 1,090 units across 191 active days this year.',
      on: 'MAGENTO2 sells 1-2 at a time. 38 units online on active days.',
      st: 'Counter Collection sold 16 units in-store on active days.'
    },
    whyAddExample: 'Even though this product is out of stock now, the velocity tells us how fast it <em>was</em> selling when available. All three channels drained from the same pile, and at 5.99/day combined, stock evaporates fast:'
  },
  {
    id: 'marabu-black',
    name: 'Marabu Contours & Effects - 073 Black - 25 ML',
    short: 'Marabu Black',
    desc: 'Marabu contour paint, black, 25ml',
    brand: 'MARABU',
    scenario: '70% wholesale, 27% online, 3% store',
    stock: 71, isd: 130, totalDays: 347, lastSale: 'Feb 28',
    wv: 0.9077, ov: 0.3538, sv: 0.0385,
    wsDemand: 118, onDemand: 46, stDemand: 5,
    wsTxns: 12, onTxns: 24, stTxns: 4,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 268, inStock: 100, critical: 42 },
    txns: [
      { dt:'Feb 28', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 24', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Feb 05', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:2 },
      { dt:'Jan 31', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1 },
      { dt:'Jan 30', vt:'Sales-Tally', party:'Gp Capt Rohit Kataria', ch:'wholesale', qty:2 },
      { dt:'Jan 29', vt:'Sales-Tally', party:'Hindustan Trading Company', ch:'wholesale', qty:6 },
      { dt:'Jan 28', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:3 },
      { dt:'Jan 26', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:2 },
      { dt:'Jan 23', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Jan 21', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:2 },
      { dt:'Jan 19', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Jan 12', vt:'Sales Store', party:'Counter Collection - CC', ch:'store', qty:3 }
    ],
    txnCallout: '<strong>All three channels active:</strong> Hindustan Trading (wholesale, 6 units), MAGENTO2 (online, steady 1-3), and Counter Collection QR/CC (store, occasional). This is a well-balanced product with real demand across channels.',
    channelExamples: {
      ws: 'Hindustan Trading ordered 6 on Jan 29, Gp Capt Rohit Kataria 2 on Jan 30. Wholesale is 70% of demand.',
      on: 'MAGENTO2 sells 1-3 at a time almost weekly. 46 units online across 24 orders &mdash; 27% of total demand.',
      st: 'Counter Collection (QR and CC) sold 5 units in-store across 4 visits. Small but real &mdash; 3% of demand.'
    },
    whyAddExample: 'In late January, Hindustan Trading ordered 6 wholesale, MAGENTO2 sold 3 online, and the store sold 1 &mdash; that\'s <strong>10 units gone</strong> in a few days from the same stock of 71:'
  },
  {
    id: 'camlin-charcoal',
    name: 'CAMLIN CHARCOAL PENCIL - SOFT',
    short: 'Camlin Charcoal',
    desc: 'Camlin charcoal pencil, soft grade',
    brand: 'CAMLIN',
    scenario: '1% wholesale, 57% online, 42% store',
    stock: 69, isd: 347, totalDays: 347, lastSale: 'Feb 20',
    wv: 0.0029, ov: 0.1354, sv: 0.0980,
    wsDemand: 1, onDemand: 47, stDemand: 34,
    wsTxns: 1, onTxns: 8, stTxns: 4,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 1196, inStock: 399, critical: 15 },
    txns: [
      { dt:'Feb 21', vt:'Purchase', party:'New Bombay Stationery Stores', ch:'supplier', qty:10, note:'inward' },
      { dt:'Feb 20', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:10 },
      { dt:'Feb 17', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:3 },
      { dt:'Feb 09', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5 },
      { dt:'Feb 09', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5 },
      { dt:'Jan 31', vt:'Sales Store', party:'Counter Collection - Cash', ch:'store', qty:10 },
      { dt:'Dec 25', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:2 },
      { dt:'Dec 24', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:6 },
      { dt:'Nov 28', vt:'Purchase', party:'Shree Sai Enterprises', ch:'supplier', qty:10, note:'inward' },
      { dt:'Nov 28', vt:'Purchase', party:'Shree Sai Enterprises', ch:'supplier', qty:20, note:'inward' },
      { dt:'Nov 28', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1 },
      { dt:'Nov 28', vt:'Sales-Tally', party:'Aadil Naqvi', ch:'wholesale', qty:1 },
      { dt:'Nov 14', vt:'Sales Store', party:'Counter Collection - CC', ch:'store', qty:1 }
    ],
    txnCallout: '<strong>Edge case &mdash; Purchase from a "wholesale" party:</strong> New Bombay Stationery Stores is classified as wholesale (Sundry Debtors), but this is a <em>Purchase</em> voucher &mdash; stock coming IN, not out. The system correctly marks it as inward and excludes it from velocity. Also note: only 1 wholesale sale all year (Aadil Naqvi, Nov 28) &mdash; this product sells almost entirely online + store.',
    channelExamples: {
      ws: 'Just 1 wholesale transaction all year: Aadil Naqvi ordered 1 pencil on Nov 28. That\'s it. Wholesale velocity is essentially zero (0.003/day).',
      on: 'MAGENTO2 sold 47 pencils in 8 transactions. The big ones: 10 on Feb 20, two orders of 5 on Feb 9. Online is the dominant channel at 57%.',
      st: 'Counter Collection sold 34 pencils in-store: 10 in one cash sale on Jan 31, 3 on Feb 17, 1 on Nov 14. Store is 42% of demand &mdash; nearly as much as online.'
    },
    whyAddExample: 'In early February, MAGENTO2 sold 10 pencils online and Counter Collection sold 3 in-store &mdash; that\'s <strong>13 gone</strong> in a few days. Almost no wholesale demand, but online + store together drain the stock of 69:'
  },

  // ═══════════════════════════════════════════════════════
  // NEW EXAMPLES — added March 2026
  // ═══════════════════════════════════════════════════════
  {
    id: 'holbein-pastels',
    name: 'Holbein Artists\' Soft Pastels S969 - Set of 250 Colours',
    short: 'Holbein 250-Set',
    desc: 'Holbein premium soft pastel set, 250 colours',
    brand: 'HOLBEIN',
    scenario: 'Tiny import, Rs 35K/unit',
    stock: 1, isd: 134, totalDays: 347, lastSale: 'Oct 31',
    wv: 0.0, ov: 0.0075, sv: 0.0,
    wsDemand: 0, onDemand: 1, stDemand: 0,
    wsTxns: 0, onTxns: 1, stTxns: 0,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 89, inStock: 44, critical: 8 },
    txns: [
      { dt:'Oct 31', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 43005 },
      { dt:'Oct 31', vt:'Purchase', party:'Hindustan Trading Company - Purchse', ch:'supplier', qty:2, note:'inward', rate: 35349 }
    ],
    txnCallout: '<strong>Tiny import, massive value:</strong> Only 2 units imported at Rs 35,349 each (Rs 70,697 total). One sold online for Rs 43,005. This is the kind of product where each unit matters &mdash; you can\'t order 200 "just in case". Import decisions are per-unit.',
    channelExamples: {
      ws: 'Zero wholesale demand. A Rs 43,000 pastel set isn\'t a typical wholesale item.',
      on: 'MAGENTO2 sold exactly 1 set on Oct 31 for Rs 43,005. Online is the only channel.',
      st: 'No store sales. At this price point, customers probably research and buy online.'
    },
    whyAddExample: 'With only 1 unit left and selling exclusively online, any single order drains 100% of stock. The velocity is tiny (0.0075/day) but each unit is worth Rs 43,000:'
  },
  {
    id: 'edding-paintmarker',
    name: 'e-750 paintmarker white',
    short: 'Edding e-750',
    desc: 'Edding paint marker, white, permanent',
    brand: 'EDDING',
    scenario: 'Huge wholesale (Rs 194K single order)',
    stock: 249, isd: 191, totalDays: 347, lastSale: 'Jan 07',
    wv: 9.2513, ov: 0.0157, sv: 0.0105,
    wsDemand: 1767, onDemand: 3, stDemand: 2,
    wsTxns: 10, onTxns: 1, stTxns: 2,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 52, inStock: 28, critical: 10 },
    txns: [
      { dt:'Jan 07', vt:'Sales-Tally', party:'Varaha Enterprises', ch:'wholesale', qty:20, rate: 287 },
      { dt:'Dec 17', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:3, rate: 287 },
      { dt:'Dec 12', vt:'Sales-Tally', party:'JIneshwar Tradelink', ch:'wholesale', qty:200, rate: 144 },
      { dt:'Dec 12', vt:'Sales-Tally', party:'Divyanshi Aviation Services Pvt. Ltd.', ch:'wholesale', qty:200, rate: 287 },
      { dt:'Dec 12', vt:'Sales-Tally', party:'Advance Engineering', ch:'wholesale', qty:100, rate: 215 },
      { dt:'Dec 12', vt:'Purchase', party:'EDDING INTERNATIONAL', ch:'supplier', qty:2000, note:'inward', rate: 84 },
      { dt:'Dec 12', vt:'Sales-Tally', party:'Advance Engineering', ch:'wholesale', qty:900, rate: 215 },
      { dt:'Oct 31', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1, rate: 210 },
      { dt:'Oct 25', vt:'Sales Store', party:'J.B.PETIT HIGH SCHOOL FOR GIRLS', ch:'store', qty:1, rate: 234 },
      { dt:'Oct 15', vt:'Sales-Tally', party:'Advance Engineering', ch:'wholesale', qty:230, rate: 186 },
      { dt:'Oct 09', vt:'Sales-Tally', party:'Varaha Enterprises', ch:'wholesale', qty:40, rate: 247 },
      { dt:'Oct 03', vt:'Sales-Tally', party:'Divyanshi Aviation Services Pvt. Ltd.', ch:'wholesale', qty:50, rate: 247 },
      { dt:'Jul 03', vt:'Sales-Tally', party:'Varaha Enterprises', ch:'wholesale', qty:20, rate: 247 }
    ],
    txnCallout: '<strong>Industrial-scale wholesale:</strong> Advance Engineering ordered 900 units in a single transaction (Rs 193,919). That\'s 51% of all demand in one order. 2,000 units were imported from EDDING INTERNATIONAL at Rs 84 each &mdash; most already sold through wholesale channels.',
    channelExamples: {
      ws: 'Advance Engineering alone accounts for 1,230 units across 3 orders. Divyanshi Aviation took 250. These are industrial/corporate buyers ordering hundreds at a time.',
      on: 'MAGENTO2 sold exactly 3 markers online. Online is less than 1% of demand.',
      st: 'Counter Collection and a school (J.B.PETIT) bought 1 each in-store. Store demand is negligible.'
    },
    whyAddExample: 'When Advance Engineering orders 900 markers on one day, that\'s nearly half of all demand in a single transaction. The velocity is 9.28/day but it\'s extremely lumpy &mdash; a few huge wholesale orders rather than steady daily sales:'
  },
  {
    id: 'koh-graphite',
    name: 'Koh-i-noor TOISON DOR GRAPHITE PENCIL - 4B',
    short: 'Koh-i-noor 4B',
    desc: 'Koh-i-noor professional graphite pencil, 4B grade',
    brand: 'KOH-I-NOOR',
    scenario: 'Dead stock (49 days no sale)',
    stock: 176, isd: 239, totalDays: 347, lastSale: 'Jan 23',
    wv: 0.4017, ov: 0.0418, sv: 0.0251,
    wsDemand: 96, onDemand: 10, stDemand: 6,
    wsTxns: 2, onTxns: 6, stTxns: 5,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 1944, inStock: 443, critical: 25 },
    txns: [
      { dt:'Jan 23', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1, rate: 58 },
      { dt:'Jan 19', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 77 },
      { dt:'Dec 31', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 70 },
      { dt:'Dec 27', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 60 },
      { dt:'Dec 16', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 63 },
      { dt:'Dec 15', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1, rate: 77 },
      { dt:'Nov 13', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:1, rate: 65 },
      { dt:'Sep 30', vt:'Sales Store', party:'Counter Collection - QR', ch:'store', qty:2, rate: 69 },
      { dt:'Sep 30', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 70 },
      { dt:'Sep 13', vt:'Sales-Tally', party:'FLINOX ENTERPRISES LLP', ch:'wholesale', qty:24, rate: 41 },
      { dt:'Aug 19', vt:'Sales Store', party:'Counter Collection - CC', ch:'store', qty:1, rate: 65 },
      { dt:'Jul 26', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:5, rate: 63 },
      { dt:'Jul 25', vt:'Sales-Tally', party:'Hindustan Trading Company', ch:'wholesale', qty:72, rate: 38 },
      { dt:'Jul 18', vt:'Purchase', party:'Koh-i-Noor Hardmuth.A.S', ch:'supplier', qty:288, note:'inward', rate: 18 }
    ],
    txnCallout: '<strong>Dead stock alert:</strong> Last sale was Jan 23 &mdash; 49 days ago. Imported 288 pencils at Rs 18 each in July. Sold 112 across all channels, then demand dried up completely. The system shows 375 days of runway, but that velocity is from months ago.',
    channelExamples: {
      ws: 'Just 2 wholesale orders, but they were big: Hindustan Trading (72 pencils) and FLINOX (24). Wholesale is 86% of demand &mdash; when it happens.',
      on: 'MAGENTO2 sold 10 pencils across 6 transactions. Small but steady through year-end, then stopped in January.',
      st: 'Counter Collection sold 6 pencils in-store across 5 visits. The last sale of this product (Jan 23) was actually a store sale.'
    },
    whyAddExample: 'This product\'s velocity is based on 239 active days of history. But the last sale was 49 days ago &mdash; the <em>recent</em> velocity is effectively zero. All three channels have gone quiet:'
  },
  {
    id: 'nitram-charcoal',
    name: 'NITRAM Batons Epais - Extra Soft - B+ - Box of 5',
    short: 'NITRAM Batons',
    desc: 'NITRAM charcoal drawing sticks, extra soft, 8mm round',
    brand: 'NITRAM',
    scenario: 'Slow mover (1 sale in 347 days)',
    stock: 25, isd: 347, totalDays: 347, lastSale: 'Oct 10',
    wv: 0.0, ov: 0.0029, sv: 0.0,
    wsDemand: 0, onDemand: 1, stDemand: 0,
    wsTxns: 0, onTxns: 1, stTxns: 0,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 24, inStock: 16, critical: 0 },
    txns: [
      { dt:'Nov 18', vt:'Purchase', party:'Art Lounge India - Purchase', ch:'internal', qty:24, note:'internal transfer' },
      { dt:'Oct 10', vt:'Sales-Tally', party:'MAGENTO2', ch:'online', qty:1, rate: 735 },
      { dt:'Oct 03', vt:'Purchase', party:'Art Lounge India - Purchase', ch:'internal', qty:2, note:'internal transfer' }
    ],
    txnCallout: '<strong>The ultimate slow mover:</strong> Exactly 1 unit sold in 347 days (online for Rs 735). 25 units in stock would last <strong>23.6 years</strong> at this velocity. The 26 units came via internal transfers (Art Lounge India), not direct imports &mdash; they\'re niche charcoal sticks for professional artists.',
    channelExamples: {
      ws: 'Zero wholesale orders all year. This is too niche for wholesale dealers.',
      on: 'MAGENTO2 sold 1 box on Oct 10 for Rs 735. That\'s the only sale of any kind.',
      st: 'No store sales. This product hasn\'t sold from the counter even once.'
    },
    whyAddExample: 'With 25 units and 0.003 units/day velocity, this product essentially doesn\'t move. The question isn\'t "when to reorder" but "should we be stocking this at all?"'
  },
  {
    id: 'wn-varnish',
    name: 'WN MATT VARNISH SPR 400ML V1',
    short: 'WN Varnish Spray',
    desc: 'Winsor & Newton matt varnish spray, 400ml',
    brand: 'WINSOR & NEWTON',
    scenario: 'Critical: 1.3 days left, 100% wholesale',
    stock: 12, isd: 61, totalDays: 347, lastSale: 'Feb 06',
    wv: 9.5902, ov: 0.0, sv: 0.0,
    wsDemand: 585, onDemand: 0, stDemand: 0,
    wsTxns: 48, onTxns: 0, stTxns: 0,
    wsOOS: 0, onOOS: 0, stOOS: 0,
    brandInfo: { total: 2257, inStock: 1030, critical: 275 },
    txns: [
      { dt:'Feb 06', vt:'Sales-Tally', party:'MARKETING SUPPLIES - LOCAL', ch:'wholesale', qty:6, rate: 457 },
      { dt:'Feb 05', vt:'Sales-Tally', party:'Bhaskar Arts Center', ch:'wholesale', qty:12, rate: 884 },
      { dt:'Feb 05', vt:'Sales-Tally', party:'Anjali International', ch:'wholesale', qty:3, rate: 762 },
      { dt:'Feb 05', vt:'Sales-Tally', party:'Shankhesh Sales and Marketing', ch:'wholesale', qty:6, rate: 762 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'Arihant International', ch:'wholesale', qty:12, rate: 762 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'Janta Book Centre', ch:'wholesale', qty:6, rate: 991 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'Kumar Concern', ch:'wholesale', qty:6, rate: 915 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'Vardhman Trading Company', ch:'wholesale', qty:18, rate: 762 },
      { dt:'Feb 04', vt:'Sales-Tally', party:'SITA RAM ENTERPRISE', ch:'wholesale', qty:6, rate: 915 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'The Art City', ch:'wholesale', qty:6, rate: 915 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'Shankhesh Sales and Marketing', ch:'wholesale', qty:6, rate: 762 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'Harsh Enterprises', ch:'wholesale', qty:18, rate: 762 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'JIneshwar Tradelink', ch:'wholesale', qty:6, rate: 762 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'Artorium the Colour World', ch:'wholesale', qty:4, rate: 941 },
      { dt:'Feb 03', vt:'Sales-Tally', party:'Stationerie', ch:'wholesale', qty:12, rate: 915 }
    ],
    txnCallout: '<strong>Pure wholesale firehose:</strong> 48 wholesale transactions, zero online, zero store. 15 different dealers ordering 585 cans in just 61 active days. On Feb 3 alone, 6 different dealers ordered a combined 52 cans. This is the canonical "about to run out" item &mdash; 12 cans left at 9.59/day = 1.3 days.',
    channelExamples: {
      ws: 'Massive dealer base: Bhaskar Arts Center (12), Vardhman Trading (18), Harsh Enterprises (18), and 12 more. 585 units in 48 transactions = 12.2 units per order average.',
      on: 'Zero online sales. This is a wholesale-only product &mdash; dealers buy in bulk and distribute.',
      st: 'Zero store sales. Customers don\'t walk in and buy varnish spray from the counter.'
    },
    whyAddExample: 'With 100% wholesale demand and 12 cans left, a single dealer order of 12 cans (common for this product) would completely wipe out stock:'
  }
];
