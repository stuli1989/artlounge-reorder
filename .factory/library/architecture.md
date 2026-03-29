# Architecture

## System Overview

Art Lounge Stock Intelligence is a full-stack inventory reordering dashboard:

- **Backend**: FastAPI (Python) serving REST API + SPA static files
- **Frontend**: React 19 + TypeScript SPA built with Vite, using shadcn/ui + TailwindCSS 4
- **Database**: PostgreSQL 17 with raw SQL (psycopg2, no ORM)
- **State Management**: TanStack React Query for server state, React context for auth
- **Charting**: Recharts for stock timeline visualization

## Key Directories

```
src/
├── api/           # FastAPI app + route modules
│   ├── main.py    # App entry, CORS, middleware, SPA serving
│   ├── auth.py    # JWT + Argon2 auth
│   └── routes/    # 12 route modules (brands, skus, po, settings, etc.)
├── dashboard/     # React SPA
│   ├── src/
│   │   ├── App.tsx       # Route definitions (lazy-loaded pages)
│   │   ├── pages/        # 12+ page components
│   │   ├── components/   # Shared components + mobile/ subdirectory
│   │   ├── lib/          # api.ts, types.ts, utils
│   │   ├── contexts/     # AuthContext
│   │   └── hooks/        # useIsMobile
│   └── dist/             # Production build (served by FastAPI)
├── engine/        # Computation pipeline (velocity, reorder, classification)
├── config/        # App settings (env vars, supplier config)
└── db/            # Schema + migrations
```

## Frontend Architecture

- **Routing**: React Router DOM 7 with lazy-loaded pages wrapped in SuspenseWrapper
- **Auth**: JWT stored in localStorage, interceptors on axios for auto-attach and 401 redirect
- **Responsive**: `useIsMobile()` hook (768px breakpoint) drives desktop vs mobile layouts
- **Mobile**: Separate MobileLayout with bottom tab bar + hamburger drawer. Pages render different components based on `isMobile`
- **API Client**: Centralized axios instance in `lib/api.ts` with baseURL defaulting to `http://localhost:8000`

## Data Flow

1. Nightly sync pulls from Unicommerce → PostgreSQL
2. Engine pipeline computes velocity, classification, reorder status
3. FastAPI serves computed metrics via REST endpoints
4. React dashboard fetches via React Query with aggressive caching + prefetch

## Auth Model

- Roles: admin, purchaser, viewer
- Admin: full access (settings, users, CRUD)
- Purchaser: read + write (overrides, PO, classification)
- Viewer: read-only
- ProtectedRoute component gates all routes except /login and /docs/*
