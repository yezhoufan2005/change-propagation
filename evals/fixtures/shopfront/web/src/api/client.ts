async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  register: (email: string, password: string) => post<{ id: string }>('/register', { email, password }),
  resetPassword: (token: string, password: string) => post<void>('/password/reset', { token, password }),
  listOrders: () => fetch('/api/orders').then(r => r.json()),
}
