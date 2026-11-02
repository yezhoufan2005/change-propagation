import { useState } from 'react'
import { ImageLightbox } from './ImageLightbox'
import { formatPrice } from '../utils/format'

export interface Product {
  id: string
  name: string
  price: number
  images: string[]
}

export function ProductCard({ product }: { product: Product }) {
  const [preview, setPreview] = useState(false)
  return (
    <article className="product-card">
      <img src={product.images[0]} alt={product.name} onClick={() => setPreview(true)} />
      <h4>{product.name}</h4>
      <span className="price">{formatPrice(product.price)}</span>
      {preview && <ImageLightbox images={product.images} onClose={() => setPreview(false)} />}
    </article>
  )
}
