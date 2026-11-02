interface OrderRow {
  createdAt: string
  total: number
}

// Day key for the daily sales report, e.g. "2026-03-01".
function toDay(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function groupOrdersByDay(orders: OrderRow[]): Record<string, number> {
  const totals: Record<string, number> = {}
  for (const o of orders) {
    const key = toDay(new Date(o.createdAt))
    totals[key] = (totals[key] ?? 0) + o.total
  }
  return totals
}
