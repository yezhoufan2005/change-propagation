import { createPortal } from 'react-dom'
import { Button } from './Button'

interface ConfirmDialogProps {
  visible: boolean
  message: string
  confirmText?: string
  onConfirm: () => void
  onCancel: () => void
}

// Kept separate from Modal: needs a higher z-index so it can sit on top of an open Modal.
export function ConfirmDialog({ visible, message, confirmText = '确定', onConfirm, onCancel }: ConfirmDialogProps) {
  if (!visible) return null
  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 1100, display: 'grid', placeItems: 'center', background: 'rgba(0, 0, 0, 0.4)' }}>
      <div role="alertdialog" style={{ width: 320, padding: 20, borderRadius: 6, background: '#fff' }}>
        <p>{message}</p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="ghost" onClick={onCancel}>取消</Button>
          <Button onClick={onConfirm}>{confirmText}</Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
