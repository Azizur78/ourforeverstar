import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/
const INVALID = 'Please enter a valid email address, or close this window to skip.'

/**
 * Optional, one-time offer shown after verification when no recovery email is saved for the registry.
 * Closing it (cross, Escape, backdrop) simply skips; nothing is required to use the site.
 */
export default function RecoveryEmailPrompt({ publicId, onClose, onSaved }) {
  const dialogRef = useRef(null)
  const inputRef = useRef(null)
  const busyRef = useRef(false)
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    const root = document.getElementById('root')
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (root) root.inert = true
    inputRef.current?.focus()
    return () => {
      document.body.style.overflow = prevOverflow
      if (root) root.inert = false
    }
  }, [])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      } else if (e.key === 'Tab' && dialogRef.current) {
        const items = [...dialogRef.current.querySelectorAll(FOCUSABLE)]
        if (!items.length) return
        const first = items[0]
        const last = items[items.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function submit(e) {
    e.preventDefault()
    if (busyRef.current) return
    const value = email.trim()
    if (!EMAIL_RE.test(value) || value.length > 254) {
      setError(INVALID)
      inputRef.current?.focus()
      return
    }
    busyRef.current = true
    setBusy(true)
    setError('')
    try {
      await api.saveContactEmail(publicId, value)
      setDone(true)
      onSaved()
    } catch (err) {
      if (err.status === 409) { onSaved(); onClose(); return }
      setError(
        err.network ? 'We could not reach the server. Please try again, or close this window to skip.'
          : err.status === 429 ? 'Too many attempts. Please try again later, or close this window to skip.'
            : err.status === 422 ? INVALID
              : 'We could not save your email just now. You can close this window and carry on.',
      )
      busyRef.current = false
      setBusy(false)
    }
  }

  return createPortal(
    <div className="vm-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={dialogRef} className="vm-dialog email-prompt" role="dialog" aria-modal="true"
        aria-labelledby="ep-title" aria-describedby="ep-body">
        <button type="button" className="vm-close" onClick={onClose} aria-label="Close and skip">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
        </button>
        {done ? (
          <>
            <h2 id="ep-title" className="vm-title">Thank you</h2>
            <p id="ep-body" className="vm-sub" role="status">
              Your recovery email is saved. If you ever lose your registry details, we can use it to help you get them back.
            </p>
            <div className="actions center">
              <button type="button" className="btn btn-primary" onClick={onClose}>Continue to my registry</button>
            </div>
          </>
        ) : (
          <>
            <h2 id="ep-title" className="vm-title">Add an email for account recovery</h2>
            <p id="ep-body" className="vm-sub">
              This is optional. If you ever lose your Registry Number or Registry Code, an email on file lets us confirm it is you
              and help you recover your details. It is used only for that. If you would rather not, simply close this window with
              the cross and carry on.
            </p>
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="ep-email">Email address (optional)</label>
                <input id="ep-email" ref={inputRef} type="email" inputMode="email" autoComplete="email" value={email}
                  onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" maxLength={254}
                  aria-invalid={error ? true : undefined} aria-describedby={error ? 'ep-error' : undefined} />
                {error && <p id="ep-error" className="field-error" role="alert">{error}</p>}
              </div>
              <div className="actions center">
                <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save my email'}</button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}
