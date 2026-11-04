import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import * as client from './api/client'
import type { ValidationResult } from './api/client'

vi.mock('./api/client')

beforeEach(() => {
  vi.resetAllMocks()
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

// A promise the test settles by hand, to control the order replies arrive in.
function later<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const issues = (text: string): ValidationResult => ({
  violations: [],
  explanations: [{ code: 'door_count', text }],
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

test('a slow reply for an older edit does not replace newer issues', async () => {
  const older = later<ValidationResult>()
  const newer = later<ValidationResult>()
  vi.mocked(client.validate)
    .mockReturnValueOnce(older.promise)
    .mockReturnValueOnce(newer.promise)
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  fireEvent.click(cells[6])
  await act(async () => newer.resolve(issues('Newer.')))
  await act(async () => older.resolve(issues('Older.')))
  screen.getByText('Newer.')
  expect(screen.queryByText('Older.')).toBeNull()
})

test('a reply for the old map does not land on a new map', async () => {
  const old = later<ValidationResult>()
  vi.mocked(client.validate).mockReturnValueOnce(old.promise)
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  vi.mocked(client.generate).mockResolvedValue({
    ...(await vi.mocked(client.generate).mock.results[0].value),
    explanations: [{ code: 'door_count', text: 'New map.' }],
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findByText('New map.')
  await act(async () => old.resolve(issues('Old map.')))
  expect(screen.queryByText('Old map.')).toBeNull()
})

test('while a map is being made, Generate is disabled and edits are ignored', async () => {
  const cells = await generateMap()
  const spec = later<client.MapSpec>()
  vi.mocked(client.getSpec).mockReturnValueOnce(spec.promise)
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  const button = screen.getByRole('button', { name: 'Generating…' })
  expect(button).toHaveProperty('disabled', true)
  fireEvent.submit(button.closest('form')!)
  expect(client.getSpec).toHaveBeenCalledTimes(2)

  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  expect(client.validate).not.toHaveBeenCalled()
  expect(cells[5].getAttribute('aria-label')).toBe('(1, 1) · floor')

  await act(async () =>
    spec.resolve(await vi.mocked(client.getSpec).mock.results[0].value),
  )
  await screen.findByRole('button', { name: 'Generate' })
})

test('an error goes away once a later edit validates', async () => {
  vi.mocked(client.validate)
    .mockRejectedValueOnce(new Error('backend down'))
    .mockResolvedValueOnce(issues('Fine again.'))
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  await screen.findByRole('alert')
  fireEvent.click(cells[6])
  await screen.findByText('Fine again.')
  expect(screen.queryByRole('alert')).toBeNull()
})

test('the seed is kept and shown', async () => {
  const random = vi.spyOn(Math, 'random').mockReturnValue(0.5)
  await generateMap()
  random.mockRestore()
  screen.getByText('Seed: 1073741824')
  expect(client.generate).toHaveBeenCalledWith(expect.anything(), 1073741824)
})

test('a failed Generate keeps the reply for the edit before it', async () => {
  const pending = later<ValidationResult>()
  vi.mocked(client.validate).mockReturnValueOnce(pending.promise)
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  vi.mocked(client.getSpec).mockRejectedValueOnce(new Error('LLM down'))
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findByRole('alert')
  await act(async () => pending.resolve(issues('After the edit.')))
  screen.getByText('After the edit.')
})

test('a good validation does not clear a Generate error', async () => {
  vi.mocked(client.validate).mockResolvedValue(issues('Fine.'))
  const cells = await generateMap()
  vi.mocked(client.getSpec).mockRejectedValueOnce(new Error('LLM down'))
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  await screen.findByText('Fine.')
  expect(screen.getByRole('alert').textContent).toContain('LLM down')
})
