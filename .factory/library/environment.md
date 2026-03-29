# Environment

## Required Environment

- **Python**: Use `py` command (not python3)
- **Node**: npm for frontend
- **PostgreSQL 17**: Binaries at `"C:\Program Files\PostgreSQL\17\bin\"`
- **Database**: `artlounge_reorder_uc` on localhost:5432
- **DB Credentials**: reorder_app / password
- **App Login**: admin / admin (admin role)

## Dev Server Setup

**Backend (FastAPI):**
```cmd
cd src
venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (Vite dev):**
```cmd
cd src\dashboard
npm run dev
```

- Vite serves at http://localhost:5173
- API calls go to http://localhost:8000 (configured in lib/api.ts)
- CORS configured to allow localhost:5173

## Key Env Vars

- `DATABASE_URL`: see CLAUDE.md for connection string (database: artlounge_reorder_uc on localhost:5432)
- `JWT_SECRET`: defaults to `dev-secret-change-in-production`
- `VITE_API_URL`: optional, defaults to `http://localhost:8000`

## Windows-Specific Notes

- PowerShell is the default shell
- Use `curl.exe` (not `curl`) to avoid PowerShell alias
- agent-browser `@ref` needs quoting in PowerShell (use semantic locators instead)
- Path separators: backslash in cmd/PowerShell, forward slash in git bash
