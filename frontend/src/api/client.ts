// Typed wrappers for the backend API. Regenerate schema.d.ts with `npm run gen:api`.
import type { components, paths } from './schema'

type Schemas = components['schemas']
export type MapSpec = Schemas['MapSpec']
export type GameMap = Schemas['GameMap']
export type MapObject = Schemas['MapObject']
export type ObjectKind = Schemas['ObjectKind']
export type Tile = Schemas['Tile']
export type Violation = Schemas['Violation']
export type Explanation = Schemas['Explanation']
export type GenerateResult = Schemas['GenerateResult']
export type ValidationResult = Schemas['ValidationResult']
export type SpecDraft = Schemas['SpecDraft']
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

export const getSpec = (idea: string) => post('/api/spec', { idea })

export const generate = (spec: MapSpec, seed: number) =>
  post('/api/generate', { spec, seed })

export const validate = (spec: MapSpec, map: GameMap) =>
  post('/api/validate', { spec, map })

export const exportTiled = (map: GameMap) => post('/api/export', { map })
