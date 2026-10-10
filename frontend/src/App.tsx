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
  // null means the current map's issues are unknown (validation failed).
  const [explanations, setExplanations] = useState<Explanation[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Bumped for every new map, so a late validation of an older map is ignored.
  const mapVersion = useRef(0)

  async function handleIdea(idea: string) {
    setBusy(true)
    setError(null)
    try {
      const nextSpec = await getSpec(idea)
      // Math.random only picks the seed; the backend generator is deterministic given it.
      const seed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, seed)
      mapVersion.current++
      setSpec(nextSpec)
      setMap(result.map)
      setExplanations(result.explanations)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleEdit(next: GameMap) {
    if (!spec || busy) return // a pending generation would overwrite the edit
    setMap(next)
    const version = ++mapVersion.current
    try {
      const result = await validate(spec, next)
      if (version !== mapVersion.current) return
      setExplanations(result.explanations)
      setError(null)
    } catch (e) {
      if (version !== mapVersion.current) return
      setExplanations(null)
      setError(`Validation failed, issues are unknown: ${e}`)
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
      setTimeout(() => URL.revokeObjectURL(a.href)) // same-tick revoke can cancel the download
    } catch (e) {
      setError(String(e))
    }
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
