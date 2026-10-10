// Typed wrappers for the backend API. Regenerate schema.d.ts with `npm run gen:api`.
import type { components, paths } from './schema'

type Schemas = components['schemas']
export type MapSpec = Schemas['MapSpec']
export type GameMap = Schemas['GameMap']
export type Tile = Schemas['Tile']
export type Violation = Schemas['Violation']
export type Explanation = Schemas['Explanation']
export type GenerateResult = Schemas['GenerateResult']
export type ValidationResult = Schemas['ValidationResult']

// Request and response types come from the generated schema, so a renamed route or
// field fails typecheck instead of at runtime.
type PostPath = {
  [P in keyof paths]: paths[P] extends { post: unknown } ? P : never
}[keyof paths]
type PostOp<P extends PostPath> = paths[P]['post']
type Body<P extends PostPath> =
  PostOp<P>['requestBody']['content']['application/json']
type Result<P extends PostPath> =
  PostOp<P>['responses'][200]['content']['application/json']

// FastAPI errors carry `detail`: a string, or a list of `{ msg }` for 422s.
export function errorDetail(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d as { msg?: unknown })?.msg)
      .filter((m): m is string => typeof m === 'string')
    if (msgs.length) return msgs.join('; ')
  }
  return null
}

async function post<P extends PostPath>(
  path: P,
  body: Body<P>,
): Promise<Result<P>> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = errorDetail(await res.json().catch(() => null))
    throw new Error(
      `${path} failed: ${res.status}${detail ? ` (${detail})` : ''}`,
    )
  }
  return res.json() as Promise<Result<P>>
}

export const getSpec = (idea: string) => post('/api/spec', { idea })

export const generate = (spec: MapSpec, seed: number) =>
  post('/api/generate', { spec, seed })

export const validate = (spec: MapSpec, map: GameMap) =>
  post('/api/validate', { spec, map })

export const exportTiled = (map: GameMap) => post('/api/export', { map })
