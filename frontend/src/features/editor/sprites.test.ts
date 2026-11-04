import { expect, test } from 'vitest'
import type { Drawing } from '../../api/client'
import { sprites } from './sprites'

test('finds each tile on the sheet and places it in floor, walls, objects order', () => {
  const drawing: Drawing = {
    width: 2,
    height: 1,
    shift: 0,
    tile_size: 16,
    columns: 12,
    floor: [[48, 48]],
    walls: [[null, 25]],
    objects: [
      { kind: 'key', x: 0, y: 0, tile: 249 },
      { kind: 'statue', x: 1, y: 0, tile: null },
    ],
  }
  expect(sprites(drawing)).toEqual([
    { sx: 0, sy: 64, dx: 0, dy: 0 }, // 48 = row 4, column 0
    { sx: 0, sy: 64, dx: 16, dy: 0 },
    { sx: 16, sy: 32, dx: 16, dy: 0 }, // 25 = row 2, column 1
    { sx: 144, sy: 320, dx: 0, dy: 0 }, // 249 = row 20, column 9
  ])
})
