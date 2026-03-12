import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import BrandOverview from './pages/BrandOverview'
import SkuDetail from './pages/SkuDetail'
import PoBuilder from './pages/PoBuilder'
import PartyClassification from './pages/PartyClassification'
import SupplierManagement from './pages/SupplierManagement'
import OverrideReview from './pages/OverrideReview'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<BrandOverview />} />
          <Route path="/brands/:categoryName/skus" element={<SkuDetail />} />
          <Route path="/brands/:categoryName/po" element={<PoBuilder />} />
          <Route path="/parties" element={<PartyClassification />} />
          <Route path="/suppliers" element={<SupplierManagement />} />
          <Route path="/overrides" element={<OverrideReview />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
