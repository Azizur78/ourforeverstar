import { createContext, useContext, useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BrandSeal } from '../components/Brand'
import { SITE_NAME } from '../lib/config'
import { api } from '../lib/api'
import { useMeta } from '../lib/meta'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

/** Guards every /admin route (except login) and provides the signed-in user. */
export default function AdminLayout() {
  const [user, setUser] = useState(undefined) // undefined = checking, null = signed out
  const [loadError, setLoadError] = useState('')
  const location = useLocation()
  const navigate = useNavigate()
  useMeta({ title: 'Admin', noindex: true })

  useEffect(() => {
    api.admin.me()
      .then((r) => setUser(r.username))
      .catch((err) => {
        if (err.status === 401) setUser(null)
        else setLoadError(err.message)
      })
  }, [])

  async function logout() {
    try { await api.admin.logout() } finally {
      setUser(null)
      navigate('/admin/login', { replace: true })
    }
  }

  if (loadError) return <p className="status-line" role="alert">{loadError}</p>
  if (user === undefined) return <p className="status-line" role="status">Loading…</p>
  if (user === null) return <Navigate to="/admin/login" state={{ from: location.pathname }} replace />

  return (
    <AuthContext.Provider value={{ user, signOutLocally: () => setUser(null) }}>
      <div className="admin">
        <header className="admin-bar">
          <div className="container admin-bar-row">
            <Link to="/admin" className="admin-brand" aria-label={`${SITE_NAME} Admin Portal, dashboard`}>
              <BrandSeal size={38} />
              <span className="admin-brand-text">{SITE_NAME}<small>Admin Portal</small></span>
            </Link>
            <nav aria-label="Admin">
              <NavLink to="/admin" end>Dashboard</NavLink>
              <NavLink to="/admin/registries" end>Registries</NavLink>
              <NavLink to="/admin/registries/new">Add registry</NavLink>
              <NavLink to="/admin/password">Change password</NavLink>
            </nav>
            <div className="admin-user">
              <Link to="/" className="text-link small">View site</Link>
              <button className="btn btn-ghost btn-sm" onClick={logout}>Sign out ({user})</button>
            </div>
          </div>
        </header>
        <main id="main" className="container admin-main">
          <Outlet />
        </main>
      </div>
    </AuthContext.Provider>
  )
}
