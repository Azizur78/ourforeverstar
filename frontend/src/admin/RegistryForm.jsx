import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'

const EMPTY = {
  registry_number: '', registry_code: '', dedicated_to: '', dedicated_by: '', dedication_date: '',
  occasion: '', star_catalogue: '', constellation: '', distance: '', dedication_message: '', status: 'active',
}
const MAX_BYTES = 5 * 1024 * 1024
const ALLOWED = ['.pdf', '.png', '.jpg', '.jpeg']

function Field({ id, label, error, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && !error && <p className="hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  )
}

export default function RegistryForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [existing, setExisting] = useState(null)
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState('')
  const [errors, setErrors] = useState({})
  const [banner, setBanner] = useState(useLocation().state?.notice || '')
  const [loading, setLoading] = useState(editing)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!editing) return
    api.admin.get(id)
      .then((r) => {
        setExisting(r)
        setForm(Object.fromEntries(Object.keys(EMPTY).map((k) => [k, r[k] ?? ''])))
      })
      .catch((e) => setBanner(e.status === 404 ? 'Registry not found.' : e.message))
      .finally(() => setLoading(false))
  }, [editing, id])

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }))
  const props = (name) => ({
    id: name, value: form[name], onChange: set(name),
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `${name}-error` : undefined,
  })

  function pickFile(e) {
    const f = e.target.files?.[0]
    setFileError('')
    setFile(null)
    if (!f) return
    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
    if (!ALLOWED.includes(ext)) return setFileError('Unsupported file type. Upload a PDF, PNG or JPG file.')
    if (f.size > MAX_BYTES) return setFileError('File is too large. Maximum size is 5 MB.')
    setFile(f)
  }

  async function submit(e) {
    e.preventDefault()
    setBanner('')
    setErrors({})
    setBusy(true)
    let saved
    try {
      saved = editing ? await api.admin.update(id, form) : await api.admin.create(form)
    } catch (err) {
      if (err.status === 422) {
        setErrors(Object.fromEntries(err.fieldErrors.map((x) => [x.field, x.message])))
        setBanner('Please correct the highlighted fields.')
      } else if (err.status === 409) {
        setErrors({ registry_number: err.message })
        setBanner(err.message)
      } else if (err.status === 401) {
        setBanner('Your session has expired. Please sign in again.')
      } else {
        setBanner(err.message)
      }
      setBusy(false)
      return
    }

    if (file) {
      try {
        await api.admin.uploadCertificate(saved.id, file)
      } catch (err) {
        // The registry itself is saved; send the admin to the edit page to retry the upload.
        navigate(`/admin/registries/${saved.id}/edit`, { state: { notice: `Registry saved, but the certificate was not uploaded: ${err.message}` } })
        return
      }
    }
    navigate(`/admin/registries/${saved.id}`, { state: { notice: editing ? 'Registry updated.' : 'Registry created.' } })
  }

  if (loading) return <p className="status-line" role="status">Loading…</p>
  if (editing && !existing) return <p className="field-error" role="alert">{banner || 'Registry not found.'}</p>

  return (
    <>
      <div className="page-head">
        <h1 className="h2">{editing ? `Edit ${existing.registry_number}` : 'Add registry'}</h1>
        <Link to={editing ? `/admin/registries/${id}` : '/admin/registries'} className="btn btn-ghost">Cancel</Link>
      </div>
      {banner && <p className="notice error" role="alert">{banner}</p>}

      <form className="card admin-form" onSubmit={submit} noValidate>
        <fieldset>
          <legend>Registry access</legend>
          <div className="form-grid">
            <Field id="registry_number" label="Registry Number *" error={errors.registry_number}
              hint="Entered manually, e.g. HIP-2026-000401. Must be unique.">
              <input {...props('registry_number')} required autoComplete="off" />
            </Field>
            <Field id="registry_code" label="Registry Code *" error={errors.registry_code}
              hint="Shared privately with the customer. 4-40 letters, numbers or hyphens.">
              <input {...props('registry_code')} required autoComplete="off" />
            </Field>
          </div>
        </fieldset>

        <fieldset>
          <legend>Dedication</legend>
          <div className="form-grid">
            <Field id="dedicated_to" label="Dedicated To *" error={errors.dedicated_to}>
              <input {...props('dedicated_to')} required maxLength={120} />
            </Field>
            <Field id="dedicated_by" label="Dedicated By *" error={errors.dedicated_by}>
              <input {...props('dedicated_by')} required maxLength={120} />
            </Field>
            <Field id="dedication_date" label="Date of Dedication *" error={errors.dedication_date}>
              <input {...props('dedication_date')} type="date" required />
            </Field>
            <Field id="occasion" label="Occasion" error={errors.occasion}>
              <input {...props('occasion')} maxLength={80} placeholder="e.g. Anniversary" />
            </Field>
          </div>
          <Field id="dedication_message" label="Dedication Message" error={errors.dedication_message}
            hint="Shown on the customer's registry page. Up to 2000 characters.">
            <textarea {...props('dedication_message')} rows={5} maxLength={2000} />
          </Field>
        </fieldset>

        <fieldset>
          <legend>Star details</legend>
          <div className="form-grid three">
            <Field id="star_catalogue" label="Star Catalogue" error={errors.star_catalogue}>
              <input {...props('star_catalogue')} maxLength={80} placeholder="e.g. HIP 101000" />
            </Field>
            <Field id="constellation" label="Constellation" error={errors.constellation}>
              <input {...props('constellation')} maxLength={80} />
            </Field>
            <Field id="distance" label="Distance" error={errors.distance}>
              <input {...props('distance')} maxLength={80} placeholder="e.g. 120 light years" />
            </Field>
          </div>
        </fieldset>

        <fieldset>
          <legend>Certificate &amp; status</legend>
          <div className="form-grid">
            <Field id="certificate" label={existing?.certificate?.available ? 'Replace certificate' : 'Certificate'}
              error={fileError} hint="PDF, PNG or JPG, up to 5 MB. Optional.">
              <input id="certificate" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                onChange={pickFile} aria-invalid={fileError ? true : undefined}
                aria-describedby={fileError ? 'certificate-error' : 'certificate-hint'} />
              {existing?.certificate?.available && (
                <p className="hint"><a href={api.admin.certificateUrl(existing.id)} target="_blank" rel="noopener noreferrer">Current certificate</a></p>
              )}
            </Field>
            <Field id="status" label="Status" error={errors.status}
              hint="Only active registries can be verified by customers.">
              <select {...props('status')}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </Field>
          </div>
        </fieldset>

        <div className="actions">
          <button className="btn btn-primary" disabled={busy || !!fileError}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Create registry'}
          </button>
        </div>
      </form>
    </>
  )
}
