import type { DriverStatus } from '../data/warehouseData'
import { DRIVER_STATUS_COLOR } from '../data/warehouseData'

// Font Awesome-style "warehouse" glyph. Original viewBox is 640x512 with
// em-based width/height meant to scale with a parent font-size - since this
// gets rasterized standalone (via an <img> data URI, with no font-size
// context), the outer dimensions are fixed to real pixels instead, keeping
// the same 1.25:1 aspect ratio.
function buildWarehouseIconSvg(color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="77" viewBox="0 0 640 512">
  <path d="M0 0h640v512H0z" fill="none" />
  <path fill="${color}" d="M504 352H136.4c-4.4 0-8 3.6-8 8l-.1 48c0 4.4 3.6 8 8 8H504c4.4 0 8-3.6 8-8v-48c0-4.4-3.6-8-8-8m0 96H136.1c-4.4 0-8 3.6-8 8l-.1 48c0 4.4 3.6 8 8 8h368c4.4 0 8-3.6 8-8v-48c0-4.4-3.6-8-8-8m0-192H136.6c-4.4 0-8 3.6-8 8l-.1 48c0 4.4 3.6 8 8 8H504c4.4 0 8-3.6 8-8v-48c0-4.4-3.6-8-8-8m106.5-139L338.4 3.7a48.15 48.15 0 0 0-36.9 0L29.5 117C11.7 124.5 0 141.9 0 161.3V504c0 4.4 3.6 8 8 8h80c4.4 0 8-3.6 8-8V256c0-17.6 14.6-32 32.6-32h382.8c18 0 32.6 14.4 32.6 32v248c0 4.4 3.6 8 8 8h80c4.4 0 8-3.6 8-8V161.3c0-19.4-11.7-36.8-29.5-44.3" />
</svg>`
}

export function warehouseIconDataUri(status: DriverStatus): string {
  const svg = buildWarehouseIconSvg(DRIVER_STATUS_COLOR[status])
  return `data:image/svg+xml;base64,${btoa(svg)}`
}

const DRIVER_STATUSES: DriverStatus[] = ['surplus', 'balanced', 'shortage']

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

// Cached across callers (the main map and the dashboard mini-map both need
// these) so the icons are only decoded once per session.
let warehouseIconsPromise: Promise<Record<DriverStatus, HTMLImageElement>> | null = null
export function loadWarehouseIcons(): Promise<Record<DriverStatus, HTMLImageElement>> {
  if (!warehouseIconsPromise) {
    warehouseIconsPromise = Promise.all(DRIVER_STATUSES.map((s) => loadImage(warehouseIconDataUri(s)))).then(
      (images) => Object.fromEntries(DRIVER_STATUSES.map((s, i) => [s, images[i]])) as Record<DriverStatus, HTMLImageElement>,
    )
  }
  return warehouseIconsPromise
}
