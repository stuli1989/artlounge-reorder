import { Link, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSyncStatus, fetchOverrides } from '@/lib/api'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Package, Users, Truck, AlertTriangle, Pencil } from 'lucide-react'

const freshnessColors = {
  fresh: 'bg-green-500',
  stale: 'bg-amber-500',
  critical: 'bg-red-500',
}

export default function Layout() {
  const location = useLocation()
  const { data: sync } = useQuery({
    queryKey: ['syncStatus'],
    queryFn: fetchSyncStatus,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })

  const { data: staleOverrides } = useQuery({
    queryKey: ['overrides', 'stale'],
    queryFn: () => fetchOverrides({ is_stale: true }),
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })

  const staleCount = staleOverrides?.length ?? 0

  const navItems = [
    { path: '/', label: 'Brands', icon: Package },
    { path: '/parties', label: 'Parties', icon: Users },
    { path: '/suppliers', label: 'Suppliers', icon: Truck },
    { path: '/overrides', label: 'Overrides', icon: Pencil },
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-semibold">Art Lounge — Stock Intelligence</h1>
            <nav className="flex gap-1">
              {navItems.map(({ path, label, icon: Icon }) => {
                const isActive = path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(path)
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`px-3 py-1.5 rounded-md text-sm flex items-center gap-1.5 transition-colors ${
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Sync Status */}
          {sync && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className={`h-2 w-2 rounded-full ${freshnessColors[sync.freshness]}`} />
              {sync.last_sync_completed
                ? `Synced ${new Date(sync.last_sync_completed).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                : 'Never synced'}
            </div>
          )}
        </div>
      </header>

      {/* Warning Banner */}
      {sync && sync.unclassified_parties_count > 0 && (
        <div className="max-w-7xl mx-auto px-4 pt-3">
          <Alert className="bg-amber-50 border-amber-200">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              {sync.unclassified_parties_count} new parties need classification. Velocity calculations may be incomplete.{' '}
              <Link to="/parties" className="underline font-medium">Classify now</Link>
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* Stale Overrides Banner */}
      {staleCount > 0 && (
        <div className="max-w-7xl mx-auto px-4 pt-3">
          <Alert className="bg-amber-50 border-amber-200">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              {staleCount} override{staleCount !== 1 ? 's' : ''} need{staleCount === 1 ? 's' : ''} review — Tally data has changed since they were set.{' '}
              <Link to="/overrides" className="underline font-medium">Review now</Link>
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
