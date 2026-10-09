export const EMPTY_REGISTRY = {
  registry_number: '', registry_code: '', dedicated_to: '', dedicated_by: '', dedication_date: '',
  occasion: '', star_catalogue: '', constellation: '', distance: '', dedication_message: '', status: 'active',
}

export const CERT_ACCEPT = '.pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg'
const CERT_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg']
const CERT_MAX_BYTES = 5 * 1024 * 1024

/** Same rules the server applies to certificate uploads; the server remains the authority. */
export function certificateError(file) {
  if (!file) return ''
  const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : ''
  if (!CERT_EXTENSIONS.includes(ext)) return 'Unsupported file type. Upload a PDF, PNG or JPG file.'
  if (file.size > CERT_MAX_BYTES) return 'File is too large. Maximum size is 5 MB.'
  return ''
}

export function Field({ id, label, error, hint, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && !error && <p className="hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="field-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  )
}

/**
 * The registry data entry fields, shared by the multi-record Add form and the Edit form.
 * idPrefix keeps element ids unique when several records are on one page.
 * `certificate` and `registryDocument` are the per-form file controls, rendered next to Status.
 */
export default function RegistryFields({ idPrefix = '', values, errors = {}, onChange, onBlurNumber, certificate, registryDocument }) {
  const props = (name) => ({
    id: idPrefix + name,
    value: values[name],
    onChange: (e) => onChange(name, e.target.value),
    'aria-invalid': errors[name] ? true : undefined,
    'aria-describedby': errors[name] ? `${idPrefix}${name}-error` : undefined,
  })
  const field = (name, label, extra = {}) => (
    <Field id={idPrefix + name} label={label} error={errors[name]} hint={extra.hint}>{extra.control}</Field>
  )

  return (
    <>
      <fieldset>
        <legend>Registry access</legend>
        <div className="form-grid">
          {field('registry_number', 'Registry Number *', {
            hint: 'Entered manually, e.g. HIP-2026-000401. Must be unique.',
            control: <input {...props('registry_number')} onBlur={onBlurNumber} required autoComplete="off"
              autoCapitalize="characters" spellCheck="false" />,
          })}
          {field('registry_code', 'Registry Code *', {
            hint: 'Shared privately with the customer. 4-40 letters, numbers or hyphens.',
            control: <input {...props('registry_code')} required autoComplete="off" spellCheck="false" />,
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend>Dedication</legend>
        <div className="form-grid">
          {field('dedicated_to', 'Dedicated To *', {
            hint: 'For a couple, enter both names, e.g. Person A and Person B.',
            control: <input {...props('dedicated_to')} required maxLength={120} />,
          })}
          {field('dedicated_by', 'Dedicated By *', {
            hint: 'One or more names, e.g. Person C and Person D. Shown beneath the heading.',
            control: <input {...props('dedicated_by')} required maxLength={120} />,
          })}
          {field('dedication_date', 'Date of Dedication *', { control: <input {...props('dedication_date')} type="date" required /> })}
          {field('occasion', 'Occasion', { control: <input {...props('occasion')} maxLength={80} placeholder="e.g. Anniversary" /> })}
        </div>
        {field('dedication_message', 'Dedication Message', {
          hint: "Shown on the customer's registry page. Up to 2000 characters.",
          control: <textarea {...props('dedication_message')} rows={4} maxLength={2000} />,
        })}
      </fieldset>

      <fieldset>
        <legend>Star details</legend>
        <div className="form-grid three">
          {field('star_catalogue', 'Star Catalogue', { control: <input {...props('star_catalogue')} maxLength={80} placeholder="e.g. HIP 101000" /> })}
          {field('constellation', 'Constellation', { control: <input {...props('constellation')} maxLength={80} /> })}
          {field('distance', 'Distance', { control: <input {...props('distance')} maxLength={80} placeholder="e.g. 120 light years" /> })}
        </div>
      </fieldset>

      <fieldset>
        <legend>Certificate, registry &amp; status</legend>
        <div className="form-grid three">
          {certificate}
          {registryDocument}
          {field('status', 'Status', {
            hint: 'Only active registries can be verified by customers.',
            control: (
              <select {...props('status')}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            ),
          })}
        </div>
      </fieldset>
    </>
  )
}
