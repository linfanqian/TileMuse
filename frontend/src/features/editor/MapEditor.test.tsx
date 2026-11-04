import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as client from '../../api/client'
import type { Drawing, GameMap } from '../../api/client'
import MapEditor from './MapEditor'

vi.mock('../../api/client')

beforeEach(() => {
  vi.resetAllMocks()
  // Most tests read the colored cells drawn when the kit's tiles aren't there.
  vi.mocked(client.drawMap).mockRejectedValue(new Error('no drawing'))
})

const start: GameMap = {
  width: 4,
  height: 3,
  tiles: [
    [1, 2, 1, 1],
    [1, 0, 0, 1],
    [1, 1, 1, 1],
  ],
  objects: [{ kind: 'player_spawn', x: 1, y: 1 }],
}

// Keeps the edited map, as App does, and records each change.
function setup() {
  const onChange = vi.fn()
  function Host() {
    const [map, setMap] = useState(start)
    return (
      <MapEditor
        map={map}
        kit="dungeon"
        onChange={(next) => {
          onChange(next)
          setMap(next)
        }}
      />
    )
  }
  render(<Host />)
  const cell = (x: number, y: number) =>
    screen.getAllByRole('gridcell')[y * start.width + x]
  const tool = (name: string) =>
    fireEvent.click(screen.getByRole('button', { name }))
  return { onChange, cell, tool }
}

test('shows each object on its cell', () => {
  const { cell } = setup()
  expect(cell(1, 1).getAttribute('aria-label')).toBe(
    '(1, 1) · floor · player spawn',
  )
  expect(cell(1, 1).textContent).toBe('P')
})

test('the palette has select, erase, three tiles, and every object kind', () => {
  setup()
  const names = screen
    .getAllByRole('button')
    .map((b) => b.getAttribute('aria-label'))
  expect(names).toEqual([
    'select',
    'erase',
    'floor',
    'wall',
    'door',
    'player spawn',
    'guard',
    'cover',
    'chest',
    'key',
    'light',
  ])
})

test('paints tiles and skips edits that change nothing', () => {
  const { onChange, cell, tool } = setup()
  tool('wall')
  fireEvent.click(cell(2, 1))
  expect(onChange).toHaveBeenLastCalledWith(
    expect.objectContaining({
      tiles: [[1, 2, 1, 1], [1, 0, 1, 1], start.tiles[2]],
    }),
  )
  fireEvent.click(cell(2, 1))
  expect(onChange).toHaveBeenCalledTimes(1)
})

test('places, moves, and erases objects, one per cell', () => {
  const { onChange, cell, tool } = setup()
  tool('guard')
  fireEvent.click(cell(2, 1))
  expect(cell(2, 1).textContent).toBe('G')

  // Placing on a taken cell replaces the object there.
  tool('key')
  fireEvent.click(cell(2, 1))
  expect(onChange.mock.lastCall?.[0].objects).toEqual([
    { kind: 'player_spawn', x: 1, y: 1 },
    { kind: 'key', x: 2, y: 1 },
  ])

  // A move onto a taken cell selects that object instead.
  tool('select')
  fireEvent.click(cell(1, 1))
  expect(cell(1, 1).getAttribute('aria-selected')).toBe('true')
  fireEvent.click(cell(2, 1))
  expect(cell(2, 1).getAttribute('aria-selected')).toBe('true')
  fireEvent.click(cell(1, 0))
  expect(cell(1, 0).textContent).toBe('K')
  expect(cell(2, 1).textContent).toBe('')

  tool('erase')
  fireEvent.click(cell(1, 0))
  expect(onChange.mock.lastCall?.[0].objects).toEqual([
    { kind: 'player_spawn', x: 1, y: 1 },
  ])
})

test('hovering a cell shows its position and contents', () => {
  const { cell } = setup()
  const status = screen.getByRole('status')
  expect(status.textContent).toContain('Hover a cell')
  expect(status.textContent).toContain('4 × 3')
  fireEvent.mouseEnter(cell(1, 0))
  expect(status.textContent).toContain('(1, 0) · door')
  fireEvent.mouseEnter(cell(1, 1))
  expect(status.textContent).toContain('(1, 1) · floor · player spawn')
})

// jsdom loads no images and has no canvas, so these stand in for both. `context` decides
// whether the canvas can paint.
function stubCanvas(
  context: object | null = { drawImage: vi.fn(), clearRect: vi.fn() },
) {
  vi.stubGlobal(
    'Image',
    class {
      onload: (() => void) | null = null
      set src(_: string) {
        queueMicrotask(() => this.onload?.())
      }
    },
  )
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as CanvasRenderingContext2D | null,
  )
  return context
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// The canvas behind the map cells. Tool icons have canvases of their own.
const mapCanvas = () =>
  document.querySelector<HTMLCanvasElement>('.map-frame canvas')

