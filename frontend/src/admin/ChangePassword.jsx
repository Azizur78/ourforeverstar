import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PasswordField from '../components/PasswordField'
import { api } from '../lib/api'

const MIN = 10
const EMPTY = { current: '', next: '', confirm: '' }
const FIELD_KEYS = { current_password: 'current', new_password: 'next', confirm_new_password: 'confirm' }

export default function ChangePassword() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [banner, setBanner] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setBanner('')
    setSuccess('')
    const errs = {}
    if (!form.current) errs.current = 'Please enter your current password.'
    if (!form.next) errs.next = 'Please enter a new password.'
    else if (form.next.length < MIN) errs.next = 'Password does not meet the required security requirements.'
    if (!form.confirm) errs.confirm = 'Please confirm your new password.'
    else if (form.next && form.confirm !== form.next) errs.confirm = 'New passwords do not match.'
    setErrors(errs)
    if (Object.keys(errs).length) return // an invalid change is never submitted

    setBusy(true)
    try {
      await api.admin.changePassword(form.current, form.next, form.confirm)
      setForm(EMPTY)
      setSuccess('Password changed successfully.')
    } catch (err) {
      if (err.status === 401) return navigate('/admin/login', { replace: true })
      const key = FIELD_KEYS[err.field]
      if (key) setErrors({ [key]: err.message })
      else setBanner(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head"><h1 className="h2">Change Password</h1></div>
      <form className="card pw-form" onSubmit={submit} noValidate>
        {success && <p className="notice" role="status">{success}</p>}
        {banner && <p className="notice error" role="alert">{banner}</p>}
        <PasswordField id="current_password" label="Current Password" autoComplete="current-password"
          value={form.current} onChange={set('current')} error={errors.current} />
        <PasswordField id="new_password" label="New Password" autoComplete="new-password"
          value={form.next} onChange={set('next')} error={errors.next} hint={`At least ${MIN} characters.`} />
        <PasswordField id="confirm_new_password" label="Confirm New Password" autoComplete="new-password"
          value={form.confirm} onChange={set('confirm')} error={errors.confirm} />
        <button className="btn btn-primary" disabled={busy} aria-busy={busy}>{busy ? 'CHANGING…' : 'CHANGE PASSWORD'}</button>
      </form>
    </>
  )
}
