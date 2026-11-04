import { afterEach, expect, test, vi } from 'vitest'
import { exportMap, type GameMap, type MapSpec } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

const spec = { kit: 'town' } as MapSpec
const map = { width: 1, height: 1, tiles: [[0]], objects: [] } as GameMap

test('exportMap sends the spec and map and returns a typed zip', async () => {
  const fetch = vi.fn(async () => new Response('zip bytes'))
  vi.stubGlobal('fetch', fetch)
  const zip = await exportMap(spec, map)
  expect(zip.type).toBe('application/zip')
  expect(await zip.text()).toBe('zip bytes')
  const [path, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
  expect(path).toBe('/api/export')
  expect(JSON.parse(init.body as string)).toEqual({ spec, map })
})

test('exportMap fails with the status when the backend does', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('bad map', { status: 422 })),
  )
  await expect(exportMap(spec, map)).rejects.toThrow('422 bad map')
})