// Waits until the canvas has painted, which turns the cell colors off.
const painted = (cell: HTMLElement) =>
  waitFor(() => expect(cell.style.background).toBe(''))

// A drawing for `start` with a two-row top wall, so the cells sit one row down.
function drawingOf(map: GameMap): Drawing {
  const rows = map.height + 1
  return {
    width: map.width,
    height: rows,
    shift: 1,
    tile_size: 16,
    columns: 12,
    floor: Array.from({ length: rows }, () => Array(map.width).fill(48)),
    walls: Array.from({ length: rows }, () => Array(map.width).fill(null)),
    objects: map.objects.map((o) => ({ ...o, y: o.y + 1, tile: 85 })),
    // A three-tile door, like a fence opening, and one tile for each other tool.
    tools: { floor: [48], wall: [25], door: [5, 48, 4], player_spawn: [85] },
  }
}

test('draws the kit tiles under the cells once they arrive', async () => {
  const context = stubCanvas() as { drawImage: ReturnType<typeof vi.fn> }
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { cell } = setup()
  expect(client.drawMap).toHaveBeenCalledWith('dungeon', start)

  const canvas = await waitFor(() => {
    const found = mapCanvas()
    expect(found).not.toBeNull()
    return found!
  })
  // The canvas holds 16px tiles and is shown at 32px per cell.
  expect([canvas.width, canvas.height]).toEqual([4 * 16, 4 * 16])
  expect(canvas.style.width).toBe('128px')
  // Once painted, the spawn is a kit tile, so its cell has no marker and no color.
  await painted(cell(1, 1))
  // The cells sit one row down, under the extra top-wall row.
  expect(screen.getByRole('grid').parentElement!.style.paddingTop).toBe('32px')
  expect(cell(1, 1).textContent).toBe('')
  expect(context.drawImage).toHaveBeenCalled()
  // Cells still name their contents.
  expect(cell(1, 1).getAttribute('aria-label')).toBe(
    '(1, 1) · floor · player spawn',
  )
})

test('edits still work over the kit tiles, and each edit is drawn again', async () => {
  stubCanvas()
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { onChange, cell, tool } = setup()
  await painted(cell(2, 1))
  tool('wall')
  fireEvent.click(cell(2, 1))
  expect(onChange).toHaveBeenCalledTimes(1)
  const [edited] = onChange.mock.lastCall!
  await waitFor(() =>
    expect(client.drawMap).toHaveBeenLastCalledWith('dungeon', edited),
  )

  tool('select')
  fireEvent.click(cell(1, 1))
  fireEvent.click(cell(2, 2))
  expect(onChange.mock.lastCall![0].objects).toEqual([
    { kind: 'player_spawn', x: 2, y: 2 },
  ])
})

test('without the kit tiles, cells keep their colors and markers', async () => {
  const { cell } = setup()
  await waitFor(() => expect(client.drawMap).toHaveBeenCalled())
  expect(mapCanvas()).toBeNull()
  expect(cell(1, 1).textContent).toBe('P')
  expect(cell(0, 0).style.background).not.toBe('')
})

test('an edit shows at once, in color, until its drawing arrives', async () => {
  stubCanvas()
  let release = () => {}
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => {
    if (map !== start) await new Promise<void>((r) => (release = r))
    return drawingOf(map)
  })
  const { cell, tool } = setup()
  await painted(cell(2, 1))

  tool('wall')
  fireEvent.click(cell(2, 1))
  expect(cell(2, 1).style.background).not.toBe('') // The new wall, in color.
  expect(cell(1, 1).style.background).toBe('') // Unchanged cells stay tiles.

  tool('select')
  fireEvent.click(cell(1, 1))
  fireEvent.click(cell(2, 2))
  expect(cell(2, 2).textContent).toBe('P') // The moved spawn, as a marker.
  expect(cell(1, 1).style.background).not.toBe('') // Covers the old spawn tile.

  release()
  await painted(cell(2, 2))
  expect(cell(2, 2).textContent).toBe('')
})

test('a door inside the room stays visible, since the kit draws it as floor', async () => {
  const context = stubCanvas() as { clearRect: ReturnType<typeof vi.fn> }
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { cell, tool } = setup()
  await painted(cell(2, 1))
  tool('door')
  fireEvent.click(cell(2, 1))
  // Wait until the canvas has painted the map with the door, so the cell isn't colored
  // only because the canvas is behind.
  // The map canvas clears its whole 4×4-tile area; tool icons clear one row of tiles.
  const mapPaints = () =>
    context.clearRect.mock.calls.filter((args) => args[3] === 4 * 16).length
  await waitFor(() => expect(mapPaints()).toBe(2))
  await waitFor(() => expect(cell(1, 1).style.background).toBe(''))
  expect(cell(2, 1).style.background).not.toBe('')
})

