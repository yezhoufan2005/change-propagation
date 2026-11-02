export function fmtDate(input: Date | string): string {
  const d = typeof input === 'string' ? new Date(input) : input
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-')
}
