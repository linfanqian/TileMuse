// Typed wrappers for the backend API. Regenerate schema.d.ts with `npm run gen:api`.
import type { components, paths } from './schema'

type Schemas = components['schemas']
export type MapSpec = Schemas['MapSpec']
export type GameMap = Schemas['GameMap']
export type ObjectKind = Schemas['ObjectKind']
export type Tile = Schemas['Tile']
export type Violation = Schemas['Violation']
export type Explanation = Schemas['Explanation']
export type GenerateResult = Schemas['GenerateResult']
export type ValidationResult = Schemas['ValidationResult']
export type SpecDraft = Schemas['SpecDraft']
export type ChatMessage = Schemas['ChatMessage']
export type Question = Schemas['Question']
export type InterviewDone = Schemas['InterviewDone']
// /api/interview streams one of these per JSON line. schema.d.ts lists the
// models but types the route's response as unknown, so the union is built here.
export type InterviewEvent =
  | Schemas['InterviewText']
  | Schemas['InterviewDone']
  | Schemas['InterviewError']

// Request and response types come from the generated schema, so a renamed route or
// field fails typecheck instead of at runtime. Only JSON routes: /api/interview streams JSON Lines.
type PostPath = {
  [P in keyof paths]: paths[P] extends {
    post: { responses: { 200: { content: { 'application/json': unknown } } } }
  }
    ? P
    : never
}[keyof paths]
type PostOp<P extends PostPath> = paths[P]['post']
type Body<P extends PostPath> =
  PostOp<P>['requestBody']['content']['application/json']
type Result<P extends PostPath> =
  PostOp<P>['responses'][200]['content']['application/json']

async function post<P extends PostPath>(
  path: P,
  body: Body<P>,
): Promise<Result<P>> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok)
    throw new Error(`${path} failed: ${res.status} ${await res.text()}`)
  return res.json() as Promise<Result<P>>
}

export const generate = (spec: MapSpec, seed: number) =>
  post('/api/generate', { spec, seed })

export const validate = (spec: MapSpec, map: GameMap) =>
  post('/api/validate', { spec, map })

export const exportTiled = (map: GameMap) => post('/api/export', { map })

/**
 * Runs one interview turn. Calls `onText` with each piece of Claude's message as it streams,
 * then resolves with the finished turn. Rejects on an error event, a failed request, or a
 * stream that ends without a result. Streamed text is only a preview: show `message` once done.
 */
export async function interview(
  messages: ChatMessage[],
  draft: SpecDraft,
  onText: (text: string) => void,
  signal?: AbortSignal,
): Promise<InterviewDone> {
  const body: Schemas['InterviewRequest'] = { messages, draft }
  const res = await fetch('/api/interview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    // The details go to the console; the chat gets a sentence the user can act on.
    console.error('/api/interview failed:', res.status, await res.text())
    throw new Error(
      `The interview request failed (${res.status}). Try again, or start over.`,
    )
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const lines = buffer.split('\n')
      // The last piece may be a partial line, unless the stream is over.
      buffer = done ? '' : lines.pop()!
      for (const line of lines) {
        if (!line.trim()) continue
        const event = JSON.parse(line) as InterviewEvent
        if (event.type === 'text') onText(event.text)
        else if (event.type === 'done') return event
        else throw new Error(event.message)
      }
      if (done) throw new Error('The interview reply was cut off. Try again.')
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}