test('if the canvas cannot paint, cells keep their colors and markers', async () => {
  stubCanvas(null)
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { cell } = setup()
  await waitFor(() => expect(mapCanvas()).not.toBeNull())
  await waitFor(() =>
    expect(HTMLCanvasElement.prototype.getContext).toHaveBeenCalled(),
  )
  expect(cell(1, 1).textContent).toBe('P')
  expect(cell(1, 1).style.background).not.toBe('')
})

// The loaded sheet is kept for the whole page, so the sheet tests load a fresh editor module.
// Its sheet loads never finish unless the test says so; `loads` holds each one started.
async function freshEditor() {
  vi.resetModules()
  const fresh = await import('../../api/client')
  const { default: Editor } = await import('./MapEditor')
  const loads: { onerror: (() => void) | null }[] = []
  vi.stubGlobal(
    'Image',
    class {
      onerror: (() => void) | null = null
      set src(_: string) {
        loads.push(this)
      }
    },
  )
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    {} as CanvasRenderingContext2D,
  )
  vi.mocked(fresh.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const show = (map: GameMap) => (
    <Editor map={map} kit="dungeon" onChange={() => {}} />
  )
  const { rerender } = render(show(start))
  return { fresh, loads, show, rerender }
}

test('redraws share one sheet load, and a failed load is tried again', async () => {
  const { fresh, loads, show, rerender } = await freshEditor()
  await waitFor(() => expect(loads).toHaveLength(1))

  rerender(show({ ...start, objects: [] }))
  await waitFor(() => expect(fresh.drawMap).toHaveBeenCalledTimes(2))
  await new Promise((r) => setTimeout(r)) // Lets the second draw reach the canvas.
  expect(loads).toHaveLength(1)

  loads[0].onerror!()
  rerender(show(start))
  await waitFor(() => expect(loads).toHaveLength(2))
})

test('a stalled sheet load is dropped after a while, so a later redraw tries again', async () => {
  vi.useFakeTimers()
  // Lets the draw replies arrive and the canvas start its load.
  const settle = () => act(() => vi.advanceTimersByTimeAsync(0))
  const { loads, show, rerender } = await freshEditor()
  await settle()
  expect(loads).toHaveLength(1)

  await act(() => vi.advanceTimersByTimeAsync(9_000))
  rerender(show({ ...start, objects: [] }))
  await settle()
  expect(loads).toHaveLength(1) // Still waiting on the first load.

  await act(() => vi.advanceTimersByTimeAsync(1_000))
  rerender(show(start))
  await settle()
  expect(loads).toHaveLength(2)
})

test('outlines the cell it is asked to point out, and scrolls to it', () => {
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  render(
    <MapEditor
      map={start}
      kit="dungeon"
      onChange={() => {}}
      highlight={{ x: 2, y: 1 }}
    />,
  )
  const cells = screen.getAllByRole('gridcell')
  expect(cells[1 * start.width + 2].style.boxShadow).not.toBe('')
  expect(cells.filter((c) => c.style.boxShadow !== '')).toHaveLength(1)
  // A big map scrolls, so the cell is brought into view.
  expect(scroll.mock.contexts).toEqual([cells[1 * start.width + 2]])
  delete (Element.prototype as Partial<Element>).scrollIntoView
})

test('the tool buttons show the kit tiles once a drawing says what they are', async () => {
  const context = stubCanvas() as { drawImage: ReturnType<typeof vi.fn> }
  let arrive!: (drawing: Drawing) => void
  vi.mocked(client.drawMap).mockReturnValue(new Promise((r) => (arrive = r)))
  setup()
  const button = (name: string) => screen.getByRole('button', { name })
  // Until then, colors and markers.
  expect(button('wall').querySelector('canvas')).toBeNull()
  expect(button('player spawn').textContent).toBe('P')

  await act(async () => arrive(drawingOf(start)))
  await waitFor(() =>
    expect(button('door').querySelector('canvas')?.style.display).toBe('block'),
  )
  // The door is a three-tile opening, drawn side by side from the sheet.
  const door = button('door').querySelector('canvas')!
  expect([door.width, door.height]).toEqual([3 * 16, 16])
  // Tile 5 is row 0, column 5 of the 12-column sheet.
  expect(context.drawImage).toHaveBeenCalledWith(
    expect.anything(),
    5 * 16,
    0,
    16,
    16,
    0,
    0,
    16,
    16,
  )
  expect(button('player spawn').textContent).toBe('')
  // A kind the drawing has no tiles for keeps its marker.
  expect(button('guard').textContent).toBe('G')
})

test('a drawing without tool tiles keeps the colored tools', async () => {
  stubCanvas()
  // As an older backend sends it, before `tools` existed.
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => {
    const { tools: _tools, ...drawing } = drawingOf(map)
    return drawing as Drawing
  })
  const { cell } = setup()
  await painted(cell(2, 1))
  expect(
    screen.getByRole('button', { name: 'wall' }).querySelector('canvas'),
  ).toBeNull()
  expect(screen.getByRole('button', { name: 'player spawn' }).textContent).toBe(
    'P',
  )
})
