import { expect, test } from 'vitest'
import type { GameMap } from '../../api/client'
import {
  eraseObject,
  moveObject,
  objectAt,
  paintTile,
  placeObject,
} from './edit'

const map: GameMap = {
  width: 3,
  height: 3,
  tiles: [
    [1, 2, 1],
    [1, 0, 1],
    [1, 1, 1],
  ],
  objects: [{ kind: 'guard', x: 1, y: 1 }],
}

test('paints a tile without changing the old map', () => {
  const next = paintTile(map, 1, 0, 1)
  expect(next.tiles[0]).toEqual([1, 1, 1])
  expect(map.tiles[0]).toEqual([1, 2, 1])
  expect(paintTile(map, 1, 0, 2)).toBe(map)
})

test('places an object, replacing the one on the cell', () => {
  expect(placeObject(map, 1, 0, 'key').objects).toEqual([
    { kind: 'guard', x: 1, y: 1 },
    { kind: 'key', x: 1, y: 0 },
  ])
  expect(placeObject(map, 1, 1, 'chest').objects).toEqual([
    { kind: 'chest', x: 1, y: 1 },
  ])
  expect(placeObject(map, 1, 1, 'guard')).toBe(map)
})

test('erases the object on a cell', () => {
  expect(eraseObject(map, 1, 1).objects).toEqual([])
  expect(eraseObject(map, 0, 0)).toBe(map)
})

test('moves an object only to an empty cell', () => {
  const moved = moveObject(map, { x: 1, y: 1 }, 1, 0)
  expect(moved.objects).toEqual([{ kind: 'guard', x: 1, y: 0 }])
  expect(objectAt(moved, 1, 1)).toBe(-1)

  const two = placeObject(map, 1, 0, 'key')
  expect(moveObject(two, { x: 1, y: 1 }, 1, 0)).toBe(two)
  expect(moveObject(map, { x: 0, y: 0 }, 1, 0)).toBe(map)
})
