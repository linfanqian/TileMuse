import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import ViolationList from './ViolationList'

test('shows one card per issue, with its rule and explanation', () => {
  render(
    <ViolationList
      violations={[
        { code: 'door_unreachable', x: 3, y: 0, details: {}, blocking: true },
        { code: 'door_count', details: {}, blocking: false },
      ]}
      explanations={[
        {
          code: 'door_unreachable',
          text: "The door at (3, 0) can't be reached.",
        },
        { code: 'door_count', text: 'Wrong number of doors.' },
      ]}
      onShow={() => {}}
    />,
  )
  const cards = screen.getAllByRole('listitem')
  expect(cards).toHaveLength(2)
  expect(cards[0].textContent).toContain('door unreachable')
  expect(cards[0].textContent).toContain('Hard rule')
  expect(cards[0].textContent).toContain("The door at (3, 0) can't be reached.")
  expect(cards[1].textContent).toContain('Spec rule')
  screen.getByRole('heading', { name: 'Issues 2' })
})

test('show on map gives the cell, and only issues with a cell have it', () => {
  const onShow = vi.fn()
  render(
    <ViolationList
      violations={[
        { code: 'object_unreachable', x: 2, y: 4, details: {}, blocking: true },
        { code: 'max_density', details: {}, blocking: false },
      ]}
      explanations={[
        { code: 'object_unreachable', text: 'Cut off.' },
        { code: 'max_density', text: 'Too many objects.' },
      ]}
      onShow={onShow}
    />,
  )
  const buttons = screen.getAllByRole('button', { name: 'Show on map' })
  expect(buttons).toHaveLength(1)
  fireEvent.click(buttons[0])
  expect(onShow).toHaveBeenCalledWith({ x: 2, y: 4 })
})

test('says so when there are no issues', () => {
  render(<ViolationList violations={[]} explanations={[]} onShow={() => {}} />)
  screen.getByText('No issues found.')
  // The count isn't shown as an error when there is nothing wrong.
  expect(screen.getByText('0').className).toBe('issue-count none')
})
