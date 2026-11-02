import { t } from '../../i18n'
import { formatPrice } from '../../utils/format'

interface Order {
  id: string
  no: string
  createdAt: string
  total: number
}

const fmt = (iso: string) =>
  new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\//g, '-')

export function OrderList({ orders }: { orders: Order[] }) {
  if (orders.length === 0) return <p>{t('orders.empty')}</p>
  return (
    <table className="order-list">
      <tbody>
        {orders.map(o => (
          <tr key={o.id}>
            <td>{o.no}</td>
            <td>{fmt(o.createdAt)}</td>
            <td>{formatPrice(o.total)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
