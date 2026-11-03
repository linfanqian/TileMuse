import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { expect, test, vi } from 'vitest'
import type { GameMap } from '../../api/client'
import MapEditor from './MapEditor'

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
