import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import RegistryView from '../components/RegistryView'
import { api } from '../lib/api'
import { formatDateTime } from '../lib/format'

export default function RegistryDetail() {
  const { id } = useParams()
  const location = useLocation()
  const [registry, setRegistry] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(location.state?.notice || '')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.admin.get(id).then(setRegistry).catch((e) => setError(e.status === 404 ? 'Registry not found.' : e.message))
  }, [id])

  async function toggle() {
    const next = registry.status === 'active' ? 'inactive' : 'active'
    const warning = next === 'inactive' ? ' Customers will no longer be able to verify it.' : ''
    if (!window.confirm(`${next === 'inactive' ? 'Deactivate' : 'Activate'} registry ${registry.registry_number}?${warning}`)) return
    setBusy(true)
    try {
      setRegistry(await api.admin.setStatus(registry.id, next))
      setNotice(`Registry ${next === 'active' ? 'activated' : 'deactivated'}.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !registry) {
    return (
      <>
        <p className="field-error" role="alert">{error}</p>
        <Link to="/admin/registries" className="btn btn-ghost">Back to registries</Link>
      </>
    )
  }
  if (!registry) return <p className="status-line" role="status">Loading…</p>

  const publicShape = {
    ...registry,
    star: { catalogue: registry.star_catalogue, constellation: registry.constellation, distance: registry.distance },
  }

  return (
    <>
      <div className="page-head">
        <h1 className="h2">{registry.registry_number} <span className={`badge ${registry.status}`}>{registry.status}</span></h1>
        <div className="actions">
          <Link to={`/admin/registries/${registry.id}/edit`} className="btn btn-primary">Edit</Link>
          <button className="btn btn-ghost" onClick={toggle} disabled={busy}>
            {registry.status === 'active' ? 'Deactivate' : 'Activate'}
          </button>
          <Link to="/admin/registries" className="btn btn-ghost">All registries</Link>
        </div>
      </div>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="notice error" role="alert">{error}</p>}
      <p className="muted small">
        Created {formatDateTime(registry.created_at)} · Updated {formatDateTime(registry.updated_at)}
        {registry.status === 'inactive' && ' · Customers cannot currently verify this registry.'}
      </p>

      <h2 className="h3">Customer preview</h2>
      <div className="preview-frame">
        <RegistryView
          registry={publicShape}
          certificateUrls={{ view: api.admin.certificateUrl(registry.id), download: api.admin.certificateUrl(registry.id, true) }}
        />
      </div>
    </>
  )
}
