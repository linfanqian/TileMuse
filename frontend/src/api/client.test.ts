import { afterEach, expect, test, vi } from 'vitest'
import { exportMap, interview, type GameMap, type MapSpec } from './client'

// A streamed response whose body arrives in these chunks, which may split lines.
function respond(chunks: string[], status = 200) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(body, { status })),
  )
}

const done = {
  type: 'done',
  message: 'How big?',
  question: null,
  draft: {},
  spec: null,
}

afterEach(() => vi.unstubAllGlobals())

const run = (onText = vi.fn()) =>
  interview([{ role: 'user', content: 'a room' }], {}, onText)

test('streams text pieces, then resolves with the finished turn', async () => {
  const lines = [
    JSON.stringify({ type: 'text', text: 'How ' }),
    JSON.stringify({ type: 'text', text: 'big?' }),
    JSON.stringify(done),
  ].join('\n')
  // Split mid-line to check that partial lines are buffered.
  respond([lines.slice(0, 10), lines.slice(10), '\n'])
  const onText = vi.fn()
  await expect(run(onText)).resolves.toEqual(done)
  expect(onText.mock.calls).toEqual([['How '], ['big?']])
  const [path, init] = vi.mocked(fetch).mock.calls[0]
  expect(path).toBe('/api/interview')
  expect(JSON.parse(init!.body as string)).toEqual({
    messages: [{ role: 'user', content: 'a room' }],
    draft: {},
  })
})

test('a last line without a newline still counts', async () => {
  respond([JSON.stringify(done)])
  await expect(run()).resolves.toEqual(done)
})

test('an error event rejects with its message', async () => {
  respond([
    JSON.stringify({ type: 'text', text: 'How' }) + '\n',
    JSON.stringify({ type: 'error', message: 'Try again.' }) + '\n',
  ])
  await expect(run()).rejects.toThrow('Try again.')
})

test('a stream that ends without a result rejects', async () => {
  respond([JSON.stringify({ type: 'text', text: 'How' }) + '\n'])
  await expect(run()).rejects.toThrow('cut off')
})

test('a failed request rejects with its status', async () => {
  respond(['{"detail":"bad"}'], 422)
  const error = vi.spyOn(console, 'error').mockImplementation(() => {})
  await expect(run()).rejects.toThrow(
    'The interview request failed (422). Try again, or start over.',
  )
  expect(error).toHaveBeenCalledWith(
    '/api/interview failed:',
    422,
    '{"detail":"bad"}',
  )
  error.mockRestore()
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
