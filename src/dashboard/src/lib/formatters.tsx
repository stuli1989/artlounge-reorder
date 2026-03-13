/** Convert daily velocity to monthly string (e.g. 0.5 → "15.0") */
export const vel = (v: number) => (v * 30).toFixed(1)

/** Render days-to-stockout with color coding */
export function daysDisplay(d: number | null) {
  if (d === null) return <span className="text-gray-400">N/A</span>
  if (d === 0) return <span className="text-red-600 font-bold">OUT</span>
  if (d < 30) return <span className="text-red-600 font-medium">{d}d</span>
  if (d < 90) return <span className="text-amber-600">{d}d</span>
  return <span className="text-green-600">{d}d</span>
}

/** Return Tailwind color classes for days-to-stockout value */
export function daysColor(days: number | null) {
  if (days === null) return 'text-gray-400'
  if (days < 30) return 'text-red-600 font-medium'
  if (days < 90) return 'text-amber-600'
  return 'text-green-600'
}
