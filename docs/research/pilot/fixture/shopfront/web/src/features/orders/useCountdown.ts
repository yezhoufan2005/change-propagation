import { useEffect, useState } from 'react'

// Seconds left until an unpaid order is cancelled.
export function useCountdown(deadline: number): number {
  const [left, setLeft] = useState(() => Math.max(0, Math.round((deadline - Date.now()) / 1000)))
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, Math.round((deadline - Date.now()) / 1000))), 1000)
    return () => clearInterval(id)
  }, [deadline])
  return left
}
