---
name: ux-tester-fixer
description: Tests a specific page/area via agent-browser, catalogs UX/UI issues, fixes them in React code, and verifies fixes.
---

# UX Tester-Fixer

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for features that require testing a specific page or set of pages in the Art Lounge dashboard for UX/UI issues, fixing those issues in the React/TypeScript/CSS code, and verifying the fixes.

## Required Skills

- **agent-browser**: MUST invoke for all browser-based testing and verification. Used to navigate pages, interact with elements, take screenshots, check console errors, and verify fixes at both desktop and mobile viewports.

## Work Procedure

### Phase 1: Environment Setup

1. Ensure services are running:
   - Check FastAPI backend on port 8000: `curl.exe -sf http://localhost:8000/api/health`
   - Check Vite dev server on port 5173: `curl.exe -sf http://localhost:5173`
   - If Vite is not running, start it: `cd src\dashboard && npm run dev` (background process)
   - Wait for both to be healthy before proceeding

2. Read the feature description carefully. Identify which page(s) to test and which validation contract assertions apply.

### Phase 2: Systematic Testing (Desktop)

3. Invoke `agent-browser` skill. Navigate to the target page at http://localhost:5173.
4. Log in if needed: username `admin`, password `admin`.
5. Set viewport to 1280x800 (desktop).
6. For EACH interactive element on the page, systematically test:
   - **Rendering**: Does it display correctly? Are labels, values, colors right?
   - **Interaction**: Click buttons, fill forms, toggle switches, expand rows, sort columns, apply filters
   - **Navigation**: Do links/buttons navigate to correct routes?
   - **States**: Loading skeleton, empty state, error state
   - **Console**: Check for JavaScript errors after each interaction
7. Take screenshots documenting each test. Name them descriptively.
8. Record EVERY issue found with: what you observed, expected behavior, severity (critical/major/minor).

### Phase 3: Mobile Testing

9. Set viewport to 375x667 (mobile).
10. Test the same page at mobile viewport:
    - Layout: No horizontal overflow, content fits viewport
    - Mobile-specific UI: BottomSheet, FilterDrawer, MobileListRow, tab bars
    - Touch targets: Buttons/links are tappable (sufficient size)
    - Navigation: Mobile nav (bottom tabs, hamburger) works
11. Take mobile screenshots and record issues.

### Phase 4: Fix Issues

12. For each issue found, locate the relevant React component in `src/dashboard/src/`.
13. Write the fix following existing patterns:
    - Use shadcn/ui components (Button, Badge, Card, etc.)
    - Use Tailwind CSS classes (match existing spacing, colors, responsive breakpoints)
    - Use React Query patterns for data fetching
    - Preserve existing component structure -- minimal, targeted changes
14. After each fix, verify via agent-browser that:
    - The issue is resolved
    - No new issues were introduced
    - Both desktop AND mobile viewports still work
15. Run `cd src\dashboard && npx tsc --noEmit` to verify no TypeScript errors.

### Phase 5: Verification

16. Do a final pass through ALL interactions on the page (desktop + mobile) to confirm everything works.
17. Check console for zero JavaScript errors across the full interaction sequence.
18. Run backend tests: `cd src && venv\Scripts\python -m pytest tests/ -x -q` to ensure no regressions.

### Phase 6: Commit

19. Stage and commit all changes: `fix: [page] resolve UX issues -- [brief list]`

## Example Handoff

```json
{
  "salientSummary": "Tested Brands page at desktop (1280x800) and mobile (375px). Found 4 issues: (1) sort arrow not toggling on re-click, (2) card view missing ABC badges, (3) mobile filter drawer not closing after apply, (4) console error on brand row hover prefetch. Fixed all 4 in BrandOverview.tsx and MobileLayout.tsx. Verified fixes. TypeScript clean, pytest passing (204 tests).",
  "whatWasImplemented": "Fixed brand table sort indicator toggle in BrandOverview.tsx. Added ABC badges to card view. Fixed mobile FilterDrawer onClose callback. Fixed null-check on prefetchQuery hover handler.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      { "command": "cd src/dashboard && npx tsc --noEmit", "exitCode": 0, "observation": "No TypeScript errors" },
      { "command": "cd src && venv/Scripts/python -m pytest tests/ -x -q", "exitCode": 0, "observation": "204 passed" }
    ],
    "interactiveChecks": [
      { "action": "Desktop: Clicked Health column header twice", "observed": "Sort toggled asc->desc correctly, arrow flipped" },
      { "action": "Desktop: Switched to card view", "observed": "ABC badges now visible on each brand card" },
      { "action": "Mobile 375px: Opened filter drawer, applied critical-only filter", "observed": "Drawer closed, table filtered" },
      { "action": "Desktop: Hovered over brand row", "observed": "No console error, prefetch visible" },
      { "action": "Mobile 375px: Full page scroll", "observed": "No horizontal overflow" },
      { "action": "Console check after all interactions", "observed": "Zero JavaScript errors" }
    ]
  },
  "tests": { "added": [] },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Backend API is returning errors that prevent testing (500s on required endpoints)
- Vite dev server won't start or crashes repeatedly
- A fix requires backend changes (not just frontend)
- The page requires data that doesn't exist in the database
- A fix would require changing shared components used by many pages (risk of regressions)
- Feature depends on another page's fixes being completed first
