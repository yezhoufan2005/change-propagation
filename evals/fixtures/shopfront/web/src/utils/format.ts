export function formatPrice(cents: number): string {
  return '¥' + (cents / 100).toFixed(2)
}

// Order timestamps, e.g. 2026-03-05 09:07
export function formatTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => (n < 10 ? '0' + n : String(n))
  return d.getFullYear() + '-' + pad(d.getMonth()) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}
