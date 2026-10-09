import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'

const PAGE_SIZE = 20

export default function RegistryList() {
  const [params, setParams] = useSearchParams()
  const notice = useLocation().state?.notice
  const q = params.get('q') || ''
  const status = params.get('status') || ''
  const page = Number(params.get('page') || 1)

  const [input, setInput] = useState(q)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const update = useCallback((changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    setParams(next, { replace: true })
  }, [params, setParams])

  // Debounce typing into the URL-backed search.
  useEffect(() => {
    if (input === q) return undefined
    const t = setTimeout(() => update({ q: input.trim(), page: '' }), 300)
    return () => clearTimeout(t)
  }, [input, q, update])

  const load = useCallback(() => {
    setError('')
    api.admin.list({ q, status, page, page_size: PAGE_SIZE })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [q, status, page])

  useEffect(load, [load])

  async function toggle(row) {
    const next = row.status === 'active' ? 'inactive' : 'active'
    const verb = next === 'inactive' ? 'Deactivate' : 'Activate'
    const warning = next === 'inactive' ? ' Customers will no longer be able to verify it.' : ''
    if (!window.confirm(`${verb} registry ${row.registry_number}?${warning}`)) return
    setBusyId(row.id)
    try {
      await api.admin.setStatus(row.id, next)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <>
      <div className="page-head">
        <h1 className="h2">Registries</h1>
        <Link to="/admin/registries/new" className="btn btn-primary">Add registry</Link>
      </div>
      {notice && <p className="notice" role="status">{notice}</p>}

      <div className="toolbar">
        <div className="field grow">
          <label htmlFor="search">Search</label>
          <input id="search" type="search" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Registry number, code, dedicated to or by" />
        </div>
        <div className="field">
          <label htmlFor="status-filter">Status</label>
          <select id="status-filter" value={status} onChange={(e) => update({ status: e.target.value, page: '' })}>
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {error && <p className="field-error" role="alert">{error}</p>}
      {!data && !error && <p className="status-line" role="status">Loading…</p>}

      {data && data.items.length === 0 && (
        <div className="card empty">
          <p>{q || status ? 'No registries match your search.' : 'No registries yet.'}</p>
          {!q && !status && <Link to="/admin/registries/new" className="btn btn-primary">Add the first registry</Link>}
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Registry number</th>
                  <th scope="col">Registry code</th>
                  <th scope="col">Dedicated to</th>
                  <th scope="col">Dedicated by</th>
                  <th scope="col">Date</th>
                  <th scope="col">Status</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td data-label="Registry number"><Link to={`/admin/registries/${r.id}`}>{r.registry_number}</Link></td>
                    <td data-label="Registry code"><code>{r.registry_code}</code></td>
                    <td data-label="Dedicated to">{r.dedicated_to}</td>
                    <td data-label="Dedicated by">{r.dedicated_by}</td>
                    <td data-label="Date">{formatDate(r.dedication_date)}</td>
                    <td data-label="Status"><span className={`badge ${r.status}`}>{r.status}</span></td>
                    <td className="row-actions">
                      <Link to={`/admin/registries/${r.id}`} className="btn btn-ghost btn-sm">View</Link>
                      <Link to={`/admin/registries/${r.id}/edit`} className="btn btn-ghost btn-sm">Edit</Link>
                      <button className="btn btn-ghost btn-sm" disabled={busyId === r.id} onClick={() => toggle(r)}>
                        {r.status === 'active' ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span>{data.total} registr{data.total === 1 ? 'y' : 'ies'}</span>
            <div className="actions">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</button>
              <span>Page {page} of {pages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>Next</button>
            </div>
          </div>
        </>
      )}
    </>
  )
}
