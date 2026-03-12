# T21: Deployment Prep

## Prerequisites
- T14 (FastAPI app exists)
- T20 (Frontend pages exist)

## Objective
Prepare the project for Railway deployment. Auth is deferred to a future version — the dashboard will be publicly accessible for now.

## Files to Create/Modify

### 1. `Procfile` (verify/update)
```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

### 2. `runtime.txt` (if Railway needs it)
```
python-3.11.x
```

### 3. Ensure `requirements.txt` is complete
Verify all dependencies are listed:
```
requests
lxml
psycopg2-binary
fastapi
uvicorn[standard]
openpyxl
pandas
python-dotenv
```

### 4. `api/routes/health.py`
Health check endpoint for Railway:
```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}
```

Register in `api/main.py`:
```python
from api.routes import health
app.include_router(health.router, prefix="/api")
```

### 5. Update `dashboard/vite.config.ts`

Ensure build output goes to `dashboard/dist/`:
```typescript
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
})
```

### 6. Production build script

Add to project root as `scripts/build.sh`:
```bash
#!/bin/bash
cd dashboard
npm install
npm run build
cd ..
echo "Build complete. Static files in dashboard/dist/"
```

## Railway Deployment Checklist (Manual Steps)
1. Create Railway project
2. Add Postgres service → copy DATABASE_URL
3. Connect GitHub repo or deploy via CLI
4. Set environment variables:
   - `DATABASE_URL` — from Railway Postgres
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL` — for sync failure emails
5. Run `db/schema.sql` against Railway Postgres
6. Verify app starts and dashboard loads at public URL

## Sync Agent Setup (AWS Box — Manual)
1. Copy extraction/, engine/, sync/, config/ to AWS box
2. Set `DATABASE_URL` in .env to Railway Postgres URL
3. Set SMTP env vars in .env for email notifications
4. Run `python sync/nightly_sync.py --full` manually
5. Set up Windows Task Scheduler for nightly 2 AM

## Future: Auth (not in V1)
Auth will be added later as a separate task. For now the dashboard is publicly accessible — the data is internal stock/velocity info with no sensitive customer data.

## Acceptance Criteria
- [ ] /api/health returns 200 (for Railway health checks)
- [ ] Static file paths work (/api/* → FastAPI, /* → React build)
- [ ] Procfile uses $PORT for Railway
- [ ] requirements.txt complete
- [ ] `npm run build` produces dashboard/dist/
- [ ] Dashboard accessible without login
