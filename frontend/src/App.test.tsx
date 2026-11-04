import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import * as client from './api/client'
import type { ValidationResult } from './api/client'

vi.mock('./api/client')

const SPEC: client.MapSpec = {
  theme: 'dungeon',
  mood: 'quiet',
  kit: 'dungeon',
  width: 4,
  height: 4,
  doors: 1,
  objects: [],
  rules: [],
}

beforeEach(() => {
  vi.resetAllMocks()
  // The editor falls back to colored cells, which these tests read.
  vi.mocked(client.drawMap).mockRejectedValue(new Error('no drawing in tests'))
  // One turn settles every field, so Generate map unlocks after the first idea.
  vi.mocked(client.interview).mockResolvedValue({
    type: 'done',
    message: 'The spec is ready.',
    question: null,
    draft: SPEC,
    spec: SPEC,
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

// Undoes the download stubs below after every test, even a failed one.
const realUrl = {
  createObjectURL: URL.createObjectURL,
  revokeObjectURL: URL.revokeObjectURL,
}
afterEach(() => {
  Object.assign(URL, realUrl)
  vi.restoreAllMocks()
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

// Sends an idea, makes a map from the spec, and waits for the map's cells.
async function generateMap() {
  render(<App />)
  fireEvent.change(screen.getByLabelText('Message'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('The spec is ready.')
  fireEvent.click(screen.getByRole('button', { name: 'Generate map' }))
  return screen.findAllByRole('gridcell')
}

// Goes back to the interview and makes a new map from the same spec.
function regenerate() {
  fireEvent.click(screen.getByRole('button', { name: '1 · Interview' }))
  fireEvent.click(screen.getByRole('button', { name: 'Generate map' }))
}

test('an idea becomes a map with its issues', async () => {
  await generateMap()
  screen.getByText('No issues found.')
  expect(client.generate).toHaveBeenCalledWith(SPEC, expect.any(Number))
  // The editor asks for the map drawn with the spec's kit, once its effect has run.
  await waitFor(() =>
    expect(client.drawMap).toHaveBeenCalledWith(SPEC.kit, expect.anything()),
  )
})

test('going back to the interview keeps the chat', async () => {
  await generateMap()
  // Hidden on the editor, but kept.
  expect(screen.queryByRole('log')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '1 · Interview' }))
  expect(screen.getByRole('log').textContent).toContain('The spec is ready.')
  fireEvent.click(screen.getByRole('button', { name: '2 · Edit' }))
  screen.getAllByRole('gridcell')
})

test('start over clears the map and the chat', async () => {
  await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
  expect(screen.queryAllByRole('gridcell')).toHaveLength(0)
  expect(screen.queryByText('The spec is ready.')).toBeNull()
  expect(screen.getByRole('button', { name: '2 · Edit' })).toHaveProperty(
    'disabled',
    true,
  )
})

test('a map that arrives after start over is dropped', async () => {
  render(<App />)
  fireEvent.change(screen.getByLabelText('Message'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('The spec is ready.')
  const pending = later<client.GenerateResult>()
  vi.mocked(client.generate).mockReturnValueOnce(pending.promise)
  fireEvent.click(screen.getByRole('button', { name: 'Generate map' }))
  fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
  await act(async () =>
    pending.resolve({
      map: { width: 1, height: 1, tiles: [[1]], objects: [] },
      violations: [],
      explanations: [],
    }),
  )
  expect(screen.queryAllByRole('gridcell')).toHaveLength(0)
  screen.getByLabelText('Message')
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
  regenerate()
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
  regenerate()
  await screen.findByText('New map.')
  await act(async () => old.resolve(issues('Old map.')))
  expect(screen.queryByText('Old map.')).toBeNull()
})

test('while a map is being made, Generate is disabled and edits are ignored', async () => {
  const cells = await generateMap()
  const result = later<client.GenerateResult>()
  vi.mocked(client.generate).mockReturnValueOnce(result.promise)
  regenerate()
  const button = screen.getByRole('button', { name: 'Generating…' })
  expect(button).toHaveProperty('disabled', true)
  fireEvent.click(button)
  expect(client.generate).toHaveBeenCalledTimes(2)

  fireEvent.click(screen.getByRole('button', { name: '2 · Edit' }))
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  expect(client.validate).not.toHaveBeenCalled()
  expect(cells[5].getAttribute('aria-label')).toBe('(1, 1) · floor')

  await act(async () =>
    result.resolve(await vi.mocked(client.generate).mock.results[0].value),
  )
  fireEvent.click(screen.getByRole('button', { name: '1 · Interview' }))
  await screen.findByRole('button', { name: 'Generate map' })
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
  vi.mocked(client.generate).mockRejectedValueOnce(new Error('generate down'))
  regenerate()
  await screen.findByRole('alert')
  await act(async () => pending.resolve(issues('After the edit.')))
  screen.getByText('After the edit.')
})

test('a good validation does not clear a Generate error', async () => {
  vi.mocked(client.validate).mockResolvedValue(issues('Fine.'))
  const cells = await generateMap()
  vi.mocked(client.generate).mockRejectedValueOnce(new Error('generate down'))
  regenerate()
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: '2 · Edit' }))
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  await screen.findByText('Fine.')
  expect(screen.getByRole('alert').textContent).toContain('generate down')
})

test('a new map clears a validation error from the old map', async () => {
  const failing = later<ValidationResult>()
  vi.mocked(client.validate).mockReturnValueOnce(failing.promise)
  const cells = await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  const result = later<client.GenerateResult>()
  vi.mocked(client.generate).mockReturnValueOnce(result.promise)
  regenerate()
  await act(async () => failing.reject(new Error('backend down')))
  screen.getByRole('alert')
  await act(async () =>
    result.resolve(await vi.mocked(client.generate).mock.results[0].value),
  )
  await screen.findAllByRole('gridcell')
  expect(screen.queryByRole('alert')).toBeNull()
})

test('a failed validation does not replace a Generate error', async () => {
  vi.mocked(client.validate)
    .mockRejectedValueOnce(new Error('backend down'))
    .mockResolvedValueOnce(issues('Fine.'))
  const cells = await generateMap()
  vi.mocked(client.generate).mockRejectedValueOnce(new Error('generate down'))
  regenerate()
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: '2 · Edit' }))
  fireEvent.click(screen.getByRole('button', { name: 'wall' }))
  fireEvent.click(cells[5])
  await waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2))
  fireEvent.click(cells[6])
  await screen.findByText('Fine.')
  const [alert] = screen.getAllByRole('alert')
  expect(alert.textContent).toContain('generate down')
  expect(screen.getAllByRole('alert')).toHaveLength(1)
})

