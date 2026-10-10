import { useRef, useState } from 'react'
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
  // null means the current map's results are unknown (validation failed).
  const [explanations, setExplanations] = useState<Explanation[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped on every map change so responses for an older map are ignored.
  const latestRequest = useRef(0)

  async function handleIdea(idea: string) {
    setBusy(true)
    setError(null)
    const id = ++latestRequest.current
    try {
      const nextSpec = await getSpec(idea)
      const seed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, seed)
      if (id !== latestRequest.current) return
      setSpec(nextSpec)
      setMap(result.map)
      setExplanations(result.explanations)
    } catch (e) {
      if (id === latestRequest.current) setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleEdit(next: GameMap) {
    if (!spec) return
    setMap(next)
    const id = ++latestRequest.current
    try {
      const result = await validate(spec, next)
      if (id !== latestRequest.current) return
      setExplanations(result.explanations)
      setError(null)
    } catch (e) {
      if (id !== latestRequest.current) return
      setExplanations(null)
      setError(`Validation failed, issues are unknown: ${e}`)
    }
  }

  async function handleExport() {
    if (!map) return
    let tiled
    try {
      tiled = await exportTiled(map)
    } catch (e) {
      setError(String(e))
      return
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(tiled, null, 2)], { type: 'application/json' }),
    )
    const a = document.createElement('a')
    a.href = url
    a.download = 'map.tmj'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main>
      <h1>TileMuse</h1>
      <ChatPanel onSubmit={handleIdea} busy={busy} />
      {error && <p role="alert">{error}</p>}
      {map && (
        <>
          <MapEditor map={map} onChange={handleEdit} />
          <button onClick={handleExport}>Export Tiled JSON</button>
          {explanations && <ViolationList explanations={explanations} />}
        </>
      )}
    </main>
  )
}
