import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import * as client from '../../api/client'
import type { InterviewDone, MapSpec } from '../../api/client'
import Interview from './Interview'

vi.mock('../../api/client')

const SPEC: MapSpec = {
  theme: 'library',
  mood: 'creepy',
  kit: 'dungeon',
  width: 20,
  height: 14,
  doors: 1,
  objects: [{ kind: 'guard', count: 2 }],
  rules: [],
}

const asking: InterviewDone = {
  type: 'done',
  message: 'How big should the room be?',
  question: {
    field: 'width',
    reason: 'Bigger rooms give longer guard routes.',
    suggestions: ['Small · 12×10', 'Medium · 20×14'],
  },
  draft: { theme: 'library', mood: 'creepy' },
  spec: null,
}

const ready: InterviewDone = {
  type: 'done',
  message: 'The spec is ready to generate.',
  question: null,
  draft: SPEC,
  spec: SPEC,
}

beforeEach(() => vi.resetAllMocks())

function setup() {
  const onGenerate = vi.fn()
  const { unmount } = render(
    <Interview onGenerate={onGenerate} generating={false} />,
  )
  const say = (text: string) => {
    fireEvent.change(screen.getByLabelText('Message'), {
      target: { value: text },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  }
  return { onGenerate, say, unmount }
}

test('a question shows its reason and suggested answers', async () => {
  vi.mocked(client.interview).mockResolvedValue(asking)
  const { say } = setup()
  say('A creepy library')
  await screen.findByText('How big should the room be?')
  screen.getByText('Bigger rooms give longer guard routes.')
  screen.getByRole('button', { name: 'Medium · 20×14' })
  expect(client.interview).toHaveBeenCalledWith(
    [{ role: 'user', content: 'A creepy library' }],
    {},
    expect.any(Function),
    expect.any(AbortSignal),
  )
})

test('picking a chip sends it as the answer, with the history and draft', async () => {
  vi.mocked(client.interview)
    .mockResolvedValueOnce(asking)
    .mockResolvedValueOnce(ready)
  const { say } = setup()
  say('A creepy library')
  fireEvent.click(await screen.findByRole('button', { name: 'Medium · 20×14' }))
  await screen.findByText('The spec is ready to generate.')
  expect(vi.mocked(client.interview).mock.lastCall!.slice(0, 2)).toEqual([
    [
      { role: 'user', content: 'A creepy library' },
      { role: 'assistant', content: 'How big should the room be?' },
      { role: 'user', content: 'Medium · 20×14' },
    ],
    asking.draft,
  ])
  // The chosen chip stays marked, and old chips can't be picked again.
  const chosen = screen.getByRole('button', { name: 'Medium · 20×14' })
  expect(chosen.getAttribute('aria-pressed')).toBe('true')
  expect(chosen).toHaveProperty('disabled', true)
})

test('the spec panel shows each field and its status', async () => {
  vi.mocked(client.interview).mockResolvedValue(asking)
  const { say } = setup()
  say('A creepy library')
  await screen.findByText('How big should the room be?')
  const row = (label: string) =>
    screen.getByRole('rowheader', { name: label }).closest('tr')!.textContent
  expect(row('Theme')).toBe('Themelibraryready')
  expect(row('Size')).toBe('Size—asking')
  expect(row('Doors')).toBe('Doors—next')
  screen.getByText('Library. Mood: creepy.')
  screen.getByText('2 of 7 fields ready')
})

test('Generate map unlocks once the spec is ready', async () => {
  vi.mocked(client.interview)
    .mockResolvedValueOnce(asking)
    .mockResolvedValueOnce(ready)
  const { say, onGenerate } = setup()
  const generate = screen.getByRole('button', { name: 'Generate map' })
  expect(generate).toHaveProperty('disabled', true)
  say('A creepy library')
  await screen.findByText('How big should the room be?')
  expect(generate).toHaveProperty('disabled', true)
  say('20 by 14')
  await screen.findByText('The spec is ready to generate.')
  fireEvent.click(generate)
  expect(onGenerate).toHaveBeenCalledWith(SPEC)
})

test('streamed text shows while the turn runs, then the final message', async () => {
  let finish!: (done: InterviewDone) => void
  vi.mocked(client.interview).mockImplementation(
    (_messages, _draft, onText) =>
      new Promise((resolve) => {
        onText('How big ')
        onText('is it?')
        finish = resolve
      }),
  )
  const { say } = setup()
  say('A creepy library')
  await screen.findByText('How big is it?')
  expect(screen.getByRole('button', { name: 'Send' })).toHaveProperty(
    'disabled',
    true,
  )
  await act(async () => finish(asking))
  screen.getByText('How big should the room be?')
  expect(screen.queryByText('How big is it?')).toBeNull()
})

test('a failed turn shows the error and gives the answer back', async () => {
  vi.mocked(client.interview).mockRejectedValue(new Error('LLM down'))
  const { say } = setup()
  say('A creepy library')
  expect((await screen.findByRole('alert')).textContent).toBe('LLM down')
  expect(screen.getByLabelText('Message')).toHaveProperty(
    'value',
    'A creepy library',
  )
  expect(screen.getByRole('log').textContent).not.toContain('A creepy library')
})

test('Enter sends and Shift+Enter does not', async () => {
  vi.mocked(client.interview).mockResolvedValue(asking)
  setup()
  const box = screen.getByLabelText('Message')
  fireEvent.change(box, { target: { value: 'A creepy library' } })
  fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })
  expect(client.interview).not.toHaveBeenCalled()
  fireEvent.keyDown(box, { key: 'Enter' })
  await screen.findByText('How big should the room be?')
})

test('unmounting stops the turn in flight', () => {
  vi.mocked(client.interview).mockReturnValue(new Promise(() => {}))
  const { say, unmount } = setup()
  say('A creepy library')
  const signal = vi.mocked(client.interview).mock.lastCall![3]!
  screen.getByText('Thinking…')
  expect(signal.aborted).toBe(false)
  unmount()
  expect(signal.aborted).toBe(true)
})

test('the hint tells an unfinished spec from one that does not fit', async () => {
  const draft = { ...SPEC, height: null }
  vi.mocked(client.interview)
    .mockResolvedValueOnce({ ...asking, draft })
    .mockResolvedValueOnce({ ...asking, draft: SPEC })
  const { say } = setup()
  say('A creepy library')
  await screen.findByText('How big should the room be?')
  screen.getByText('Available once every field is ready')
  say('Make it 20 by 14')
  await screen.findByText("Some fields don't fit together yet")
})
