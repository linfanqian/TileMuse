// Where each tile of a drawing comes from on the sheet, and where it goes, in sheet pixels.
import type { Drawing } from '../../api/client'

export type Sprite = { sx: number; sy: number; dx: number; dy: number }

// Floor first, then walls, then objects, so later layers draw on top.
export function sprites(drawing: Drawing): Sprite[] {
  const { tile_size: size, columns } = drawing
  const at = (tile: number, x: number, y: number): Sprite => ({
    sx: (tile % columns) * size,
    sy: Math.floor(tile / columns) * size,
    dx: x * size,
    dy: y * size,
  })
  const layer = (rows: (number | null)[][]) =>
    rows.flatMap((row, y) =>
      row.flatMap((tile, x) => (tile === null ? [] : [at(tile, x, y)])),
    )
  return [
    ...layer(drawing.floor),
    ...layer(drawing.walls),
    ...drawing.objects.flatMap((o) =>
      o.tile === null ? [] : [at(o.tile, o.x, o.y)],
    ),
  ]
}
