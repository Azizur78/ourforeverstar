import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BrandSeal } from '../components/Brand'
import PasswordField from '../components/PasswordField'
import StarField from '../components/StarField'
import { api } from '../lib/api'
import { SITE_NAME } from '../lib/config'
import { useMeta } from '../lib/meta'

export default function Login() {
  useMeta({ title: 'Admin Login', noindex: true })
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setFailure('')
    const errs = {}
    if (!username.trim()) errs.username = 'Please enter your username.'
    if (!password) errs.password = 'Please enter your password.'
    setErrors(errs)
    if (errs.username || errs.password) return
    setBusy(true)
    try {
      await api.admin.login(username.trim(), password)
      navigate(location.state?.from || '/admin', { replace: true })
    } catch (err) {
      setFailure(err.status === 401 ? 'Invalid username or password.' : err.message)
      setBusy(false)
    }
  }

  return (
    <div className="gate">
      <StarField />
      <main id="main" className="gate-main">
        <div className="gate-card">
          <BrandSeal size={92} className="gate-seal" />
          <p className="gate-brand">{SITE_NAME}</p>
          <p className="gate-badge">Admin Portal</p>
          <h1 className="gate-title">Admin Login</h1>

          <form onSubmit={submit} noValidate>
            <div className="field">
              <label htmlFor="username">Username</label>
              <input id="username" value={username} onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck="false"
                aria-invalid={errors.username ? true : undefined}
                aria-describedby={errors.username ? 'username-error' : undefined} />
              {errors.username && <p id="username-error" className="field-error" role="alert">{errors.username}</p>}
            </div>
            <PasswordField id="password" label="Password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} error={errors.password} />
            {failure && <p className="vm-error" role="alert">{failure}</p>}
            <button className="btn btn-primary btn-block" disabled={busy} aria-busy={busy}>
              {busy ? 'SIGNING IN…' : 'LOGIN'}
            </button>
          </form>
          <p className="gate-note">Authorised staff only.</p>
        </div>
      </main>
    </div>
  )
}
