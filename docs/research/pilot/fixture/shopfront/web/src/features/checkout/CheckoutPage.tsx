import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '../../components/Button'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { formatPrice } from '../../utils/format'
import { showCouponLayer } from './couponLayer'

interface Address {
  id: string
  text: string
}

interface CheckoutPageProps {
  total: number
  addresses: Address[]
  coupons: { code: string; title: string }[]
  onSubmit: (addressId: string) => void
}

export function CheckoutPage({ total, addresses, coupons, onSubmit }: CheckoutPageProps) {
  const [addressId, setAddressId] = useState(addresses[0]?.id ?? '')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const current = addresses.find(a => a.id === addressId)

  return (
    <main className="checkout">
      <h1>结算</h1>
      <p>收货地址：{current?.text ?? '未选择'}</p>
      <Button variant="ghost" onClick={() => setPickerOpen(true)}>更换地址</Button>
      <Button variant="ghost" onClick={() => showCouponLayer(coupons)}>使用优惠券</Button>
      <p className="checkout-total">应付：{formatPrice(total)}</p>
      <Button onClick={() => setConfirming(true)}>提交订单</Button>

      {pickerOpen &&
        createPortal(
          <div
            className="address-picker-mask"
            style={{ position: 'fixed', inset: 0, zIndex: 950, background: 'rgba(0, 0, 0, 0.4)' }}
            onClick={() => setPickerOpen(false)}
          >
            <ul className="address-picker" onClick={e => e.stopPropagation()}>
              {addresses.map(a => (
                <li
                  key={a.id}
                  onClick={() => {
                    setAddressId(a.id)
                    setPickerOpen(false)
                  }}
                >
                  {a.text}
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}

      <ConfirmDialog visible={confirming} message="确认提交订单？" onConfirm={() => onSubmit(addressId)} onCancel={() => setConfirming(false)} />
    </main>
  )
}
