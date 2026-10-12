import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import SiteLayout from './components/SiteLayout'
import About from './pages/About'
import Contact from './pages/Contact'
import Faq from './pages/Faq'
import Gifting from './pages/Gifting'
import Home from './pages/Home'
import HowItWorks from './pages/HowItWorks'
import NotFound from './pages/NotFound'
import Recover from './pages/Recover'
import Registry from './pages/Registry'
import { VerifyProvider } from './components/VerifyModal'

// The admin portal is split out so public visitors never download it.
const AdminLayout = lazy(() => import('./admin/AdminLayout'))
const Login = lazy(() => import('./admin/Login'))
const ChangePassword = lazy(() => import('./admin/ChangePassword'))
const Dashboard = lazy(() => import('./admin/Dashboard'))
const RegistryList = lazy(() => import('./admin/RegistryList'))
const RegistryForm = lazy(() => import('./admin/RegistryForm'))
const RecoveryList = lazy(() => import('./admin/RecoveryList'))
const RecoveryDetail = lazy(() => import('./admin/RecoveryDetail'))
const RegistryBatchForm = lazy(() => import('./admin/RegistryBatchForm'))
const RegistryDetail = lazy(() => import('./admin/RegistryDetail'))

export default function App() {
  return (
    <Suspense fallback={<p className="status-line" role="status">Loading…</p>}>
      <VerifyProvider>
      <Routes>
        <Route element={<SiteLayout />}>
          <Route index element={<Home />} />
          <Route path="celestial-gifting" element={<Gifting />} />
          <Route path="about" element={<About />} />
          <Route path="how-it-works" element={<HowItWorks />} />
          <Route path="faq" element={<Faq />} />
          <Route path="contact" element={<Contact />} />
          {/* /verify (QR / NFC / bookmarks) shows the home page with the Verify Registry modal open. */}
          <Route path="verify" element={<Home />} />
          <Route path="recover" element={<Recover />} />
          <Route path="registry/:publicId" element={<Registry />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="admin/login" element={<Login />} />
        <Route path="admin" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="password" element={<ChangePassword />} />
          <Route path="recovery" element={<RecoveryList />} />
          <Route path="recovery/:id" element={<RecoveryDetail />} />
          <Route path="registries" element={<RegistryList />} />
          <Route path="registries/new" element={<RegistryBatchForm />} />
          <Route path="registries/:id" element={<RegistryDetail />} />
          <Route path="registries/:id/edit" element={<RegistryForm />} />
        </Route>
      </Routes>
      </VerifyProvider>
    </Suspense>
  )
}
