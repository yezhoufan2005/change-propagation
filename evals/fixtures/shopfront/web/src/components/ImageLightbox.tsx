import { useState } from 'react'
import { createPortal } from 'react-dom'
import '../styles/lightbox.css'

interface ImageLightboxProps {
  images: string[]
  startIndex?: number
  onClose: () => void
}

export function ImageLightbox({ images, startIndex = 0, onClose }: ImageLightboxProps) {
  const [index, setIndex] = useState(startIndex)
  const next = () => setIndex(i => (i + 1) % images.length)

  return createPortal(
    <div className="lightbox-overlay" onClick={onClose}>
      <img
        className="lightbox-img"
        src={images[index]}
        alt=""
        onClick={e => {
          e.stopPropagation()
          next()
        }}
      />
      <span className="lightbox-counter">
        {index + 1} / {images.length}
      </span>
    </div>,
    document.body,
  )
}
