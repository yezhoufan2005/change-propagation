import express from 'express'
import { authRouter } from './routes/auth'
import { ordersRouter } from './routes/orders'

const app = express()
app.use(express.json())
app.use('/api', authRouter)
app.use('/api', ordersRouter)

app.listen(3000, () => console.log('shopfront api on :3000'))
