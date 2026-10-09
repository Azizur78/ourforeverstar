import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import RegistryFields, { CERT_ACCEPT, EMPTY_REGISTRY, Field, certificateError } from './RegistryFields'

/** Edit one existing registry. New registries are added with RegistryBatchForm. */
export default function RegistryForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_REGISTRY)
  const [existing, setExisting] = useState(null)
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState('')
  const [doc, setDoc] = useState(null)
  const [docError, setDocError] = useState('')
  const [errors, setErrors] = useState({})
  const [banner, setBanner] = useState(useLocation().state?.notice || '')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.admin.get(id)
      .then((r) => {
        setExisting(r)
        setForm(Object.fromEntries(Object.keys(EMPTY_REGISTRY).map((k) => [k, r[k] ?? ''])))
      })
      .catch((e) => setBanner(e.status === 404 ? 'Registry not found.' : e.message))
      .finally(() => setLoading(false))
  }, [id])

  function pickFile(e) {
    const f = e.target.files?.[0] || null
    const problem = certificateError(f)
    setFileError(problem)
    setFile(problem ? null : f)
  }

  function pickDoc(e) {
    const f = e.target.files?.[0] || null
    const problem = certificateError(f)
    setDocError(problem)
    setDoc(problem ? null : f)
  }

  async function submit(e) {
    e.preventDefault()
    setBanner('')
    setErrors({})
    setBusy(true)
    let saved
    try {
      saved = await api.admin.update(id, form)
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

    for (const [upload, send, what] of [
      [file, api.admin.uploadCertificate, 'certificate'],
      [doc, api.admin.uploadRegistryDocument, 'registry document'],
    ]) {
      if (!upload) continue
      try {
        await send(saved.id, upload)
      } catch (err) {
        // The registry itself is saved; stay here so the upload can be retried.
        setBanner(`Registry saved, but the ${what} was not uploaded: ${err.message}`)
        setBusy(false)
        return
      }
    }
    navigate(`/admin/registries/${saved.id}`, { state: { notice: 'Registry updated.' } })
  }

  if (loading) return <p className="status-line" role="status">Loading…</p>
  if (!existing) return <p className="field-error" role="alert">{banner || 'Registry not found.'}</p>

  return (
    <>
      <div className="page-head">
        <h1 className="h2">Edit {existing.registry_number}</h1>
        <Link to={`/admin/registries/${id}`} className="btn btn-ghost">Cancel</Link>
      </div>
      {banner && <p className="notice error" role="alert">{banner}</p>}

      <form className="card admin-form" onSubmit={submit} noValidate>
        <RegistryFields
          values={form}
          errors={errors}
          onChange={(name, value) => setForm((f) => ({ ...f, [name]: value }))}
          certificate={(
            <Field id="certificate" label={existing.certificate?.available ? 'Replace certificate' : 'Certificate'}
              error={fileError} hint="PDF, PNG or JPG, up to 5 MB. Optional.">
              <input id="certificate" type="file" accept={CERT_ACCEPT} onChange={pickFile}
                aria-invalid={fileError ? true : undefined}
                aria-describedby={fileError ? 'certificate-error' : 'certificate-hint'} />
              {existing.certificate?.available && (
                <p className="hint"><a href={api.admin.certificateUrl(existing.id)} target="_blank" rel="noopener noreferrer">Current certificate</a></p>
              )}
            </Field>
          )}
          registryDocument={(
            <Field id="registry_document" label={existing.registry_document?.available ? 'Replace registry document' : 'Registry document'}
              error={docError} hint="PDF, PNG or JPG, up to 5 MB. Optional.">
              <input id="registry_document" type="file" accept={CERT_ACCEPT} onChange={pickDoc}
                aria-invalid={docError ? true : undefined}
                aria-describedby={docError ? 'registry_document-error' : 'registry_document-hint'} />
              {existing.registry_document?.available && (
                <p className="hint"><a href={api.admin.registryDocumentUrl(existing.id)} target="_blank" rel="noopener noreferrer">Current registry document</a></p>
              )}
            </Field>
          )}
        />
        <div className="actions">
          <button className="btn btn-primary" disabled={busy || !!fileError || !!docError}>{busy ? 'Saving…' : 'Save changes'}</button>
        </div>
      </form>
    </>
  )
}
