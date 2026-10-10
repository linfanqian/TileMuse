// Typed wrappers for the backend API. Regenerate schema.d.ts with `npm run gen:api`.
import type { components } from './schema'

type Schemas = components['schemas']
export type MapSpec = Schemas['MapSpec']
export type GameMap = Schemas['GameMap']
export type Tile = Schemas['Tile']
export type Violation = Schemas['Violation']
export type Explanation = Schemas['Explanation']
export type GenerateResult = Schemas['GenerateResult']
export type ValidationResult = Schemas['ValidationResult']

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json() as Promise<T>
}

export const getSpec = (idea: string) => post<MapSpec>('/spec', { idea })

export const generate = (spec: MapSpec, seed: number) =>
  post<GenerateResult>('/generate', { spec, seed })

export const validate = (spec: MapSpec, map: GameMap) =>
  post<ValidationResult>('/validate', { spec, map })

export const exportTiled = (map: GameMap) =>
  post<Record<string, unknown>>('/export', { map })
