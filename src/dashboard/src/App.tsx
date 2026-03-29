import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { AuthProvider } from '@/contexts/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRowSkeleton } from '@/components/mobile/MobileListRow'

const Login = lazy(() => import('./pages/Login'))
const Users = lazy(() => import('./pages/Users'))
const Home = lazy(() => import('./pages/Home'))
const BrandOverview = lazy(() => import('./pages/BrandOverview'))
const SkuDetail = lazy(() => import('./pages/SkuDetail'))
const PoBuilder = lazy(() => import('./pages/PoBuilder'))
const PartyClassification = lazy(() => import('./pages/PartyClassification'))
const SupplierManagement = lazy(() => import('./pages/SupplierManagement'))
const OverrideReview = lazy(() => import('./pages/OverrideReview'))
const DeadStock = lazy(() => import('./pages/DeadStock'))
const CriticalSkus = lazy(() => import('./pages/CriticalSkus'))
const Settings = lazy(() => import('./pages/Settings'))

const DocsLayout = lazy(() => import('./pages/docs/components/DocsLayout'))
const DocsOverview = lazy(() => import('./pages/docs/Overview'))
const DocsDataSources = lazy(() => import('./pages/docs/DataSources'))
const DocsCalculations = lazy(() => import('./pages/docs/Calculations'))
const DocsStatuses = lazy(() => import('./pages/docs/Statuses'))
const DocsWalkthroughs = lazy(() => import('./pages/docs/Walkthroughs'))
const DocsDashboardGuide = lazy(() => import('./pages/docs/DashboardGuide'))
const DocsWorkflows = lazy(() => import('./pages/docs/Workflows'))
const DocsArchitecture = lazy(() => import('./pages/docs/Architecture'))
const DocsGlossary = lazy(() => import('./pages/docs/Glossary'))

function LoadingSkeleton() {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <div className="space-y-2 p-4">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        {Array.from({ length: 5 }).map((_, i) => (
          <MobileListRowSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4 p-6">
      <div className="h-8 w-48 bg-muted animate-pulse rounded" />
      <div className="grid grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
      <div className="h-10 w-full bg-muted animate-pulse rounded" />
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 w-full bg-muted animate-pulse rounded" />
        ))}
      </div>
    </div>
  )
}

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingSkeleton />}>{children}</Suspense>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<SuspenseWrapper><Login /></SuspenseWrapper>} />

          {/* Docs — public, no auth */}
          <Route path="/docs" element={<SuspenseWrapper><DocsLayout /></SuspenseWrapper>}>
            <Route index element={<Navigate to="/docs/overview" replace />} />
            <Route path="overview" element={<SuspenseWrapper><DocsOverview /></SuspenseWrapper>} />
            <Route path="data-sources" element={<SuspenseWrapper><DocsDataSources /></SuspenseWrapper>} />
            <Route path="calculations" element={<SuspenseWrapper><DocsCalculations /></SuspenseWrapper>} />
            <Route path="statuses" element={<SuspenseWrapper><DocsStatuses /></SuspenseWrapper>} />
            <Route path="walkthroughs" element={<SuspenseWrapper><DocsWalkthroughs /></SuspenseWrapper>} />
            <Route path="dashboard-guide" element={<SuspenseWrapper><DocsDashboardGuide /></SuspenseWrapper>} />
            <Route path="workflows" element={<SuspenseWrapper><DocsWorkflows /></SuspenseWrapper>} />
            <Route path="architecture" element={<SuspenseWrapper><DocsArchitecture /></SuspenseWrapper>} />
            <Route path="glossary" element={<SuspenseWrapper><DocsGlossary /></SuspenseWrapper>} />
            <Route path="*" element={<Navigate to="/docs/overview" replace />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<SuspenseWrapper><Home /></SuspenseWrapper>} />
              <Route path="/brands" element={<SuspenseWrapper><BrandOverview /></SuspenseWrapper>} />
              <Route path="/brands/:categoryName/skus" element={<SuspenseWrapper><SkuDetail /></SuspenseWrapper>} />
              <Route path="/brands/:categoryName/po" element={<SuspenseWrapper><PoBuilder /></SuspenseWrapper>} />
              <Route path="/po" element={<SuspenseWrapper><PoBuilder /></SuspenseWrapper>} />
              <Route path="/brands/:categoryName/dead-stock" element={<SuspenseWrapper><DeadStock /></SuspenseWrapper>} />
              <Route path="/parties" element={<SuspenseWrapper><PartyClassification /></SuspenseWrapper>} />
              <Route path="/suppliers" element={<SuspenseWrapper><SupplierManagement /></SuspenseWrapper>} />
              <Route path="/critical" element={<SuspenseWrapper><CriticalSkus /></SuspenseWrapper>} />
              <Route path="/overrides" element={<SuspenseWrapper><OverrideReview /></SuspenseWrapper>} />
              <Route path="/settings" element={<SuspenseWrapper><Settings /></SuspenseWrapper>} />
              <Route path="/users" element={<SuspenseWrapper><Users /></SuspenseWrapper>} />
              <Route path="*" element={
                <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
                  <h1 className="text-4xl font-bold mb-2">404</h1>
                  <p className="text-muted-foreground mb-6">Page not found</p>
                  <a href="/" className="text-primary hover:underline">Go to Home</a>
                </div>
              } />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
