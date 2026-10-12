import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recovery, setRecovery] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.admin.stats().then(setStats).catch((e) => setError(e.message))
    api.admin.recovery.summary().then(setRecovery).catch(() => {})
  }, [])

  return (
    <>
      <h1 className="h2">Dashboard</h1>
      {error && <p className="field-error" role="alert">{error}</p>}
      <div className="stat-grid">
        {[['Total registries', 'total'], ['Active registries', 'active'], ['Inactive registries', 'inactive']].map(([label, key]) => (
          <div className="card stat" key={key}>
            <p className="stat-value">{stats ? stats[key] : '–'}</p>
            <p className="stat-label">{label}</p>
          </div>
        ))}
        <Link to="/admin/recovery?status=pending" className="card stat stat-link">
          <p className="stat-value">{recovery ? recovery.pending : '–'}</p>
          <p className="stat-label">Recovery requests waiting</p>
        </Link>
      </div>
      <div className="actions">
        <Link to="/admin/registries/new" className="btn btn-primary">Add registry</Link>
        <Link to="/admin/registries" className="btn btn-ghost">Manage registries</Link>
      </div>
    </>
  )
}
