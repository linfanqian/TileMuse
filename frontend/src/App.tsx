import { useState } from 'react'
import {
  exportTiled,
  generate,
  getSpec,
  validate,
  type Explanation,
  type GameMap,
  type MapSpec,
} from './api/client'
import ChatPanel from './features/chat/ChatPanel'
import MapEditor from './features/editor/MapEditor'
import ViolationList from './features/violations/ViolationList'

// Composes the features. Features never import each other; shared state lives here.
export default function App() {
  const [spec, setSpec] = useState<MapSpec | null>(null)
  const [map, setMap] = useState<GameMap | null>(null)
  const [explanations, setExplanations] = useState<Explanation[]>([])
  const [error, setError] = useState<string | null>(null)

  async function handleIdea(idea: string) {
    setError(null)
    try {
      const nextSpec = await getSpec(idea)
      // Math.random only picks the seed; the backend generator is deterministic given it.
      const seed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, seed)
      setSpec(nextSpec)
      setMap(result.map)
      setExplanations(result.explanations)
    } catch (e) {
      setError(String(e))
    }
  }

  async function handleEdit(next: GameMap) {
    if (!spec) return
    setMap(next)
    try {
      setExplanations((await validate(spec, next)).explanations)
    } catch (e) {
      setError(String(e))
    }
  }

  async function handleExport() {
    if (!map) return
    try {
      const tiled = await exportTiled(map)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([JSON.stringify(tiled, null, 2)]))
      a.download = 'map.tmj'
      a.click()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <main>
      <h1>TileMuse</h1>
      <ChatPanel onSubmit={handleIdea} />
      {error && <p role="alert">{error}</p>}
      {map && (
        <>
          <MapEditor map={map} onChange={handleEdit} />
          <button onClick={handleExport}>Export Tiled JSON</button>
          <ViolationList explanations={explanations} />
        </>
      )}
    </main>
  )
}
