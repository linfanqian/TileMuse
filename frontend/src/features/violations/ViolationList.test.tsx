import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import ViolationList from './ViolationList'

test('renders one item per explanation', () => {
  render(
    <ViolationList
      explanations={[
        { code: 'a', text: 'First issue' },
        { code: 'b', text: 'Second issue' },
      ]}
    />,
  )
  expect(screen.getAllByRole('listitem')).toHaveLength(2)
  screen.getByText('Second issue')
})

test('renders an empty state when there are no explanations', () => {
  render(<ViolationList explanations={[]} />)
  screen.getByText('No issues found.')
  expect(screen.queryByRole('list')).toBeNull()
})
