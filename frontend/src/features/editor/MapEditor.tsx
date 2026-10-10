import type { GameMap, Tile } from '../../api/client'

const CELL = 24
const COLORS: Record<Tile, string> = {
  0: '#e8e2d0',
  1: '#4a4a4a',
  2: '#b5651d',
}
const TILE_COUNT = Object.keys(COLORS).length

type Props = {
  map: GameMap
  onChange: (map: GameMap) => void
}

export default function MapEditor({ map, onChange }: Props) {
  // Placeholder editing: clicking a cell cycles its tile.
  function cycle(x: number, y: number) {
    const tiles = map.tiles.map((row) => [...row])
    tiles[y][x] = ((tiles[y][x] + 1) % TILE_COUNT) as Tile
    onChange({ ...map, tiles })
  }

  return (
    <div
      role="grid"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${map.width}, ${CELL}px)`,
      }}
    >
      {map.tiles.flatMap((row, y) =>
        row.map((tile, x) => (
          <div
            key={`${x},${y}`}
            role="gridcell"
            onClick={() => cycle(x, y)}
            style={{ width: CELL, height: CELL, background: COLORS[tile] }}
          />
        )),
      )}
    </div>
  )
}
