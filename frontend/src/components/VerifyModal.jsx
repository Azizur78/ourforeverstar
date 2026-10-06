import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import logo from '../assets/ourforeverstar-logo.jpg'
import { api } from '../lib/api'
import { SITE_NAME } from '../lib/config'

const VerifyContext = createContext(null)
export const useVerify = () => useContext(VerifyContext)

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'

const ERRORS = {
  limited: 'Too many attempts. Please wait a few minutes and try again.',
  network: 'We could not reach the server. Please check your connection and try again.',
  server: 'Something went wrong. Please try again shortly.',
}

/** Single source of the Verify Registry experience. Mount once; open from anywhere via useVerify(). */
export function VerifyProvider({ children }) {
  const [open, setOpen] = useState(false)
  const [expired, setExpired] = useState(false)
  const trigger = useRef(null)
  const navigate = useNavigate()
  const location = useLocation()

  const openVerify = useCallback((opts = {}) => {
    trigger.current = document.activeElement
    setExpired(Boolean(opts.expired))
    setOpen(true)
  }, [])

  const closeVerify = useCallback(() => {
    setOpen(false)
    if (window.location.pathname === '/verify') navigate('/', { replace: true })
    const el = trigger.current
    trigger.current = null
    // Return focus to whatever opened the dialog, if it still exists.
    setTimeout(() => el && document.contains(el) && el.focus?.(), 0)
  }, [navigate])

  const onVerified = useCallback((publicId) => {
    setOpen(false)
    trigger.current = null
    navigate(`/registry/${encodeURIComponent(publicId)}`)
    setTimeout(() => document.getElementById('main')?.focus(), 0)
  }, [navigate])

  // /verify (QR/NFC/bookmarks) opens the modal over the home page.
  useEffect(() => {
    if (location.pathname === '/verify') openVerify({ expired: Boolean(location.state?.expired) })
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo(() => ({ openVerify }), [openVerify])
  return (
    <VerifyContext.Provider value={value}>
      {children}
      {open && createPortal(<VerifyDialog expired={expired} onClose={closeVerify} onVerified={onVerified} />, document.body)}
    </VerifyContext.Provider>
  )
}

/** Any "Verify Registry" call to action. Renders a real link (/verify) that opens the modal. */
export function VerifyLink({ className, children }) {
  const { openVerify } = useVerify()
  return (
    <a
      href="/verify"
      className={className}
      onClick={(e) => {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
        e.preventDefault()
        openVerify()
      }}
    >
      {children}
    </a>
  )
}

function VerifyDialog({ expired, onClose, onVerified }) {
  const dialogRef = useRef(null)
  const numberRef = useRef(null)
  const submitting = useRef(false)
  const pressedOnBackdrop = useRef(false)
  const [number, setNumber] = useState('')
  const [code, setCode] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)

  // Lock page scroll, make the page behind inert, focus the first field.
  useEffect(() => {
    const root = document.getElementById('root')
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (root) root.inert = true
    numberRef.current?.focus()
    return () => {
      document.body.style.overflow = prevOverflow
      if (root) root.inert = false
    }
  }, [])

  // Escape closes; Tab stays inside the dialog.
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
        else if (!dialogRef.current.contains(document.activeElement)) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function submit(e) {
    e.preventDefault()
    if (submitting.current) return
    const errs = {}
    if (!number.trim()) errs.number = 'Please enter your Registry Number.'
    if (!code.trim()) errs.code = 'Please enter your Registry Code.'
    setFieldErrors(errs)
    setFailure('')
    if (errs.number || errs.code) {
      (errs.number ? numberRef.current : dialogRef.current.querySelector('#vm-code'))?.focus()
      return
    }
    submitting.current = true
    setBusy(true)
    try {
      const { public_id } = await api.verify(number.trim(), code.trim())
      onVerified(public_id)
    } catch (err) {
      setFailure(
        err.network ? ERRORS.network
          : err.status === 404 ? err.message // the server's generic "could not be verified" text
            : err.status === 429 ? ERRORS.limited : ERRORS.server,
      )
      submitting.current = false
      setBusy(false)
    }
  }

  const describedBy = (key, id) => (fieldErrors[key] ? id : undefined)

  return (
    <div
      className="vm-backdrop"
      onMouseDown={(e) => { pressedOnBackdrop.current = e.target === e.currentTarget }}
      onMouseUp={(e) => {
        // Only a full click that starts and ends on the backdrop closes it (not a text-selection drag).
        if (pressedOnBackdrop.current && e.target === e.currentTarget) onClose()
        pressedOnBackdrop.current = false
      }}
    >
      <div ref={dialogRef} className="vm-dialog" role="dialog" aria-modal="true" aria-labelledby="vm-title" aria-describedby="vm-sub">
        <button type="button" className="vm-close" onClick={onClose} aria-label="Close">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
        </button>

        <div className="vm-brand">
          <img src={logo} alt={`${SITE_NAME} seal`} className="vm-logo" width="735" height="735" />
          <p className="vm-wordmark">{SITE_NAME}</p>
        </div>

        <h2 id="vm-title" className="vm-title">Verify Your Star Registry</h2>
        <p id="vm-sub" className="vm-sub">Enter your registry details to view your dedication.</p>

        {expired && <p className="notice vm-notice" role="status">Your session has ended. Please verify again to view your registry.</p>}

        <form onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor="vm-number">Registry Number</label>
            <input id="vm-number" ref={numberRef} value={number} onChange={(e) => setNumber(e.target.value)}
              placeholder="e.g. HIP-2026-000401" autoComplete="off" autoCapitalize="characters" autoCorrect="off"
              spellCheck="false" aria-invalid={fieldErrors.number ? true : undefined}
              aria-describedby={describedBy('number', 'vm-number-error')} />
            {fieldErrors.number && <p id="vm-number-error" className="field-error">{fieldErrors.number}</p>}
          </div>
          <div className="field">
            <label htmlFor="vm-code">Registry Code</label>
            <input id="vm-code" value={code} onChange={(e) => setCode(e.target.value)}
              placeholder="Your private code" autoComplete="off" autoCapitalize="characters" autoCorrect="off"
              spellCheck="false" aria-invalid={fieldErrors.code ? true : undefined}
              aria-describedby={describedBy('code', 'vm-code-error')} />
            {fieldErrors.code && <p id="vm-code-error" className="field-error">{fieldErrors.code}</p>}
          </div>

          <div aria-live="assertive">
            {failure && (
              <div className="vm-error" role="alert">
                <p>{failure}</p>
                {failure === 'Registry details could not be verified.' && (
                  <p className="vm-error-hint">Please check your Registry Number and Registry Code and try again.</p>
                )}
              </div>
            )}
          </div>

          <button type="submit" className="btn btn-primary btn-block" disabled={busy} aria-busy={busy}>
            {busy ? 'VERIFYING…' : 'VERIFY REGISTRY'}
          </button>
        </form>

        <p className="vm-help">Need help? <Link to="/contact" className="text-link" onClick={onClose}>Contact Us</Link></p>
      </div>
    </div>
  )
}
