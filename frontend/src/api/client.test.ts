import { afterEach, expect, test, vi } from 'vitest'
import { errorDetail, validate, type GameMap } from './client'

const map: GameMap = { width: 1, height: 1, tiles: [[0]], objects: [] }

afterEach(() => {
  vi.unstubAllGlobals()
})

test('errorDetail reads string and list details', () => {
  expect(errorDetail({ detail: 'map size does not match spec' })).toBe(
    'map size does not match spec',
  )
  expect(errorDetail({ detail: [{ msg: 'a' }, { msg: 'b' }] })).toBe('a; b')
  expect(errorDetail({ detail: [{}] })).toBeNull()
  expect(errorDetail(null)).toBeNull()
})

test('a failed request reports the backend detail', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'map size does not match spec' }), {
        status: 422,
      }),
    ),
  )
  await expect(validate({ width: 4, height: 4 }, map)).rejects.toThrow(
    '/api/validate failed: 422 (map size does not match spec)',
  )
})

test('a failed request without JSON still reports the status', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('oops', { status: 500 })),
  )
  await expect(validate({ width: 4, height: 4 }, map)).rejects.toThrow(
    /failed: 500$/,
  )
})
