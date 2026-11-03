import {
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from 'react'
import type { GameMap, ObjectKind, Tile } from '../../api/client'
import {
  cellKey,
  eraseObject,
  indexObjects,
  moveObject,
  paintTile,
  placeObject,
} from './edit'

const CELL = 24

// Tile tools, and how each tile value is named and drawn.
const TILE_TOOLS = { floor: 0, wall: 1, door: 2 } as const
type TileTool = keyof typeof TILE_TOOLS
const TILE_NAMES: Record<Tile, TileTool> = { 0: 'floor', 1: 'wall', 2: 'door' }
const TILE_COLORS: Record<Tile, string> = {
  0: '#e8e2d0',
  1: '#4a4a4a',
  2: '#b5651d',
}

// Every object kind needs a marker; `satisfies` fails typecheck if a kind is missing.
const MARKERS = {
  player_spawn: { label: 'P', color: '#2f7de1' },
  guard: { label: 'G', color: '#d64545' },
  cover: { label: 'C', color: '#7a7a7a' },
  chest: { label: 'Ch', color: '#c9a227' },
  key: { label: 'K', color: '#9b59b6' },
  light: { label: 'L', color: '#f0a020' },
} satisfies Record<ObjectKind, { label: string; color: string }>
const KINDS = Object.keys(MARKERS) as ObjectKind[]

type Tool = 'select' | 'erase' | TileTool | ObjectKind
type Cell = { x: number; y: number }
type SetHover = (cell: Cell | null) => void

const isTileTool = (tool: Tool): tool is TileTool => tool in TILE_TOOLS

// Code names like player_spawn, shown as words.
const plain = (name: string) => name.replaceAll('_', ' ')

type Props = {
  map: GameMap
  onChange: (map: GameMap) => void
}

export default function MapEditor({ map, onChange }: Props) {
  const [tool, setTool] = useState<Tool>('select')
  const [selected, setSelected] = useState<Cell | null>(null)
  // The status line owns the hovered cell, so hovering redraws only that line, not the grid.
  const setHover = useRef<SetHover>(null)

  // Built once per map, so drawing doesn't scan every object for every cell.
  const objectIndex = useMemo(() => indexObjects(map), [map])
  const objectOn = (x: number, y: number) =>
    objectIndex.get(cellKey(x, y)) ?? -1

  function chooseTool(next: Tool) {
    setTool(next)
    setSelected(null)
  }

  function edit(next: GameMap) {
    if (next !== map) onChange(next)
  }

  // Select: click an object, then an empty cell to move it there.
  function select(x: number, y: number) {
    const here = objectOn(x, y) !== -1
    if (selected && !here) {
      edit(moveObject(map, selected, x, y))
      setSelected(null)
    } else if (here && !(selected?.x === x && selected.y === y)) {
      setSelected({ x, y })
    } else {
      setSelected(null)
    }
  }

  function click(x: number, y: number) {
    if (tool === 'select') select(x, y)
    else if (tool === 'erase') edit(eraseObject(map, x, y))
    else if (isTileTool(tool)) edit(paintTile(map, x, y, TILE_TOOLS[tool]))
    else edit(placeObject(map, x, y, tool))
  }

  function describe({ x, y }: Cell): string {
    const i = objectOn(x, y)
    const obj = i === -1 ? '' : ` · ${plain(map.objects[i].kind)}`
    return `(${x}, ${y}) · ${TILE_NAMES[map.tiles[y][x]]}${obj}`
  }

  const toolButton = (name: Tool, content: ReactNode, color?: string) => (
    <button
      key={name}
      type="button"
      aria-label={plain(name)}
      title={plain(name)}
      aria-pressed={tool === name}
      onClick={() => chooseTool(name)}
      style={{
        width: 32,
        height: 32,
        background: color,
        outline: tool === name ? '2px solid #2f7de1' : undefined,
      }}
    >
      {content}
    </button>
  )

  return (
    <div>
      <div
        role="toolbar"
        aria-label="Tools"
        style={{ display: 'flex', gap: 4 }}
      >
        {toolButton('select', '↖')}
        {toolButton('erase', '⌫')}
        {(Object.keys(TILE_TOOLS) as TileTool[]).map((name) =>
          toolButton(name, null, TILE_COLORS[TILE_TOOLS[name]]),
        )}
        {KINDS.map((kind) =>
          toolButton(kind, <Marker kind={kind} size={18} />),
        )}
      </div>
      <div
        role="grid"
        onMouseLeave={() => setHover.current?.(null)}
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${map.width}, ${CELL}px)`,
          marginTop: 8,
        }}
      >
        {map.tiles.flatMap((row, y) =>
          row.map((tile, x) => {
            const i = objectOn(x, y)
            const isSelected = selected?.x === x && selected.y === y
            return (
              <div
                key={`${x},${y}`}
                role="gridcell"
                aria-label={describe({ x, y })}
                aria-selected={isSelected}
                onClick={() => click(x, y)}
                onMouseEnter={() => setHover.current?.({ x, y })}
                style={{
                  width: CELL,
                  height: CELL,
                  display: 'grid',
                  placeItems: 'center',
                  background: TILE_COLORS[tile],
                  outline: isSelected ? '2px solid #2f7de1' : undefined,
                  outlineOffset: -2,
                }}
              >
                {i !== -1 && (
                  <Marker kind={map.objects[i].kind} size={CELL - 6} />
                )}
              </div>
            )
          }),
        )}
      </div>
      <StatusLine
        setHoverRef={setHover}
        describe={describe}
        size={`${map.width} × ${map.height}`}
      />
    </div>
  )
}

// The hovered cell's position and contents, and the map size.
function StatusLine({
  setHoverRef,
  describe,
  size,
}: {
  setHoverRef: Ref<SetHover>
  describe: (cell: Cell) => string
  size: string
}) {
  const [hover, setHover] = useState<Cell | null>(null)
  useImperativeHandle(setHoverRef, () => setHover, [])
  return (
    <p role="status" style={{ display: 'flex', gap: 16 }}>
      <span>{hover ? describe(hover) : 'Hover a cell'}</span>
      <span>{size}</span>
    </p>
  )
}

// A round marker with a short label. Kinds the editor doesn't know show as "?".
function Marker({ kind, size }: { kind: string; size: number }) {
  const marker = MARKERS[kind as ObjectKind] ?? { label: '?', color: '#000' }
  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: marker.color,
        color: '#fff',
        fontSize: size / 2,
        display: 'grid',
        placeItems: 'center',
        pointerEvents: 'none',
      }}
    >
      {marker.label}
    </span>
  )
}
