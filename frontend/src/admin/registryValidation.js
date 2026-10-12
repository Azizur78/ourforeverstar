// Client-side mirror of the backend rules (backend/app/schemas/registry.py). It only gives fast feedback;
// the server validates every record again and is the authority.
const NUMBER_RE = /^[A-Z0-9][A-Z0-9\-_/]{2,39}$/
const CODE_RE = /^[A-Za-z0-9][A-Za-z0-9\-]{3,39}$/
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+([.][A-Za-z0-9-]+)+$/

export const MESSAGES = {
  duplicateInBatch: 'Duplicate registry number in this batch.',
  alreadyExists: 'Registry number already exists.',
}

const REQUIRED = [
  ['registry_number', 'Registry Number'],
  ['registry_code', 'Registry Code'],
  ['dedicated_to', 'Dedicated To'],
  ['dedicated_by', 'Dedicated By'],
  ['dedication_date', 'Date of Dedication'],
]
const MAX = { dedicated_to: 120, dedicated_by: 120, occasion: 80, star_catalogue: 80, constellation: 80, distance: 80, dedication_message: 2000 }

export const normalizeNumber = (value) => value.trim().toUpperCase()

/** Format/required errors for one record: {field: message}. */
export function validateRecord(values) {
  const errors = {}
  for (const [field, label] of REQUIRED) {
    if (!String(values[field] ?? '').trim()) errors[field] = `${label} is required.`
  }
  const number = normalizeNumber(values.registry_number)
  if (number && !NUMBER_RE.test(number)) {
    errors.registry_number = 'Use 3-40 letters, numbers, hyphens, underscores or slashes (e.g. HIP-2026-000401).'
  }
  const code = values.registry_code.trim()
  if (code && !CODE_RE.test(code)) errors.registry_code = 'Use 4-40 letters, numbers or hyphens.'
  const email = String(values.contact_email ?? '').trim()
  if (email && (email.length > 254 || !EMAIL_RE.test(email))) errors.contact_email = 'Enter a valid email address.'
  for (const [field, max] of Object.entries(MAX)) {
    if (String(values[field] ?? '').trim().length > max) errors[field] = `Use at most ${max} characters.`
  }
  return errors
}

/** Keys of records whose Registry Number is used by more than one record in the batch (case-insensitive). */
export function duplicateKeys(records) {
  const byNumber = new Map()
  for (const r of records) {
    const number = normalizeNumber(r.values.registry_number)
    if (number) byNumber.set(number, [...(byNumber.get(number) || []), r.key])
  }
  return new Set([...byNumber.values()].filter((keys) => keys.length > 1).flat())
}

/** Full pre-submit check: {recordKey: {field: message}} containing only records with problems. */
export function validateBatch(records) {
  const dupes = duplicateKeys(records)
  const result = {}
  for (const r of records) {
    const errors = validateRecord(r.values)
    if (dupes.has(r.key) && !errors.registry_number) errors.registry_number = MESSAGES.duplicateInBatch
    if (Object.keys(errors).length) result[r.key] = errors
  }
  return result
}
