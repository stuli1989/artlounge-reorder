import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSyncStatus, fetchOverrides } from '@/lib/api'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LayoutDashboard, Package, Users, Truck, AlertTriangle, Pencil, ShieldAlert, ClipboardList, Settings, LogOut, UserCog } from 'lucide-react'
import HelpMenu from '@/components/HelpMenu'
import { useAuth } from '@/contexts/AuthContext'
import GuidedTour, { isTourCompleted, resetTour } from '@/components/GuidedTour'
import HelpTip from '@/components/HelpTip'
import { useIsMobile } from '@/hooks/useIsMobile'
import MobileLayout from '@/components/mobile/MobileLayout'

const freshnessColors = {
  fresh: 'bg-green-500',
  stale: 'bg-amber-500',
  critical: 'bg-red-500',
}

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const { user, logout } = useAuth()
  const [tourRunning, setTourRunning] = useState(() => !isTourCompleted())

  const handleReplayTour = () => {
    resetTour()
    navigate('/')
    setTimeout(() => setTourRunning(true), 300)
  }

  // Keep all hooks above any early returns to satisfy Rules of Hooks.
  // MobileLayout manages its own queries internally.
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

  if (isMobile) {
    return (
      <MobileLayout
        tourRunning={tourRunning}
        setTourRunning={setTourRunning}
        sync={sync}
        staleOverrides={staleOverrides}
      />
    )
  }

  const navGroups = [
    [
      { path: '/', label: 'Home', icon: LayoutDashboard, exact: true },
      { path: '/brands', label: 'Brands', icon: Package, exact: true },
      { path: '/critical', label: 'Critical', icon: ShieldAlert },
      ...(user?.role !== 'viewer' ? [{ path: '/po', label: 'Build PO', icon: ClipboardList }] : []),
    ],
    ...(user?.role !== 'viewer' ? [[
      { path: '/parties', label: 'Parties', icon: Users },
      { path: '/suppliers', label: 'Suppliers', icon: Truck },
      { path: '/overrides', label: 'Overrides', icon: Pencil },
    ]] : []),
    ...(user?.role === 'admin' ? [[
      { path: '/settings', label: 'Settings', icon: Settings },
      { path: '/users', label: 'Users', icon: UserCog },
    ]] : []),
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-lg font-semibold">Art Lounge — Stock Intelligence</h1>
            <nav className="flex items-center gap-1">
              {navGroups.map((group, gi) => (
                <div key={gi} className="flex items-center gap-1">
                  {gi > 0 && (
                    <div className="h-5 w-px bg-slate-300 mx-1" />
                  )}
                  {group.map(({ path, label, icon: Icon, exact }) => {
                    const isActive = exact
                      ? location.pathname === path
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
                </div>
              ))}
            </nav>
          </div>

          {/* Sync Status */}
          <div className="flex items-center gap-3">
          {sync && (
            <div data-tour="sync-indicator" className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className={`h-2 w-2 rounded-full ${freshnessColors[sync.freshness]}`} />
              {sync.last_sync_completed
                ? `Synced ${new Date(sync.last_sync_completed).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                : 'Never synced'}
              <HelpTip tip="Last successful data sync from Tally. Runs nightly." helpAnchor="getting-started" />
            </div>
          )}
          <div data-tour="help-menu">
            <HelpMenu onReplayTour={handleReplayTour} />
          </div>
          {user && (
            <div className="flex items-center gap-2 text-sm border-l pl-3 ml-1">
              <span className="font-medium">{user.username}</span>
              <span className="text-xs text-muted-foreground capitalize">({user.role})</span>
              <button
                onClick={logout}
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
          </div>
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

      <GuidedTour run={tourRunning} onFinish={() => setTourRunning(false)} />
    </div>
  )
}
