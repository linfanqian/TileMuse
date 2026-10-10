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
  // Generation/export errors and validation errors are separate so clearing one never hides the other.
  const [error, setError] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  // Request counters so late responses are ignored. Editing never cancels a pending
  // generation; a newly generated map cancels pending validations of the old one.
  const latestGenerate = useRef(0)
  const latestMap = useRef(0)

  async function handleIdea(idea: string) {
    setBusy(true)
    setError(null)
    const id = ++latestGenerate.current
    try {
      const nextSpec = await getSpec(idea)
      const seed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, seed)
      if (id !== latestGenerate.current) return
      latestMap.current++
      setSpec(nextSpec)
      setMap(result.map)
      setExplanations(result.explanations)
      setValidationError(null)
    } catch (e) {
      if (id === latestGenerate.current) setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleEdit(next: GameMap) {
    if (!spec) return
    setMap(next)
    const id = ++latestMap.current
    try {
      const result = await validate(spec, next)
      if (id !== latestMap.current) return
      setExplanations(result.explanations)
      setValidationError(null)
    } catch (e) {
      if (id !== latestMap.current) return
      setExplanations(null)
      setValidationError(`Validation failed, issues are unknown: ${e}`)
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
          {validationError && <p role="alert">{validationError}</p>}
          {explanations && <ViolationList explanations={explanations} />}
        </>
      )}
    </main>
  )
}
