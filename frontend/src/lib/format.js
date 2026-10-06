/** Format an ISO date (YYYY-MM-DD) without timezone shifting. */
export function formatDate(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return iso
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(y, m - 1, d),
  )
}

export function formatDateTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
