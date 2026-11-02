import { ReactNode, useEffect } from 'react'
import { createPortal } from 'react-dom'
import './modal.css'

interface ModalProps {
  open: boolean
  title?: string
  onClose: () => void
  children: ReactNode
}

export function Modal({ open, title, onClose, children }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-panel" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}>
        {title && <h3 className="modal-title">{title}</h3>}
        {children}
      </div>
    </div>,
    document.body,
  )
}
