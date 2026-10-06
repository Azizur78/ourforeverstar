const POINTS = [
  [60, 210], [130, 150], [215, 175], [290, 95], [380, 120], [455, 60], [330, 230], [250, 300], [150, 290],
]
const LINES = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [2, 6], [6, 7], [7, 8], [8, 1]]
const FEATURED = 3

/** Decorative constellation with one glowing featured star. */
export default function Constellation({ className = '' }) {
  return (
    <svg className={`constellation ${className}`} viewBox="0 0 520 360" role="img"
      aria-label="A constellation with one glowing star at its centre">
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#f6e6bd" stopOpacity="0.95" />
          <stop offset="35%" stopColor="#d9bb82" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#d9bb82" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="290" cy="95" r="110" fill="none" stroke="#d9bb82" strokeOpacity="0.12" />
      <circle cx="290" cy="95" r="70" fill="none" stroke="#d9bb82" strokeOpacity="0.18" strokeDasharray="2 6" />
      {LINES.map(([a, b], i) => (
        <line key={i} className="c-line" x1={POINTS[a][0]} y1={POINTS[a][1]} x2={POINTS[b][0]} y2={POINTS[b][1]}
          style={{ animationDelay: `${i * 0.18}s` }} />
      ))}
      {POINTS.map(([x, y], i) => (i === FEATURED ? null : (
        <circle key={i} className="c-dot" cx={x} cy={y} r={i % 3 === 0 ? 3.2 : 2.4}
          style={{ animationDelay: `${i * 0.4}s` }} />
      )))}
      <circle cx={POINTS[FEATURED][0]} cy={POINTS[FEATURED][1]} r="60" fill="url(#glow)" className="c-glow" />
      <path className="c-star" transform={`translate(${POINTS[FEATURED][0]} ${POINTS[FEATURED][1]})`}
        d="M0 -15 L3.6 -3.6 L15 0 L3.6 3.6 L0 15 L-3.6 3.6 L-15 0 L-3.6 -3.6Z" />
    </svg>
  )
}
