import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import * as client from './api/client'

vi.mock('./api/client')

const spec: client.MapSpec = { width: 2, height: 1 }
const map: client.GameMap = {
  width: 2,
  height: 1,
  tiles: [[0, 0]],
  objects: [],
}
const issue = (text: string): client.Explanation => ({ code: 'c', text })

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(client.getSpec).mockResolvedValue(spec)
})

async function submitIdea() {
  fireEvent.change(screen.getByLabelText('Map idea'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findAllByRole('gridcell')
}

test('failed validation hides stale issues and shows an error', async () => {
  vi.mocked(client.generate).mockResolvedValue({
    map,
    violations: [],
    explanations: [],
  })
  vi.mocked(client.validate).mockRejectedValue(new Error('down'))
  render(<App />)
  await submitIdea()
  screen.getByText('No issues found.')

  fireEvent.click(screen.getAllByRole('gridcell')[0])

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    expect.stringContaining('Validation failed'),
  )
  expect(screen.queryByText('No issues found.')).toBeNull()
})

test('a validation response for an older map does not overwrite a newer map', async () => {
  let resolveOld!: (r: client.ValidationResult) => void
  vi.mocked(client.validate).mockReturnValue(
    new Promise((resolve) => {
      resolveOld = resolve
    }),
  )
  vi.mocked(client.generate)
    .mockResolvedValueOnce({ map, violations: [], explanations: [] })
    .mockResolvedValueOnce({
      map,
      violations: [],
      explanations: [issue('new map issue')],
    })
  render(<App />)
  await submitIdea()

  fireEvent.click(screen.getAllByRole('gridcell')[0]) // validation now pending
  await submitIdea()
  await screen.findByText('new map issue')

  await act(async () =>
    resolveOld({ violations: [], explanations: [issue('old map issue')] }),
  )
  screen.getByText('new map issue')
  expect(screen.queryByText('old map issue')).toBeNull()
})

test('editing the old map while a new one generates does not drop the new map', async () => {
  vi.mocked(client.validate).mockResolvedValue({
    violations: [],
    explanations: [],
  })
  let resolveNew!: (r: client.GenerateResult) => void
  vi.mocked(client.generate)
    .mockResolvedValueOnce({ map, violations: [], explanations: [] })
    .mockReturnValueOnce(
      new Promise((resolve) => {
        resolveNew = resolve
      }),
    )
  render(<App />)
  await submitIdea()

  fireEvent.click(screen.getByRole('button', { name: 'Generate' })) // generation now pending
  await vi.waitFor(() => expect(client.generate).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getAllByRole('gridcell')[0])

  await act(async () =>
    resolveNew({ map, violations: [], explanations: [issue('new map issue')] }),
  )
  screen.getByText('new map issue')
})

test('a successful validation does not clear a generation error', async () => {
  vi.mocked(client.validate).mockResolvedValue({
    violations: [],
    explanations: [],
  })
  vi.mocked(client.generate)
    .mockResolvedValueOnce({ map, violations: [], explanations: [] })
    .mockRejectedValueOnce(new Error('generate down'))
  render(<App />)
  await submitIdea()

  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findByText(/generate down/)
  fireEvent.click(screen.getAllByRole('gridcell')[0])

  await vi.waitFor(() => expect(client.validate).toHaveBeenCalled())
  await act(async () => {})
  screen.getByText(/generate down/)
})
