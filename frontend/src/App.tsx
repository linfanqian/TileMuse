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
  const [explanations, setExplanations] = useState<Explanation[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const latestValidation = useRef(0)

  async function handleIdea(idea: string) {
    setBusy(true)
    setError(null)
    try {
      const nextSpec = await getSpec(idea)
      const seed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, seed)
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
    if (!spec) return
    setMap(next)
    const id = ++latestValidation.current
    try {
      const result = await validate(spec, next)
      if (id === latestValidation.current) setExplanations(result.explanations)
    } catch (e) {
      setError(String(e))
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
          <ViolationList explanations={explanations} />
        </>
      )}
    </main>
  )
}
