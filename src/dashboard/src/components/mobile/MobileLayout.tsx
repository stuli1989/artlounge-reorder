import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import type { SyncStatus, Override } from '@/lib/types'
import {
  LayoutDashboard,
  Package,
  ShieldAlert,
  ClipboardList,
  Users,
  Truck,
  Pencil,
  Settings,
  BookOpen,
  Skull,
  Menu,
  X,
  LogOut,
  UserCog,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import GuidedTour, { resetTour } from '@/components/GuidedTour'
import HelpMenu from '@/components/HelpMenu'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const freshnessColors: Record<string, string> = {
  fresh: 'bg-green-500',
  stale: 'bg-amber-500',
  critical: 'bg-red-500',
}

const PAGE_TITLES: Record<string, string> = {
  '/': 'Home',
  '/brands': 'Brands',
  '/critical': 'Critical',
  '/po': 'Build PO',
  '/parties': 'Parties',
  '/suppliers': 'Suppliers',
  '/overrides': 'Overrides',
  '/settings': 'Settings',
  '/users': 'Users',
  '/help': 'Help Guide',
}

function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname]
  if (pathname.startsWith('/brands/') && pathname.endsWith('/skus')) return 'SKU Detail'
  if (pathname.startsWith('/brands/') && pathname.endsWith('/po')) return 'Build PO'
  if (pathname.startsWith('/brands/') && pathname.endsWith('/dead-stock')) return 'Dead Stock'
  if (pathname.startsWith('/brands/')) return 'Brand'
  return 'Art Lounge'
}

const BOTTOM_TABS = [
  { path: '/', label: 'Home', icon: LayoutDashboard, exact: true },
  { path: '/brands', label: 'Brands', icon: Package, exact: true },
  { path: '/critical', label: 'Critical', icon: ShieldAlert, exact: false },
  { path: '/po', label: 'PO', icon: ClipboardList, exact: false },
]

// Drawer groups are now built dynamically inside the component (role-aware)

interface MobileLayoutProps {
  tourRunning: boolean
  setTourRunning: (running: boolean) => void
  sync?: SyncStatus
  staleOverrides?: Override[]
}

export default function MobileLayout({ tourRunning, setTourRunning, sync, staleOverrides }: MobileLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [warningDismissed, setWarningDismissed] = useState(false)

  const handleReplayTour = () => {
    resetTour()
    navigate('/')
    setTimeout(() => setTourRunning(true), 300)
  }

  const staleCount = staleOverrides?.length ?? 0
  const unclassifiedCount = sync?.unclassified_parties_count ?? 0
  const showWarning = !warningDismissed && (unclassifiedCount > 0 || staleCount > 0)

  const pageTitle = getPageTitle(location.pathname)

  const bottomTabs = BOTTOM_TABS.filter(t => !(t.path === '/po' && user?.role === 'viewer'))

  const drawerGroups = [
    ...(user?.role !== 'viewer' ? [{
      title: 'Data Management',
      items: [
        { path: '/parties', label: 'Parties', icon: Users },
        { path: '/suppliers', label: 'Suppliers', icon: Truck },
        { path: '/overrides', label: 'Overrides', icon: Pencil },
        { path: '/brands?filter=dead-stock', label: 'Dead Stock', icon: Skull },
      ],
    }] : []),
    {
      title: 'System',
      items: [
        ...(user?.role === 'admin' ? [
          { path: '/settings', label: 'Settings', icon: Settings },
          { path: '/users', label: 'Users', icon: UserCog },
        ] : []),
        { path: '/help', label: 'Help Guide', icon: BookOpen },
      ],
    },
  ]

  return (
    <div className="h-dvh bg-background flex flex-col overflow-hidden">
      {/* Compact Header */}
      <header className="border-b bg-card px-3 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDrawerOpen(true)}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
            aria-label="Open menu"
            data-tour-mobile="hamburger"
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="text-base font-semibold truncate">{pageTitle}</h1>
        </div>
        <div className="flex items-center gap-2">
          {sync && (
            <span
              className={cn('h-2 w-2 rounded-full shrink-0', freshnessColors[sync.freshness])}
              title={
                sync.last_sync_completed
                  ? `Synced ${new Date(sync.last_sync_completed).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                  : 'Never synced'
              }
            />
          )}
          <div data-tour="help-menu">
            <HelpMenu onReplayTour={handleReplayTour} />
          </div>
        </div>
      </header>

      {/* Warning Notification Bar */}
      {showWarning && (
        <div className="bg-amber-900/80 text-amber-200 px-3 py-2 text-xs flex items-center justify-between shrink-0">
          <div className="flex-1 min-w-0">
            {unclassifiedCount > 0 && (
              <span>{unclassifiedCount} unclassified parties</span>
            )}
            {unclassifiedCount > 0 && staleCount > 0 && <span> &middot; </span>}
            {staleCount > 0 && (
              <span>{staleCount} stale override{staleCount !== 1 ? 's' : ''}</span>
            )}
            {' '}
            <Link
              to={unclassifiedCount > 0 ? '/parties' : '/overrides'}
              className="underline font-medium"
            >
              Review &rarr;
            </Link>
          </div>
          <button
            onClick={() => setWarningDismissed(true)}
            className="p-0.5 ml-2 shrink-0"
            aria-label="Dismiss warning"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

      {/* Bottom Tab Bar */}
      <nav className="border-t bg-card shrink-0 pb-[env(safe-area-inset-bottom)]" data-tour-mobile="bottom-tabs">
        <div className="flex items-center justify-around">
          {bottomTabs.map(({ path, label, icon: Icon, exact }) => {
            const isActive = exact
              ? location.pathname === path
              : location.pathname.startsWith(path)
            return (
              <Link
                key={path}
                to={path}
                className={cn(
                  'flex flex-col items-center gap-0.5 py-2 px-3 text-[10px] transition-colors min-w-0',
                  isActive
                    ? 'text-primary'
                    : 'text-muted-foreground'
                )}
              >
                <Icon className="h-5 w-5" />
                <span className="truncate">{label}</span>
              </Link>
            )
          })}
        </div>
      </nav>

      {/* Hamburger Drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="px-4 pt-4 pb-2 border-b">
            <SheetTitle className="text-sm">Art Lounge</SheetTitle>
          </SheetHeader>
          <div className="py-2">
            {drawerGroups.map((group) => (
              <div key={group.title} className="mb-2">
                <div className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {group.title}
                </div>
                {group.items.map(({ path, label, icon: Icon }) => {
                  const isActive = location.pathname === path ||
                    (location.pathname + location.search) === path
                  return (
                    <Link
                      key={path}
                      to={path}
                      onClick={() => setDrawerOpen(false)}
                      className={cn(
                        'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  )
                })}
              </div>
            ))}
          </div>
          {/* User section */}
          <div className="absolute bottom-0 left-0 right-0 border-t bg-card px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{user?.username}</p>
                <p className="text-[10px] text-muted-foreground capitalize">{user?.role}</p>
              </div>
              <button
                onClick={() => { logout(); setDrawerOpen(false) }}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-muted transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <GuidedTour run={tourRunning} onFinish={() => setTourRunning(false)} />
    </div>
  )
}
