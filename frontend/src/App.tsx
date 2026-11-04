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
  const [seed, setSeed] = useState<number | null>(null)
  // Counts generated maps. A new map remounts the editor, so no hover or selection carries over.
  const [generation, setGeneration] = useState(0)
  const [explanations, setExplanations] = useState<Explanation[]>([])
  // Where the error came from, so a good validation clears only its own error.
  const [error, setError] = useState<{
    text: string
    from: 'validate' | 'other'
  } | null>(null)
  // True while a map is being made. Edits and a second Generate are ignored until it's done.
  const [busy, setBusy] = useState(false)
  // Each edit, and each new map once it arrives, takes the next number. Only the newest one's
  // reply is shown, so a slow reply for an older map can't replace the current issues.
  const latest = useRef(0)

  async function handleIdea(idea: string) {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const nextSpec = await getSpec(idea)
      // Math.random only picks the seed; the backend generator is deterministic given it.
      const nextSeed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, nextSeed)
      // Only now is the old map replaced, so a failed Generate keeps its pending replies.
      latest.current += 1
      setSpec(nextSpec)
      setSeed(nextSeed)
      setMap(result.map)
      setGeneration((n) => n + 1)
      setExplanations(result.explanations)
    } catch (e) {
      setError({ text: String(e), from: 'other' })
    } finally {
      setBusy(false)
    }
  }

  async function handleEdit(next: GameMap) {
    if (!spec || busy) return
    const request = (latest.current += 1)
    setMap(next)
    try {
      const result = await validate(spec, next)
      if (request !== latest.current) return
      setExplanations(result.explanations)
      setError((old) => (old?.from === 'validate' ? null : old))
    } catch (e) {
      if (request === latest.current)
        setError({ text: String(e), from: 'validate' })
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
      setError({ text: String(e), from: 'other' })
    }
  }

  return (
    <main>
      <h1>TileMuse</h1>
      <ChatPanel onSubmit={handleIdea} busy={busy} />
      {error && <p role="alert">{error.text}</p>}
      {map && (
        <>
          <p>Seed: {seed}</p>
          <MapEditor key={generation} map={map} onChange={handleEdit} />
          <button onClick={handleExport}>Export Tiled JSON</button>
          <ViolationList explanations={explanations} />
        </>
      )}
    </main>
  )
}
