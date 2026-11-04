import { expect, test } from 'vitest'
import type { ChatMessage, SpecDraft } from '../../api/client'
import { MAX_MESSAGES, allSet, specRows, summary, trimHistory } from './fields'

test('rows show set fields as ready and the asked field as asking', () => {
  const rows = specRows(
    { theme: 'library', mood: 'creepy', width: 20, height: 14, objects: [] },
    { field: 'objects', reason: 'Why.', suggestions: ['a', 'b'] },
  )
  const byLabel = Object.fromEntries(rows.map((r) => [r.label, r]))
  expect(byLabel['Theme']).toEqual({
    label: 'Theme',
    value: 'library',
    status: 'ready',
  })
  expect(byLabel['Size']).toMatchObject({ value: '20 × 14', status: 'ready' })
  expect(byLabel['Objects']).toMatchObject({ value: 'none', status: 'asking' })
  expect(byLabel['Doors']).toMatchObject({ value: '—', status: 'next' })
})

test('size is ready only once both sides are set, and asking for either', () => {
  const [size] = specRows({ width: 20 }, null).filter((r) => r.label === 'Size')
  expect(size).toMatchObject({ value: '20 × ?', status: 'next' })
  const [asked] = specRows(
    { width: 20, height: 14 },
    { field: 'height', reason: 'Why.', suggestions: ['a', 'b'] },
  ).filter((r) => r.label === 'Size')
  expect(asked.status).toBe('asking')
})

test('objects and rules read as plain words', () => {
  const rows = specRows(
    {
      objects: [
        { kind: 'player_spawn', count: 1 },
        { kind: 'guard', count: 2 },
      ],
      rules: [
        { type: 'max_density', max: 0.25 },
        { type: 'min_distance', a: 'guard', b: 'guard', tiles: 4 },
        { type: 'min_distance', a: 'guard', b: 'player_spawn', tiles: 5 },
      ],
    },
    null,
  )
  const value = (label: string) => rows.find((r) => r.label === label)!.value
  expect(value('Objects')).toBe('player spawn ×1, guard ×2')
  expect(value('Layout rules')).toBe(
    'at most 25% of the floor filled; guards ≥ 4 tiles apart; guard ≥ 5 tiles from player spawn',
  )
})

test('the summary names what is decided', () => {
  expect(summary({})).toBeNull()
  expect(summary({ theme: 'abandoned library', mood: 'creepy' })).toBe(
    'Abandoned library. Mood: creepy.',
  )
  expect(summary({ theme: 'A barn.', width: 12, height: 10, doors: 2 })).toBe(
    'A barn. 12×10 tiles, 2 doors.',
  )
})

test('trimming keeps the first idea and drops the oldest question and answer', () => {
  const messages: ChatMessage[] = Array.from(
    { length: MAX_MESSAGES + 2 },
    (_, i) => ({ role: i % 2 === 0 ? 'user' : 'assistant', content: `m${i}` }),
  )
  const kept = trimHistory(messages)
  expect(kept).toHaveLength(MAX_MESSAGES)
  expect(kept.slice(0, 2).map((m) => m.content)).toEqual(['m0', 'm3'])
  expect(kept.at(-1)!.content).toBe(`m${MAX_MESSAGES + 1}`)
  expect(trimHistory(messages.slice(0, 3))).toEqual(messages.slice(0, 3))
})

test('a half-set size does not count as every field set', () => {
  const spec: SpecDraft = {
    theme: 'library',
    mood: 'creepy',
    kit: 'dungeon',
    width: 20,
    height: 14,
    doors: 1,
    objects: [],
    rules: [],
  }
  expect(allSet(spec)).toBe(true)
  expect(allSet({ ...spec, height: null })).toBe(false)
  expect(allSet({ ...spec, rules: undefined })).toBe(false)
})
