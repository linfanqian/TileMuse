// Map edits. Each returns a new map, or the same map when nothing changes.
import type { GameMap, ObjectKind, Tile } from '../../api/client'

export const cellKey = (x: number, y: number) => `${x},${y}`

// Object index by cellKey. The editor keeps at most one object per cell; if a map has more,
// the first one in the list wins everywhere.
export function indexObjects(map: GameMap): Map<string, number> {
  const index = new Map<string, number>()
  map.objects.forEach((o, i) => {
    if (!index.has(cellKey(o.x, o.y))) index.set(cellKey(o.x, o.y), i)
  })
  return index
}

// Index of the object on a cell, or -1.
export function objectAt(map: GameMap, x: number, y: number): number {
  return indexObjects(map).get(cellKey(x, y)) ?? -1
}

export function paintTile(
  map: GameMap,
  x: number,
  y: number,
  tile: Tile,
): GameMap {
  if (map.tiles[y][x] === tile) return map
  const tiles = map.tiles.map((row) => [...row])
  tiles[y][x] = tile
  return { ...map, tiles }
}

// Places an object, replacing any object already on the cell.
export function placeObject(
  map: GameMap,
  x: number,
  y: number,
  kind: ObjectKind,
): GameMap {
  const i = objectAt(map, x, y)
  if (i === -1) return { ...map, objects: [...map.objects, { kind, x, y }] }
  if (map.objects[i].kind === kind) return map
  return { ...map, objects: map.objects.with(i, { kind, x, y }) }
}

export function eraseObject(map: GameMap, x: number, y: number): GameMap {
  const i = objectAt(map, x, y)
  if (i === -1) return map
  return { ...map, objects: map.objects.toSpliced(i, 1) }
}

// Moves the object on one cell to an empty cell. Does nothing if the target is taken.
export function moveObject(
  map: GameMap,
  from: { x: number; y: number },
  x: number,
  y: number,
): GameMap {
  const i = objectAt(map, from.x, from.y)
  if (i === -1 || objectAt(map, x, y) !== -1) return map
  return { ...map, objects: map.objects.with(i, { ...map.objects[i], x, y }) }
}
