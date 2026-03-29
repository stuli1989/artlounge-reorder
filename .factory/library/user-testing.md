# User Testing

## Validation Surface

- **Surface**: Browser UI (React SPA)
- **URL**: http://localhost:5173 (Vite dev server for development, http://localhost:8000 for production build)
- **Tool**: `agent-browser`
- **Auth**: Login as admin/admin at `/login`
- **Viewports**: Desktop (1280x800), Mobile (375x667)

## Testing Prerequisites

1. PostgreSQL running on port 5432 with `artlounge_reorder_uc` database
2. FastAPI backend running on port 8000 (`cd src && venv\Scripts\python -m uvicorn api.main:app --port 8000 --reload`)
3. Vite dev server running on port 5173 (`cd src\dashboard && npm run dev`)
4. Login with admin/admin credentials

## Validation Concurrency

**Machine specs:** 32GB RAM, 16 logical CPUs, ~6GB available
**Headroom budget:** 6GB * 0.7 = 4.2GB

**agent-browser surface:**
- Vite dev server: ~200MB
- Each agent-browser instance: ~300MB
- Budget after Vite: 4.0GB / 300MB = ~13 instances theoretical
- **Max concurrent validators: 3** (conservative for Windows with PowerShell overhead and existing processes)

## Known Environment Quirks

- PowerShell `@ref` syntax conflicts with agent-browser element references — use quoted `"@ref"` or semantic locators (labels, roles, text) instead
- `curl` in PowerShell is an alias for `Invoke-WebRequest` — use `curl.exe` for real curl
- Some API calls may return 500 on dashboard load (known pre-existing issue)
- The Vite dev server has no proxy — frontend makes direct CORS calls to port 8000
- `window.confirm()` used for delete confirmations (browser native dialog)
