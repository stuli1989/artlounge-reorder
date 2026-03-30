# Channel Rules Page — Design Spec

## Problem

The `/parties` page shows an empty Tally-era parties table. With Unicommerce, channel classification uses rule-based `channel_rules` (entity type, sale order prefix, defaults). The page needs a complete rewrite to manage these rules.

## Design

### Page Content

**Title:** "Channel Rules"
**Subtitle:** "Rules that classify transactions into channels. Higher priority rules are evaluated first."

**Rules table** showing all active rules sorted by priority DESC:
- Columns: Priority, Type (badge), Match Value, Facility (or "All"), Channel (colored badge), Actions (Edit/Delete)
- Admin sees Edit/Delete buttons. Non-admins see read-only view.

**Add Rule button** (admin only): opens dialog with fields:
- Rule Type: dropdown (entity / sale_order_prefix / default)
- Match Value: text input (validated non-empty)
- Facility Filter: text input (optional, for facility-specific rules)
- Channel: dropdown (supplier / wholesale / online / store / internal / ignore)
- Priority: number input

**Edit:** dialog with same fields, pre-populated.

**Delete:** confirmation, then soft-delete (is_active=false). Shows toast on success.

**Info callout** at top: "Rules are evaluated top-to-bottom by priority. Entity rules match transaction type (GRN, PICKLIST, etc.). Sale order prefix rules match the start of the order number (MA- for online, SO for wholesale). Default rules are the fallback when nothing else matches."

### API (already exists, no backend changes)

- `GET /api/channel-rules` — list active rules
- `POST /api/channel-rules` — create rule (admin)
- `PUT /api/channel-rules/{id}` — update rule (admin)
- `DELETE /api/channel-rules/{id}` — soft-delete (admin)

All mutations trigger background pipeline recompute automatically.

### Files

| Action | File |
|--------|------|
| Rewrite | `src/dashboard/src/pages/PartyClassification.tsx` — complete replacement with channel rules CRUD |
| Modify | `src/dashboard/src/lib/api.ts` — add channel rules API functions, remove old parties functions |

### What gets removed

- `fetchUnclassifiedParties`, `fetchAllParties`, `classifyParty` functions in api.ts
- All parties-based UI in PartyClassification.tsx
