import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import SeedDialog from './SeedDialog'
import { MAX_SEED, parseSeed } from './seed'

function setup(seed = 7) {
  const onCancel = vi.fn()
  const onRegenerate = vi.fn()
  render(
    <SeedDialog seed={seed} onCancel={onCancel} onRegenerate={onRegenerate} />,
  )
  const input = screen.getByLabelText('Seed')
  const regenerate = screen.getByRole('button', { name: 'Regenerate' })
  return { onCancel, onRegenerate, input, regenerate }
}

test('takes whole numbers from 0 to the largest seed', () => {
  expect(parseSeed(' 42 ')).toBe(42)
  expect(parseSeed('0')).toBe(0)
  expect(parseSeed(String(MAX_SEED))).toBe(MAX_SEED)
  for (const bad of ['', '-1', '1.5', '1e3', 'abc', String(MAX_SEED + 1)])
    expect(parseSeed(bad)).toBeNull()
})

test('a seed that is not a whole number cannot be used', () => {
  const { input, regenerate, onRegenerate } = setup()
  fireEvent.change(input, { target: { value: '-3' } })
  expect(regenerate).toHaveProperty('disabled', true)
  screen.getByText(`Use a whole number from 0 to ${MAX_SEED}.`)
  fireEvent.submit(input)
  expect(onRegenerate).not.toHaveBeenCalled()
})

test('Enter regenerates with the typed seed', () => {
  const { input, onRegenerate } = setup()
  fireEvent.change(input, { target: { value: '123' } })
  fireEvent.submit(input)
  expect(onRegenerate).toHaveBeenCalledWith(123)
})

test('Escape and a click outside the dialog both cancel', () => {
  const { input, onCancel } = setup()
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(onCancel).toHaveBeenCalledTimes(1)
  const backdrop = screen.getByRole('dialog').parentElement!
  // A click inside doesn't.
  fireEvent.mouseDown(screen.getByRole('dialog'))
  fireEvent.click(screen.getByRole('dialog'))
  expect(onCancel).toHaveBeenCalledTimes(1)
  fireEvent.mouseDown(backdrop)
  fireEvent.click(backdrop)
  expect(onCancel).toHaveBeenCalledTimes(2)
})

test('a drag from the input that ends outside does not cancel', () => {
  const { input, onCancel } = setup()
  // The browser sends the click to the backdrop, since the press and release had only it in common.
  fireEvent.mouseDown(input)
  fireEvent.click(screen.getByRole('dialog').parentElement!)
  expect(onCancel).not.toHaveBeenCalled()
})
