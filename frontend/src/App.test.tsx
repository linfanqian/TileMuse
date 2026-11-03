import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import * as client from './api/client'

vi.mock('./api/client')

beforeEach(() => {
  vi.mocked(client.getSpec).mockResolvedValue({
    theme: 'dungeon',
    mood: 'quiet',
    kit: 'dungeon',
    width: 4,
    height: 4,
    doors: 1,
    objects: [],
    rules: [],
  })
  vi.mocked(client.generate).mockResolvedValue({
    map: {
      width: 4,
      height: 4,
      tiles: [
        [1, 2, 1, 1],
        [1, 0, 0, 1],
        [1, 0, 0, 1],
        [1, 1, 1, 1],
      ],
      objects: [],
    },
    violations: [],
    explanations: [],
  })
})

// Types an idea and waits for the generated map's cells.
async function generateMap() {
  render(<App />)
  fireEvent.change(screen.getByLabelText('Map idea'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  return screen.findAllByRole('gridcell')
}

test('an idea becomes a map with its issues', async () => {
  await generateMap()
  screen.getByText('No issues found.')
})

test('a new, smaller map starts the editor fresh', async () => {
  const cells = await generateMap()
  fireEvent.mouseEnter(cells[15]) // (3, 3), which the next map doesn't have.
  vi.mocked(client.generate).mockResolvedValue({
    map: {
      width: 3,
      height: 3,
      tiles: [
        [1, 2, 1],
        [1, 0, 1],
        [1, 1, 1],
      ],
      objects: [],
    },
    violations: [],
    explanations: [],
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await waitFor(() => expect(screen.getAllByRole('gridcell')).toHaveLength(9))
  expect(screen.getByRole('status').textContent).toContain('Hover a cell')
})

test('each edit runs validation', async () => {
  vi.mocked(client.validate).mockResolvedValue({
    violations: [],
    explanations: [{ code: 'door_count', text: 'Wrong number of doors.' }],
  })
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[1]) // The door at (1, 0).
  await screen.findByText('Wrong number of doors.')
  const [, map] = vi.mocked(client.validate).mock.lastCall!
  expect(map.tiles[0]).toEqual([1, 1, 1, 1])
})
