// Imperative layer carried over from the legacy (pre-React) checkout page.
export function showCouponLayer(coupons: { code: string; title: string }[], onPick?: (code: string) => void) {
  const mask = document.createElement('div')
  mask.className = 'coupon-layer-mask'
  mask.style.cssText = 'position:fixed;inset:0;z-index:1300;display:flex;align-items:flex-end;background:rgba(0,0,0,.5)'

  const panel = document.createElement('div')
  panel.className = 'coupon-layer'
  for (const c of coupons) {
    const item = document.createElement('button')
    item.textContent = c.title
    item.addEventListener('click', () => {
      onPick?.(c.code)
      mask.remove()
    })
    panel.appendChild(item)
  }

  mask.appendChild(panel)
  mask.addEventListener('click', e => {
    if (e.target === mask) mask.remove()
  })
  document.body.appendChild(mask)
  return () => mask.remove()
}
