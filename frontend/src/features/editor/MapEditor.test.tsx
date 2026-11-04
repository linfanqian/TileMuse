import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, expect, test, vi } from 'vitest'
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
  }
}

test('draws the kit tiles under the cells once they arrive', async () => {
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { cell } = setup()
  expect(client.drawMap).toHaveBeenCalledWith('dungeon', start)

  const canvas = await waitFor(() => {
    const found = document.querySelector('canvas')
    expect(found).not.toBeNull()
    return found!
  })
  // The canvas holds 16px tiles and is shown at 32px per cell.
  expect([canvas.width, canvas.height]).toEqual([4 * 16, 4 * 16])
  expect(canvas.style.width).toBe('128px')
  // The cells start one row down, under the extra top-wall row.
  expect(screen.getByRole('grid').parentElement!.style.paddingTop).toBe('32px')
  // The spawn is a kit tile now, so its cell has no marker and no color.
  expect(cell(1, 1).textContent).toBe('')
  expect(cell(1, 1).style.background).toBe('')
  // Cells still name their contents.
  expect(cell(1, 1).getAttribute('aria-label')).toBe(
    '(1, 1) · floor · player spawn',
  )
})

test('edits still work over the kit tiles, and each edit is drawn again', async () => {
  vi.mocked(client.drawMap).mockImplementation(async (_, map) => drawingOf(map))
  const { onChange, cell, tool } = setup()
  await waitFor(() => expect(document.querySelector('canvas')).not.toBeNull())
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
  expect(document.querySelector('canvas')).toBeNull()
  expect(cell(1, 1).textContent).toBe('P')
  expect(cell(0, 0).style.background).not.toBe('')
})
