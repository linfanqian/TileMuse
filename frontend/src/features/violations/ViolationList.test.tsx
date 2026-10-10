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
})
