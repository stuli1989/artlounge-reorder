import type { Step } from 'react-joyride'

export const TOUR_ROUTES: Record<string, string> = {
  home: '/',
  brands: '/brands',
  skuDetail: '/brands/WINSOR%20%26%20NEWTON/skus',
  poBuilder: '/brands/WINSOR%20%26%20NEWTON/po',
}

export const STEP_ROUTE_MAP: { start: number; end: number; route: string }[] = [
  { start: 0, end: 4, route: TOUR_ROUTES.home },
  { start: 5, end: 7, route: TOUR_ROUTES.brands },
  { start: 8, end: 13, route: TOUR_ROUTES.skuDetail },
  { start: 14, end: 16, route: TOUR_ROUTES.poBuilder },
  { start: 17, end: 17, route: TOUR_ROUTES.home },
]

export const TOUR_STEPS: Step[] = [
  // Home (0-4)
  {
    target: 'body',
    placement: 'center',
    disableBeacon: true,
    content: 'Welcome to Stock Intelligence! This dashboard tracks 22,000+ SKUs across 167 brands and tells you what to reorder and when. All data syncs nightly from Unicommerce. Let\'s take a quick tour.',
    title: 'Welcome to Stock Intelligence',
  },
  {
    target: '[data-tour="sync-indicator"]',
    content: 'This shows when data last synced. A green dot means data is fresh. Syncs run nightly so you always have yesterday\'s numbers.',
    title: 'Data Freshness',
  },
  {
    target: '[data-tour="summary-cards"]',
    content: 'Your daily snapshot. Critical SKUs need ordering now — the red number tells you how many. Click any card to drill in.',
    title: 'Summary Cards',
  },
  {
    target: '[data-tour="brand-search"]',
    content: 'Type any brand name to jump straight to its SKU list. Useful when you know exactly what you\'re looking for.',
    title: 'Brand Search',
  },
  {
    target: '[data-tour="priority-table"]',
    content: 'Brands sorted by urgency — most critical items at the top. Click any row to see that brand\'s individual SKUs.',
    title: 'Priority Brands',
  },
  // Brands (5-7)
  {
    target: '[data-tour="brand-cards"]',
    content: 'Each card summarizes a brand\'s health — how many critical SKUs, warnings, and dead stock items. Red and amber numbers need attention.',
    title: 'Brand Health Summary',
  },
  {
    target: '[data-tour="brand-filters"]',
    content: 'Filter to only brands with critical items, or sort by any column to focus your review.',
    title: 'Filters & Sorting',
  },
  {
    target: '[data-tour="brand-table"]',
    content: 'Click any brand row to see all its individual SKUs. Let\'s drill into one.',
    title: 'Drill Into a Brand',
  },
  // SKU Detail (8-13)
  {
    target: '[data-tour="sku-table"]',
    content: 'Every SKU for this brand. Status badges tell you at a glance what needs attention — red means act now, amber means plan ahead.',
    title: 'SKU Table',
  },
  {
    target: '[data-tour="sku-columns"]',
    content: 'Each column tells part of the story. Status shows urgency, Stock shows what you have, Velocity shows how fast it sells across all channels, and ABC shows revenue importance.',
    title: 'Understanding the Columns',
  },
  {
    target: '[data-tour="sku-expand-hint"]',
    content: 'Click any SKU row to expand it. You\'ll see the full story — stock history chart, sales breakdown by channel, and exactly how the reorder suggestion was calculated.',
    title: 'Expand for Details',
  },
  {
    target: '[data-tour="stock-timeline"]',
    content: 'This chart shows daily stock levels over time. You can see when stock ran out and when it was replenished. Drag across the chart to zoom into a date range.',
    title: 'Stock Timeline',
  },
  {
    target: '[data-tour="calculation-tab"]',
    content: 'This tab breaks down exactly how the reorder number was calculated — velocity from each channel, lead time, safety buffer. Every number is explained and traceable.',
    title: 'Calculation Breakdown',
  },
  {
    target: '[data-tour="override-buttons"]',
    content: 'If the system\'s estimate doesn\'t match reality — maybe you know a big wholesale order is coming, or a product is seasonal — click Adjust to set your own value. You\'ll need to provide a reason.',
    title: 'Overrides',
  },
  // PO Builder (14-16)
  {
    target: '[data-tour="po-table"]',
    content: 'The purchase order builder shows suggested quantities for every SKU that needs reordering. Toggle items in or out, adjust quantities, and add notes for your supplier.',
    title: 'Purchase Order Builder',
  },
  {
    target: '[data-tour="po-config"]',
    content: 'Configure lead time type and buffer settings for this order. These affect the suggested quantities.',
    title: 'PO Configuration',
  },
  {
    target: '[data-tour="po-export"]',
    content: 'Export to Excel — ready to send to your supplier. The export includes all quantities, part numbers, and notes.',
    title: 'Export to Excel',
  },
  // Wrap-up (17)
  {
    target: '[data-tour="help-menu"]',
    placement: 'bottom',
    content: 'That\'s the core workflow! You can replay this tour anytime from here. The Help Guide has detailed explanations of every concept, page-by-page guides, and daily workflow checklists.',
    title: 'You\'re All Set!',
  },
]
