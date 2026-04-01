# PO Config Bar Redesign

**Date:** 2026-04-01
**Status:** Approved
**Mockup:** `.superpowers/brainstorm/14343-1775057342/content/config-bar-compact.html`

## Problem

The PO builder config bar has unclear labels that don't explain what values mean:
- "default" for lead time doesn't say what it resolves to
- "supplier_default" for order mode is developer jargon
- "Per-SKU (ABC-based)" for buffer is opaque
- Coverage period uses raw days (182) as the primary unit when users think in months
- Two separate toggles for Warning/OK items are harder to scan than a single control

## Design

Two-row grouped layout with visual hierarchy. Primary controls (frequently used) on top row, secondary controls (rarely changed) on bottom row.

### Row 1 — Primary Controls

**Lead Time** (dropdown, left):
- Options: "Supplier Default (Xd)", "Sea Freight (180 days)", "Air Freight (30 days)", "Custom"
- "Supplier Default" resolves and shows the actual days from the supplier record (e.g., "180d"). The resolved value comes from the `leadTime` computed variable (which already falls back through supplier_lead_time -> 180).
- When "Custom" is selected, show an inline number input for days
- When lead time type is "default", the `leadTime` value equals `customLeadTime` — so we need to initialize `customLeadTime` from the API response (first item's `lead_time` field) to show the correct resolved days

**Order Enough For** (number input, center-left):
- Renamed from "Coverage Period"
- Input is in **months** (not days) — e.g., user types "6"
- Days shown in parentheses as secondary info: "(182d)"
- Input uses string state internally so clearing the field to retype doesn't error out
- On blur with empty value: reset to auto-calculated default
- "Reset to auto" link shown only when value differs from auto-calculated

**Show** (segmented button, right-aligned):
- Three segments: "Critical" | "+ Warning" | "All"
- Replaces two separate Switch toggles (Warning items, OK items)
- Mapping:
  - "Critical" = includeWarning: false, includeOk: false
  - "+ Warning" = includeWarning: true, includeOk: false
  - "All" = includeWarning: true, includeOk: true

### Row 2 — Secondary Controls + Actions

Compact inline row separated from row 1 by a thin border.

**Order Mode** (inline dropdown):
- Label: "Order Mode:"
- Display: resolved value with explanation — e.g., "Full Order (lead + coverage)"
- Options:
  - "Supplier Setting" (uses supplier's `lead_time_demand_mode`, label shows resolved value)
  - "Full Order (lead + coverage)"
  - "Coverage Only"
- Small dropdown chevron inline

**Buffer** (inline with override button):
- Label: "Buffer:"
- Default display: "Auto per SKU"
- "Override" button opens slider (existing behavior, range 0.1-3.0x)
- When overridden: shows "1.3x override" with "Reset" link

**Actions** (right-aligned):
- "Import SKUs" button (outline)
- "Export Excel" button (primary/dark)

### Sizing

- All inputs/selects/segments: 32px height
- Override button: 24px height
- Card padding: 14px vertical, 20px horizontal
- Row 1 bottom padding: 10px with 1px border
- Row 2 top padding: 8px
- Gap between row 1 controls: 28px
- Font sizes: 13px primary controls, 12px secondary row, 11px labels/hints

### Coverage Period Input Behavior (Bug Fix)

Current behavior: `coverageDays` state is `number | null`. Clearing the input can produce `NaN` or `0`.

New behavior:
- Use a local string state (`coverageInput`) for the text field
- Parse to number only on blur or Enter
- Empty string while typing is valid (no error, no API call)
- On blur with empty/invalid value: reset display to auto-calculated default, set `coverageDays` back to `null`
- Convert between months (display) and days (API) — multiply by 30 on submit, divide by 30 for display

### Mobile

The mobile config (collapsible card) gets the same label improvements:
- "default" -> "Supplier Default (Xd)"
- Coverage input in months
- Order mode labels clarified
- Segmented button replaces two toggles (stacked vertically if needed)

## Files to Change

- `src/dashboard/src/pages/PoBuilder.tsx` — main implementation (both desktop and mobile sections)

## Out of Scope

- No changes to the API or backend
- No changes to the table, timeline, or other page sections
- No new components needed (segmented button built from existing shadcn primitives)
