import { Router } from 'express'
import { groupOrdersByDay } from '../services/report'
import { fmtDate } from '../utils/time'

const orders = [
  { id: 'o1', no: 'SF20260301001', createdAt: '2026-03-01T10:12:00+08:00', total: 12900 },
  { id: 'o2', no: 'SF20260302001', createdAt: '2026-03-02T00:30:00+08:00', total: 5600 },
]

export const ordersRouter = Router()

ordersRouter.get('/orders', (_req, res) => {
  res.json(orders.map(o => ({ ...o, date: fmtDate(o.createdAt) })))
})

ordersRouter.get('/reports/daily', (_req, res) => {
  res.json(groupOrdersByDay(orders))
})
