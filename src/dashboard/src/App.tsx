import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'

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

function LoadingSkeleton() {
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
      <Routes>
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
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
