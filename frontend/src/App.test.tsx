import { fireEvent, render, screen } from '@testing-library/react'
import { test, vi } from 'vitest'
import App from './App'
import * as client from './api/client'

vi.mock('./api/client')

test('an idea becomes a map with its issues', async () => {
  vi.mocked(client.getSpec).mockResolvedValue({ width: 2, height: 1 })
  vi.mocked(client.generate).mockResolvedValue({
    map: { width: 2, height: 1, tiles: [[0, 0]], objects: [] },
    violations: [],
    explanations: [],
  })
  render(<App />)
  fireEvent.change(screen.getByLabelText('Map idea'), {
    target: { value: 'room' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await screen.findAllByRole('gridcell')
  screen.getByText('No issues found.')
})
