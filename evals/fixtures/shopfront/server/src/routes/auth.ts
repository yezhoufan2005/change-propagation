import { Router } from 'express'
import { validatePasswordReset, validateRegistration } from '../validators/user'

export const authRouter = Router()

authRouter.post('/register', (req, res) => {
  const errors = validateRegistration(req.body)
  if (errors.length) return res.status(400).json({ errors })
  // Persistence is omitted in this demo.
  res.status(201).json({ id: 'u_' + Math.random().toString(36).slice(2, 8) })
})

authRouter.post('/password/reset', (req, res) => {
  const errors = validatePasswordReset(req.body)
  if (errors.length) return res.status(400).json({ errors })
  res.status(204).end()
})
