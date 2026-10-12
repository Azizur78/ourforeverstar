import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import RegistryFields, { CERT_ACCEPT, DOC_LABELS, EMPTY_REGISTRY, Field, certificateError } from './RegistryFields'
import { MESSAGES, normalizeNumber, validateBatch, validateRecord } from './registryValidation'

let keySeed = 0
const newRecord = () => ({ key: ++keySeed, values: { ...EMPTY_REGISTRY }, file: null, doc: null })
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
const isDirty = (records) => records.some((r) => r.file || r.doc || Object.entries(r.values).some(([k, v]) => v !== EMPTY_REGISTRY[k]))

/**
 * Add several registry records, then save them all in one request. Each record is its own card with its own
 * field values, errors and certificate file, so nothing can leak from one record into another.
 */
export default function RegistryBatchForm() {
  const navigate = useNavigate()
  const [records, setRecords] = useState(() => [newRecord()])
  const [errors, setErrors] = useState({})       // {recordKey: {field: message}}
  const [fileErrors, setFileErrors] = useState({}) // {recordKey: message} for the certificate
  const [docErrors, setDocErrors] = useState({})   // {recordKey: message} for the registry document
  const [banner, setBanner] = useState('')
  const [busy, setBusy] = useState(false)
  const savingRef = useRef(false)                 // blocks a second submit even before React re-renders
  const cardRefs = useRef(new Map())
  const [focusTarget, setFocusTarget] = useState(null)

  // Warn before a refresh/close would throw away entered records.
  useEffect(() => {
    const warn = (e) => { if (isDirty(records) && !savingRef.current) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [records])

  // Move focus/scroll to a newly added card or to the first card with a problem.
  useEffect(() => {
    if (!focusTarget) return
    const card = cardRefs.current.get(focusTarget.key)
    if (card) {
      const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
      card.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' })
      const target = focusTarget.field ? card.querySelector(`[id$="-${focusTarget.field}"]`) : null
      ;(target || card.querySelector('input'))?.focus({ preventScroll: true })
    }
    setFocusTarget(null)
  }, [focusTarget])

  const clearError = (key, field) => setErrors((prev) => {
    if (!prev[key]?.[field]) return prev
    const { [field]: _removed, ...rest } = prev[key]
    return { ...prev, [key]: rest }
  })

  const setValue = (key, name, value) => {
    setRecords((rs) => rs.map((r) => (r.key === key ? { ...r, values: { ...r.values, [name]: value } } : r)))
    clearError(key, name)
  }

  const setFile = (key, file) => {
    setRecords((rs) => rs.map((r) => (r.key === key ? { ...r, file } : r)))
    setFileErrors((prev) => ({ ...prev, [key]: certificateError(file) }))
  }

  const setDoc = (key, doc) => {
    setRecords((rs) => rs.map((r) => (r.key === key ? { ...r, doc } : r)))
    setDocErrors((prev) => ({ ...prev, [key]: certificateError(doc) }))
  }

  function addRecord() {
    const record = newRecord()
    setRecords((rs) => [...rs, record])
    setFocusTarget({ key: record.key })
  }

  function removeRecord(key) {
    if (records.length < 2) return
    const index = records.findIndex((r) => r.key === key)
    const neighbour = records[index === 0 ? 1 : index - 1]
    setRecords((rs) => rs.filter((r) => r.key !== key))
    setErrors(({ [key]: _e, ...rest }) => rest)
    setFileErrors(({ [key]: _f, ...rest }) => rest)
    setDocErrors(({ [key]: _d, ...rest }) => rest)
    cardRefs.current.delete(key)
    setFocusTarget({ key: neighbour.key })
  }

  // Early feedback when leaving the Registry Number field: format, duplicate in this batch, or already in the database.
  async function checkNumber(key) {
    const record = records.find((r) => r.key === key)
    const number = normalizeNumber(record.values.registry_number)
    if (!number) return
    let message = validateRecord(record.values).registry_number
    if (!message && records.some((r) => r.key !== key && normalizeNumber(r.values.registry_number) === number)) {
      message = MESSAGES.duplicateInBatch
    }
    if (!message) {
      try {
        const { items } = await api.admin.list({ q: number, page_size: 5 })
        if (items.some((i) => i.registry_number.toUpperCase() === number)) message = MESSAGES.alreadyExists
      } catch { /* the server re-checks on save */ }
    }
    if (message) setErrors((prev) => ({ ...prev, [key]: { ...prev[key], registry_number: message } }))
  }

  const showProblems = useCallback((nextErrors, nextFileErrors, nextDocErrors, message) => {
    const keys = records.map((r) => r.key)
    const first = keys.find((k) => nextErrors[k] || nextFileErrors[k] || nextDocErrors[k])
    setBanner(message)
    if (first !== undefined) {
      const field = Object.keys(nextErrors[first] || {})[0]
        || (nextFileErrors[first] ? 'certificate' : nextDocErrors[first] ? 'registry_document' : null)
      setFocusTarget({ key: first, field })
    }
  }, [records])

  async function saveAll(e) {
    e.preventDefault()
    if (savingRef.current) return
    setBanner('')

    const local = validateBatch(records)
    const localFiles = Object.fromEntries(records.map((r) => [r.key, certificateError(r.file)]).filter(([, m]) => m))
    const localDocs = Object.fromEntries(records.map((r) => [r.key, certificateError(r.doc)]).filter(([, m]) => m))
    setErrors(local)
    setFileErrors(localFiles)
    setDocErrors(localDocs)
    const bad = new Set([...Object.keys(local), ...Object.keys(localFiles), ...Object.keys(localDocs)]).size
    if (bad) {
      showProblems(local, localFiles, localDocs, `${plural(bad, 'record')} need${bad === 1 ? 's' : ''} attention. Please review the highlighted fields.`)
      return
    }

    savingRef.current = true
    setBusy(true)
    try {
      const certificates = records.map((r, index) => ({ index, file: r.file })).filter((c) => c.file)
      const documents = records.map((r, index) => ({ index, file: r.doc })).filter((c) => c.file)
      const result = await api.admin.createBatch(records.map((r) => r.values), certificates, documents)
      navigate('/admin/registries', { state: { notice: `${plural(result.count, 'registry record')} added successfully.` } })
    } catch (err) {
      if (err.status === 401) return navigate('/admin/login', { replace: true })
      const serverErrors = {}
      const serverFileErrors = {}
      const serverDocErrors = {}
      for (const item of err.fieldErrors) {
        const record = records[item.index]
        if (!record) continue
        if (item.field === 'certificate') serverFileErrors[record.key] = item.message
        else if (item.field === 'registry_document') serverDocErrors[record.key] = item.message
        else serverErrors[record.key] = { ...serverErrors[record.key], [item.field]: item.message }
      }
      setErrors(serverErrors)
      setFileErrors(serverFileErrors)
      setDocErrors(serverDocErrors)
      const flagged = Object.keys(serverErrors).length + Object.keys(serverFileErrors).length + Object.keys(serverDocErrors).length
      showProblems(serverErrors, serverFileErrors, serverDocErrors,
        flagged ? 'Some records could not be saved. Please review the highlighted fields. Nothing was saved.' : err.message)
      savingRef.current = false
      setBusy(false)
    }
  }

  function cancel(e) {
    if (isDirty(records) && !window.confirm('Discard the records you have entered?')) e.preventDefault()
  }

  return (
    <form onSubmit={saveAll} noValidate className="batch">
      <div className="page-head">
        <h1 className="h2">Add Registry Records</h1>
        <Link to="/admin/registries" className="btn btn-ghost" onClick={cancel}>Cancel</Link>
      </div>
      <p className="muted batch-intro">
        Add as many records as you need, review them, then save them all at once. Nothing is saved until you choose
        <strong> Save All Records</strong>, and if any record has a problem none of them are saved.
      </p>

      {banner && <p className="notice error" role="alert">{banner}</p>}

      {records.map((record, position) => {
        const recordErrors = errors[record.key] || {}
        const certError = fileErrors[record.key]
        const docError = docErrors[record.key]
        const needsAttention = Object.keys(recordErrors).length > 0 || Boolean(certError) || Boolean(docError)
        const prefix = `r${record.key}-`
        return (
          <section key={record.key} className={`card record-card ${needsAttention ? 'has-errors' : ''}`}
            aria-labelledby={`${prefix}title`} tabIndex={-1}
            ref={(el) => (el ? cardRefs.current.set(record.key, el) : cardRefs.current.delete(record.key))}>
            <header className="record-head">
              <h2 id={`${prefix}title`} className="h3">Record {position + 1}</h2>
              {needsAttention && <span className="badge inactive">Needs attention</span>}
              {records.length > 1 && (
                <button type="button" className="btn btn-ghost btn-sm record-remove" onClick={() => removeRecord(record.key)}
                  disabled={busy} aria-label={`Remove record ${position + 1}`}>Remove</button>
              )}
            </header>
            <RegistryFields
              idPrefix={prefix}
              values={record.values}
              errors={recordErrors}
              onChange={(name, value) => setValue(record.key, name, value)}
              onBlurNumber={() => checkNumber(record.key)}
              certificate={(
                <Field id={`${prefix}certificate`} label={DOC_LABELS.certificate} error={certError}
                  hint="PDF only, up to 5 MB. Optional. Applies to this record only.">
                  <input id={`${prefix}certificate`} type="file" accept={CERT_ACCEPT}
                    onChange={(e) => setFile(record.key, e.target.files?.[0] || null)}
                    aria-invalid={certError ? true : undefined}
                    aria-describedby={certError ? `${prefix}certificate-error` : `${prefix}certificate-hint`} />
                </Field>
              )}
              registryDocument={(
                <Field id={`${prefix}registry_document`} label={DOC_LABELS.registry_document} error={docError}
                  hint="PDF only, up to 5 MB. Optional. Applies to this record only.">
                  <input id={`${prefix}registry_document`} type="file" accept={CERT_ACCEPT}
                    onChange={(e) => setDoc(record.key, e.target.files?.[0] || null)}
                    aria-invalid={docError ? true : undefined}
                    aria-describedby={docError ? `${prefix}registry_document-error` : `${prefix}registry_document-hint`} />
                </Field>
              )}
            />
          </section>
        )
      })}

      <div className="batch-bar">
        <span className="batch-count" aria-live="polite">{plural(records.length, 'record')}</span>
        <button type="button" className="btn btn-ghost" onClick={addRecord} disabled={busy}>+ New Registry</button>
        <button type="submit" className="btn btn-primary" disabled={busy} aria-busy={busy}>
          {busy ? 'Saving…' : 'Save All Records'}
        </button>
      </div>
    </form>
  )
}
