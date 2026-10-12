import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { MATCH_LABELS, STATUS_LABELS, StatusBadge } from './RecoveryList'

const ACTIONS = {
  under_review: 'Start review',
  pending: 'Return to pending',
  approved: 'Approve',
  rejected: 'Reject',
  completed: 'Mark completed (no email)',
}
const CONFIRM = {
  approved: 'Approve this request? You will then be able to email the registry details.',
  rejected: 'Reject this request? No details will be sent.',
  completed: 'Mark as completed without sending an email?',
}
const RECIPIENT = {
  registry_contact: "the contact email saved on the registry",
  submitted_after_manual_verification: 'the submitted email (the registry has none, and you verified the customer manually)',
}

function Row({ label, children }) {
  return <div className="detail"><dt>{label}</dt><dd className="detail-plain">{children || <span className="muted">Not provided</span>}</dd></div>
}

export default function RecoveryDetail() {
  const { id } = useParams()
  const [req, setReq] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [notes, setNotes] = useState('')
  const [link, setLink] = useState('')
  const [manual, setManual] = useState(false)
  const [manualNote, setManualNote] = useState('')

  const load = (data) => { setReq(data); setNotes(data.admin_notes || '') }
  useEffect(() => { api.admin.recovery.get(id).then(load).catch((e) => setError(e.status === 404 ? 'Request not found.' : e.message)) }, [id])

  async function run(action) {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await action()
      load(result)
      return result
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setBusy(false)
    }
  }

  const change = async (status) => {
    if (CONFIRM[status] && !window.confirm(CONFIRM[status])) return
    const body = { status }
    if (status === 'approved' && req.registry_match !== 'match') {
      body.manually_verified = manual
      body.verification_note = manualNote
    }
    const done = await run(() => api.admin.recovery.update(id, body))
    if (done) setNotice(`Marked as ${STATUS_LABELS[status].toLowerCase()}.`)
  }
  const saveNotes = async () => { if (await run(() => api.admin.recovery.update(id, { admin_notes: notes }))) setNotice('Notes saved.') }
  const linkRegistry = async () => { if (await run(() => api.admin.recovery.update(id, { registry_number: link }))) { setLink(''); setNotice('Registry linked.') } }
  const sendEmail = async () => {
    if (!window.confirm(`Email the registry number and code to ${req.email_recipient.masked}?`)) return
    const result = await run(() => api.admin.recovery.sendEmail(id))
    if (result?.notice) setNotice(result.notice)
    // A failed attempt is recorded by the server; reload so the screen shows what was recorded.
    else api.admin.recovery.get(id).then(load).catch(() => {})
  }

  if (error && !req) return <><p className="field-error" role="alert">{error}</p><Link to="/admin/recovery" className="btn btn-ghost">Back to requests</Link></>
  if (!req) return <p className="status-line" role="status">Loading…</p>

  const needsManual = req.allowed_transitions.includes('approved') && req.registry_match !== 'match'
  const closed = req.status === 'completed'
  const canLink = !['approved', 'completed'].includes(req.status)

  return (
    <>
      <div className="page-head">
        <h1 className="h2">{req.request_ref} <StatusBadge status={req.status} /></h1>
        <Link to="/admin/recovery" className="btn btn-ghost">All requests</Link>
      </div>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="notice error" role="alert">{error}</p>}

      <div className="rec-grid">
        <section className="card" aria-labelledby="rec-submitted">
          <h2 id="rec-submitted" className="h3">What the customer sent</h2>
          <dl className="details one">
            <Row label="Name">{req.customer_name}</Row>
            <Row label="Email">{req.email}</Row>
            <Row label="Registry number">{req.registry_number}</Row>
            <Row label="Message">{req.message && <span className="pre">{req.message}</span>}</Row>
            <Row label="Received">{formatDateTime(req.created_at)}</Row>
          </dl>
        </section>

        <section className="card" aria-labelledby="rec-registry">
          <h2 id="rec-registry" className="h3">Matching registry</h2>
          {req.registry ? (
            <>
              <dl className="details one">
                <Row label="Registry"><Link to={`/admin/registries/${req.registry.id}`} className="text-link">{req.registry.registry_number}</Link></Row>
                <Row label="Dedicated to">{req.registry.dedicated_to}</Row>
                <Row label="Dedicated by">{req.registry.dedicated_by}</Row>
                <Row label="Contact email on file">{req.registry.contact_email}</Row>
              </dl>
              <p className={`match-panel match-${req.registry_match}`} role="status">
                <strong>{MATCH_LABELS[req.registry_match]}.</strong>{' '}
                {req.registry_match === 'match' && 'The submitted email equals the one on file for this registry.'}
                {req.registry_match === 'mismatch' && 'The submitted email is not the one on file. Verify the customer another way before approving.'}
                {req.registry_match === 'no_email_on_file' && 'This registry has no contact email, so the customer must be verified another way before approving.'}
              </p>
              <p className="hint">A matching name is never enough on its own.</p>
            </>
          ) : (
            <p className="muted">No registry is linked yet. Find it in the registry list, then link it by number.</p>
          )}
          {canLink && (
            <div className="inline-form">
              <label htmlFor="link-number" className="sr-only">Registry number to link</label>
              <input id="link-number" value={link} onChange={(e) => setLink(e.target.value)} placeholder="Registry number" autoComplete="off" />
              <button className="btn btn-ghost btn-sm" disabled={busy || !link.trim()} onClick={linkRegistry}>Link</button>
            </div>
          )}
        </section>
      </div>

      <section className="card rec-section" aria-labelledby="rec-review">
        <h2 id="rec-review" className="h3">Review</h2>
        <div className="field">
          <label htmlFor="admin-notes">Private notes</label>
          <textarea id="admin-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
          <p className="hint">Only admins can see these. Do not paste passwords or card details.</p>
        </div>
        <button className="btn btn-ghost btn-sm" disabled={busy || notes === (req.admin_notes || '')} onClick={saveNotes}>Save notes</button>

        {needsManual && (
          <fieldset className="manual-verify">
            <legend>Manual verification (needed to approve)</legend>
            <label className="check">
              <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />
              I verified this customer through the original order or another reliable record.
            </label>
            <div className="field">
              <label htmlFor="manual-note">How did you verify them?</label>
              <textarea id="manual-note" rows={2} value={manualNote} onChange={(e) => setManualNote(e.target.value)} maxLength={1000}
                placeholder="e.g. Matched the Instagram order of 3 March and the delivery address" />
            </div>
            <p className="hint">The email saved on the registry is never changed by approving a request.</p>
          </fieldset>
        )}

        <div className="actions">
          {req.allowed_transitions.map((next) => (
            <button key={next} className={`btn ${next === 'approved' ? 'btn-primary' : 'btn-ghost'}`}
              disabled={busy || (next === 'approved' && needsManual && !(manual && manualNote.trim()))}
              onClick={() => change(next)}>
              {ACTIONS[next]}
            </button>
          ))}
          {closed && <span className="muted">This request is complete.</span>}
        </div>
        <p className="hint">
          {req.reviewed_by ? `Last reviewed by ${req.reviewed_by} on ${formatDateTime(req.reviewed_at)}.` : 'Not reviewed yet.'}
          {req.verification_basis && ` Verified by ${req.verification_basis === 'email_match' ? 'email match' : 'manual check'}.`}
          {req.completed_at && ` Completed ${formatDateTime(req.completed_at)}.`}
        </p>
      </section>

      {req.status === 'approved' && (
        <section className="card rec-section" aria-labelledby="rec-email">
          <h2 id="rec-email" className="h3">Send the details</h2>
          {req.email_recipient ? (
            <p>This will email the Registry Number and Registry Code to <strong>{req.email_recipient.masked}</strong>, {RECIPIENT[req.email_recipient.kind]}.
              The email contains no document links; the customer verifies on the website to download their documents.</p>
          ) : (
            <p className="muted">There is no verified address to send to yet.</p>
          )}
          {req.email_status === 'failed' && (
            <p className="notice error" role="alert">
              The last attempt failed ({req.email_error}). The request is still Approved so you can try again once email is working.
            </p>
          )}
          <div className="actions">
            <button className="btn btn-primary" disabled={busy || !req.email_recipient} onClick={sendEmail}>
              {busy ? 'Sending…' : 'Send registry details by email'}
            </button>
          </div>
        </section>
      )}
      {req.email_status === 'sent' && (
        <p className="notice" role="status">Email accepted by the mail server on {formatDateTime(req.email_sent_at)}.</p>
      )}
    </>
  )
}
