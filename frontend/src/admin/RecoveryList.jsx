import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { formatDateTime } from '../lib/format'

export const STATUS_LABELS = {
  pending: 'Pending', under_review: 'Under review', approved: 'Approved', rejected: 'Rejected', completed: 'Completed',
}
export const MATCH_LABELS = {
  match: 'Email matches', mismatch: 'Email differs', no_email_on_file: 'No email on file', no_registry: 'No registry linked',
}
const PAGE_SIZE = 20

export function StatusBadge({ status }) {
  return <span className={`badge st-${status}`}>{STATUS_LABELS[status] || status}</span>
}

export default function RecoveryList() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') || ''
  const page = Number(params.get('page') || 1)
  const [data, setData] = useState(null)
  const [counts, setCounts] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    api.admin.recovery.list({ status, page, page_size: PAGE_SIZE }).then(setData).catch((e) => setError(e.message))
  }, [status, page])
  useEffect(() => { api.admin.recovery.summary().then(setCounts).catch(() => {}) }, [])

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    setParams(next, { replace: true })
  }
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <>
      <div className="page-head"><h1 className="h2">Recovery requests</h1></div>
      <p className="muted batch-intro">
        Customers who lost their registry details ask for help here. Review each request by hand: a name alone is never enough.
      </p>

      <div className="toolbar">
        <div className="field">
          <label htmlFor="status-filter">Status</label>
          <select id="status-filter" value={status} onChange={(e) => update({ status: e.target.value, page: '' })}>
            <option value="">All{counts ? ` (${Object.values(counts).reduce((a, b) => a + b, 0)})` : ''}</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}{counts ? ` (${counts[value]})` : ''}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="field-error" role="alert">{error}</p>}
      {!data && !error && <p className="status-line" role="status">Loading…</p>}
      {data && data.items.length === 0 && (
        <div className="card empty"><p>{status ? 'No requests with this status.' : 'No recovery requests yet.'}</p></div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Reference</th><th scope="col">Customer</th><th scope="col">Email</th>
                  <th scope="col">Registry</th><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Received</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td data-label="Reference"><Link to={`/admin/recovery/${r.id}`}>{r.request_ref}</Link></td>
                    <td data-label="Customer">{r.customer_name}</td>
                    <td data-label="Email">{r.email}</td>
                    <td data-label="Registry">{r.registry_number || <span className="muted">Not given</span>}</td>
                    <td data-label="Check"><span className={`match match-${r.registry_match}`}>{MATCH_LABELS[r.registry_match]}</span></td>
                    <td data-label="Status"><StatusBadge status={r.status} /></td>
                    <td data-label="Received">{formatDateTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span>{data.total} request{data.total === 1 ? '' : 's'}</span>
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
