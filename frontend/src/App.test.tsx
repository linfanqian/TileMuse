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
  vi.mocked(client.generate).mockResolvedValue({
    map,
    violations: [],
    explanations: [],
  })
})

async function submitIdea() {
  render(<App />)
  fireEvent.change(screen.getByLabelText('Map idea'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findAllByRole('gridcell')
}

test('an idea becomes a map with its issues', async () => {
  await submitIdea()
  screen.getByText('No issues found.')
})

test('failed validation hides stale issues and shows an error', async () => {
  vi.mocked(client.validate).mockRejectedValue(new Error('down'))
  await submitIdea()

  fireEvent.click(screen.getAllByRole('gridcell')[0])

  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    expect.stringContaining('Validation failed'),
  )
  expect(screen.queryByText('No issues found.')).toBeNull()
})

test('a late validation of an older edit is ignored', async () => {
  const pending: ((r: client.ValidationResult) => void)[] = []
  vi.mocked(client.validate).mockImplementation(
    () => new Promise((resolve) => pending.push(resolve)),
  )
  await submitIdea()

  fireEvent.click(screen.getAllByRole('gridcell')[0])
  fireEvent.click(screen.getAllByRole('gridcell')[0])
  await act(async () =>
    pending[1]({ violations: [], explanations: [issue('new')] }),
  )
  await act(async () =>
    pending[0]({ violations: [], explanations: [issue('old')] }),
  )

  screen.getByText('new')
  expect(screen.queryByText('old')).toBeNull()
})
