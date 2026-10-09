// Presentation helpers for the registry. They only change how stored text is DISPLAYED; stored values are never altered.

/**
 * "Person A and Person B" -> ["Person A", "Person B"]. Splits on the word "and" or "&" only (never on commas,
 * so "Smith, Jr." stays intact). Anything that is not a clean 2-4 name list is returned as a single name.
 */
export function splitNames(text) {
  const clean = String(text ?? '').replace(/\s+/g, ' ').trim()
  const parts = clean.split(/\s+(?:and|&)\s+/i).map((p) => p.trim()).filter(Boolean)
  return parts.length >= 2 && parts.length <= 4 ? parts : clean ? [clean] : []
}

/** Type-size tier so long names or long couples stay elegant instead of overflowing. */
export function nameScale(names) {
  const longest = Math.max(0, ...names.map((n) => n.length))
  const total = names.join(' ').length
  if (longest > 38 || total > 90) return 'xlong'
  if (longest > 24 || total > 56) return 'long'
  return 'regular'
}

/** Official catalogue references read as capitals: "hip 1001" -> "HIP 1001". Other text is left untouched. */
export function formatCatalogue(value) {
  if (!value) return value
  return value.replace(/^(\s*)([A-Za-z]{2,4})(?=[\s-]?\d)/, (_, space, code) => space + code.toUpperCase())
}
