import { useMemo } from 'react'

// Deterministic pseudo-random so the sky is stable between renders.
function rng(seed) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function layer(seed, count) {
  const rand = rng(seed)
  return Array.from({ length: count }, () => `${(rand() * 100).toFixed(2)}vw ${(rand() * 100).toFixed(2)}vh 0 0 currentColor`).join(',')
}

/** Fixed, lightweight star backdrop: three box-shadow layers, no canvas and no libraries. */
export default function StarField() {
  const layers = useMemo(() => [layer(7, 70), layer(21, 45), layer(43, 22)], [])
  return (
    <div className="starfield" aria-hidden="true">
      {layers.map((shadow, i) => (
        <span key={i} className={`stars stars-${i + 1}`} style={{ boxShadow: shadow }} />
      ))}
    </div>
  )
}
