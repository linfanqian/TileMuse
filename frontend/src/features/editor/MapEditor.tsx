import {
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from 'react'
import {
  drawMap,
  TILESHEET_URL,
  type Drawing,
  type GameMap,
  type Kit,
  type ObjectKind,
  type Tile,
} from '../../api/client'
import {
  cellKey,
  eraseObject,
  indexObjects,
  moveObject,
  paintTile,
  placeObject,
} from './edit'
import { sprites } from './sprites'

// On-screen size of a cell: 16px tiles drawn at twice their size, so pixels stay sharp.
const CELL = 32

// Tile tools, and how each tile value is named. The colors draw the map until the kit's
// tiles arrive, or if they can't be loaded.
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
// A drawing and the map it was drawn for.
type Drawn = { map: GameMap; drawing: Drawing }
type SetHover = (cell: Cell | null) => void

const isTileTool = (tool: Tool): tool is TileTool => tool in TILE_TOOLS

// Code names like player_spawn, shown as words.
const plain = (name: string) => name.replaceAll('_', ' ')

type Props = {
  map: GameMap
  kit: Kit
  onChange: (map: GameMap) => void
}

export default function MapEditor({ map, kit, onChange }: Props) {
  const [tool, setTool] = useState<Tool>('select')
  const [selected, setSelected] = useState<Cell | null>(null)
  // The newest drawing from the backend. A failed request keeps the last one.
  const [drawn, setDrawn] = useState<Drawn | null>(null)
  // What the canvas shows right now, set by the canvas once it has painted. Null until then,
  // or if it can't paint, and then every cell is drawn in color.
  const [art, setArt] = useState<Drawn | null>(null)
  useEffect(() => {
    let current = true
    drawMap(kit, map).then(
      (drawing) => current && setDrawn({ map, drawing }),
      () => {},
    )
    return () => {
      current = false
    }
  }, [kit, map])
  const artIndex = useMemo(() => art && indexObjects(art.map), [art])

  // True when the canvas doesn't show this cell as the map has it: an edit not drawn yet, or
  // a door inside the room, which the kit draws as floor. Such cells are drawn in color.
  function needsColor(x: number, y: number): boolean {
    if (!art || !artIndex) return true
    const tile = map.tiles[y][x]
    const inside = x > 0 && y > 0 && x < map.width - 1 && y < map.height - 1
    if (tile === TILE_TOOLS.door && inside) return true
    const shownKind = art.map.objects[artIndex.get(cellKey(x, y)) ?? -1]?.kind
    const kind = map.objects[objectOn(x, y)]?.kind
    return art.map.tiles[y]?.[x] !== tile || shownKind !== kind
  }
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
        style={{
          position: 'relative',
          marginTop: 8,
          // A two-row top wall adds rows above the map, so the cells sit `shift` rows down.
          paddingTop: (art?.drawing.shift ?? 0) * CELL,
        }}
      >
        {drawn && <TileCanvas drawn={drawn} onPainted={setArt} />}
        <div
          role="grid"
          onMouseLeave={() => setHover.current?.(null)}
          style={{
            position: 'relative',
            display: 'grid',
            gridTemplateColumns: `repeat(${map.width}, ${CELL}px)`,
          }}
        >
          {map.tiles.flatMap((row, y) =>
            row.map((tile, x) => {
              const i = objectOn(x, y)
              const isSelected = selected?.x === x && selected.y === y
              const color = needsColor(x, y)
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
                    background: color ? TILE_COLORS[tile] : undefined,
                    outline: isSelected ? '2px solid #2f7de1' : undefined,
                    outlineOffset: -2,
                  }}
                >
                  {i !== -1 &&
                    // The kit has a tile for every kind the editor knows.
                    (color || !(map.objects[i].kind in MARKERS)) && (
                      <Marker kind={map.objects[i].kind} size={CELL - 6} />
                    )}
                </div>
              )
            }),
          )}
        </div>
      </div>
      <StatusLine
        setHoverRef={setHover}
        describe={describe}
        size={`${map.width} × ${map.height}`}
      />
    </div>
  )
}

// One load of the sheet, shared by every redraw, even while it is still loading. A failed
// load is dropped, so the next redraw tries again.
let sheet: Promise<HTMLImageElement> | null = null
function loadSheet(): Promise<HTMLImageElement> {
  sheet ??= new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('The tile sheet did not load.'))
    image.src = TILESHEET_URL
  }).catch((error: unknown) => {
    sheet = null
    throw error
  })
  return sheet
}

// The kit's tiles, drawn at the sheet's own size and scaled up without smoothing. Tells the
// editor which drawing it painted, or null if it couldn't, so the editor can color the cells
// that changed since then. Pieces drawn beside a changed cell, like a door's ends, still show
// the old tiles until the next paint.
function TileCanvas({
  drawn,
  onPainted,
}: {
  drawn: Drawn
  onPainted: (shown: Drawn | null) => void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const { drawing } = drawn
  useEffect(() => {
    let current = true
    loadSheet().then(
      (image) => {
        if (!current) return
        const context = canvas.current?.getContext('2d')
        if (!context) return onPainted(null)
        const size = drawing.tile_size
        context.imageSmoothingEnabled = false
        context.clearRect(0, 0, drawing.width * size, drawing.height * size)
        for (const { sx, sy, dx, dy } of sprites(drawing))
          context.drawImage(image, sx, sy, size, size, dx, dy, size, size)
        onPainted(drawn)
      },
      () => current && onPainted(null),
    )
    return () => {
      current = false
    }
  }, [drawn, drawing, onPainted])
  return (
    <canvas
      ref={canvas}
      aria-hidden
      width={drawing.width * drawing.tile_size}
      height={drawing.height * drawing.tile_size}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: drawing.width * CELL,
        height: drawing.height * CELL,
        imageRendering: 'pixelated',
      }}
    />
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
