import { useState } from 'react'
import { Link } from 'react-router-dom'
import { InstagramLink } from '../components/Ui'
import { api } from '../lib/api'
import { useMeta } from '../lib/meta'

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+([.][A-Za-z0-9-]+)+$/
const EMPTY = { customer_name: '', email: '', registry_number: '', message: '', website: '' }

function Field({ id, label, optional, error, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}{optional && <span className="optional"> (optional)</span>}</label>
      {children}
      {hint && !error && <p className="hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  )
}

export default function Recover() {
  useMeta({
    title: 'Recover your registry details',
    description: 'Lost your Registry Number or Registry Code? Send us a request and our team will review it personally.',
    noindex: true,
  })
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState('')

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }))
  const aria = (name) => ({
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `${name}-error` : `${name}-hint`,
  })

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setFailure('')
    const found = {}
    if (form.customer_name.trim().length < 2) found.customer_name = 'Please enter your name.'
    if (!EMAIL_RE.test(form.email.trim())) found.email = 'Please enter a valid email address.'
    setErrors(found)
    if (Object.keys(found).length) return

    setBusy(true)
    try {
      const result = await api.requestRecovery({
        customer_name: form.customer_name, email: form.email, website: form.website,
        registry_number: form.registry_number.trim() || null, message: form.message.trim() || null,
      })
      setDone(result.message)
    } catch (err) {
      if (err.status === 422) {
        setErrors(Object.fromEntries(err.fieldErrors.map((x) => [x.field, x.message])))
        setFailure('Please check the highlighted fields.')
      } else {
        setFailure(err.status === 429 ? 'You have sent several requests. Please try again a little later.' : err.message)
      }
      setBusy(false)
    }
  }

  return (
    <section className="verify">
      <div className="container verify-wrap recover-wrap">
        <p className="eyebrow">Registry help</p>
        <h1>Lost your registry details?</h1>
        <p className="lede">Tell us who you are and our team will review your request personally.</p>

        {done ? (
          <div className="card result-card" role="status">
            <h2>Request received</h2>
            <p>{done}</p>
            <div className="actions center">
              <Link to="/" className="btn btn-primary">Back to Home</Link>
              <InstagramLink className="btn btn-ghost">Message us on Instagram</InstagramLink>
            </div>
          </div>
        ) : (
          <form className="card form-card" onSubmit={submit} noValidate>
            <Field id="customer_name" label="Your name" error={errors.customer_name}>
              <input id="customer_name" value={form.customer_name} onChange={set('customer_name')} autoComplete="name"
                maxLength={120} {...aria('customer_name')} />
            </Field>
            <Field id="email" label="Email address" error={errors.email}
              hint="Use the email you used when you ordered, if you can.">
              <input id="email" type="email" value={form.email} onChange={set('email')} autoComplete="email" maxLength={254}
                {...aria('email')} />
            </Field>
            <Field id="registry_number" label="Registry Number" optional error={errors.registry_number}
              hint="If you remember it, for example HIP-2026-000401.">
              <input id="registry_number" value={form.registry_number} onChange={set('registry_number')} autoComplete="off"
                autoCapitalize="characters" spellCheck="false" maxLength={40} {...aria('registry_number')} />
            </Field>
            <Field id="message" label="Anything that will help us find your order" optional error={errors.message}>
              <textarea id="message" rows={4} value={form.message} onChange={set('message')} maxLength={1000} {...aria('message')} />
            </Field>

            {/* Honeypot: invisible to people, tempting to bots. */}
            <div className="hp" aria-hidden="true">
              <label htmlFor="website">Leave this field empty</label>
              <input id="website" name="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
            </div>

            {failure && <p className="vm-error" role="alert">{failure}</p>}
            <button className="btn btn-primary btn-block" disabled={busy} aria-busy={busy}>
              {busy ? 'SENDING…' : 'SEND REQUEST'}
            </button>
            <p className="recover-note">
              For your security we cannot say whether a registry exists, and we only ever send details to an address we can verify.
            </p>
          </form>
        )}

        <p className="help">Remembered them? <Link to="/verify" className="text-link">Verify your registry</Link></p>
      </div>
    </section>
  )
}
