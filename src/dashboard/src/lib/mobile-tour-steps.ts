import type { Step } from 'react-joyride'

export const MOBILE_TOUR_ROUTES: Record<string, string> = {
  home: '/',
  brands: '/brands',
}

export const MOBILE_STEP_ROUTE_MAP: { start: number; end: number; route: string }[] = [
  { start: 0, end: 5, route: MOBILE_TOUR_ROUTES.home },
  { start: 6, end: 8, route: MOBILE_TOUR_ROUTES.brands },
  { start: 9, end: 9, route: MOBILE_TOUR_ROUTES.home },
]

export const MOBILE_TOUR_STEPS: Step[] = [
  // Home (0-5)
  {
    target: 'body',
    placement: 'center',
    disableBeacon: true,
    content: 'Welcome to Stock Intelligence! This dashboard tracks 22,000+ SKUs across 167 brands and tells you what to reorder. Let\'s take a quick tour of the mobile interface.',
    title: 'Welcome!',
  },
  {
    target: '[data-tour-mobile="bottom-tabs"]',
    placement: 'top',
    content: 'Navigate between your daily workflow pages using these tabs: Home, Brands, Critical SKUs, and PO Builder.',
    title: 'Navigation',
  },
  {
    target: '[data-tour-mobile="hamburger"]',
    placement: 'bottom',
    content: 'Tap here for settings, supplier management, parties, overrides, and the help guide.',
    title: 'More Pages',
  },
  {
    target: '[data-tour="summary-cards"]',
    placement: 'bottom',
    content: 'Your daily snapshot. Critical SKUs need ordering now. Tap any card to see details.',
    title: 'Summary Cards',
  },
  {
    target: '[data-tour="brand-search"]',
    placement: 'bottom',
    content: 'Search for any brand or SKU by name or part number. Results appear as you type.',
    title: 'Search',
  },
  {
    target: '[data-tour="priority-table"]',
    placement: 'top',
    content: 'Brands sorted by urgency. Tap any brand to see its SKUs and reorder suggestions.',
    title: 'Priority Brands',
  },
  // Brands (6-8)
  {
    target: '[data-tour="brand-cards"]',
    placement: 'bottom',
    content: 'Each card shows a brand\'s health at a glance: critical count, warnings, and stock status.',
    title: 'Brand Cards',
  },
  {
    target: '[data-tour="brand-filters"]',
    placement: 'bottom',
    content: 'Filter and sort brands to focus on what needs attention. Use the filter button to narrow results.',
    title: 'Filters',
  },
  {
    target: '[data-tour="brand-cards"]',
    placement: 'top',
    content: 'Tap any brand card to see all its SKUs with status badges, stock levels, and velocity data.',
    title: 'Drill Into a Brand',
  },
  // Wrap-up (9)
  {
    target: '[data-tour="help-menu"]',
    placement: 'bottom',
    content: 'That\'s the basics! You can replay this tour anytime from the help menu. The Help Guide has detailed explanations of every concept.',
    title: 'You\'re All Set!',
  },
]