// Stubs the browser download, which jsdom can't do. Returns the clicked links.
function stubDownload() {
  URL.createObjectURL = vi.fn(() => 'blob:map')
  URL.revokeObjectURL = vi.fn()
  const clicked: HTMLAnchorElement[] = []
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push(this)
  })
  return clicked
}

test('export downloads a zip for the map and frees its URL later', async () => {
  const clicked = stubDownload()
  const timers = vi.spyOn(window, 'setTimeout')
  const zip = new Blob(['zip'], { type: 'application/zip' })
  vi.mocked(client.exportMap).mockResolvedValue(zip)
  await generateMap()
  fireEvent.click(screen.getByRole('button', { name: 'Export for Tiled' }))
  await waitFor(() => expect(clicked).toHaveLength(1))
  const [spec, map] = vi.mocked(client.exportMap).mock.lastCall!
  expect(spec.kit).toBe('dungeon')
  expect(map.width).toBe(4)
  expect(URL.createObjectURL).toHaveBeenCalledWith(zip)
  expect(clicked[0].download).toBe('tilemuse-map.zip')

  // Freed a minute later, not right away, so slower browsers can still read the file.
  expect(URL.revokeObjectURL).not.toHaveBeenCalled()
  const free = timers.mock.calls.find(([, delay]) => delay === 60_000)?.[0]
  expect(free).toBeDefined()
  ;(free as () => void)()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:map')
})

test('an export error goes away when export is tried again', async () => {
  stubDownload()
  vi.mocked(client.exportMap)
    .mockRejectedValueOnce(new Error('export failed'))
    .mockResolvedValueOnce(new Blob(['zip'], { type: 'application/zip' }))
  await generateMap()
  const exportButton = screen.getByRole('button', { name: 'Export for Tiled' })
  fireEvent.click(exportButton)
  await screen.findByRole('alert')
  fireEvent.click(exportButton)
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
})
