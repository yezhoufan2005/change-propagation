import { ReactNode } from 'react'
import '../styles/drawer.css'

interface DrawerProps {
  open: boolean
  side?: 'left' | 'right'
  onClose: () => void
  children: ReactNode
}

export function Drawer({ open, side = 'right', onClose, children }: DrawerProps) {
  return (
    <div className={`drawer-root${open ? ' is-open' : ''}`} aria-hidden={!open}>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className={`drawer drawer-${side}`}>{children}</aside>
    </div>
  )
}
