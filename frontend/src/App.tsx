import { useRef, useState } from 'react'
import {
  exportTiled,
  generate,
  validate,
  type Explanation,
  type GameMap,
  type MapSpec,
} from './api/client'
import Interview from './features/interview/Interview'
import MapEditor from './features/editor/MapEditor'
import ViolationList from './features/violations/ViolationList'
import './App.css'

type Screen = 'interview' | 'editor'

// Composes the features. Features never import each other; shared state lives here.
export default function App() {
  const [screen, setScreen] = useState<Screen>('interview')
  // Start over remounts the interview with this key, so its chat and draft start empty.
  const [session, setSession] = useState(0)
  const [spec, setSpec] = useState<MapSpec | null>(null)
  const [map, setMap] = useState<GameMap | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  // Counts generated maps. A new map remounts the editor, so no hover or selection carries over.
  const [generation, setGeneration] = useState(0)
  const [explanations, setExplanations] = useState<Explanation[]>([])
  // Two kinds of error, so neither can hide or clear the other. A validation error belongs to
  // the map on screen. An action error belongs to the last Generate or export.
  const [validateError, setValidateError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  // True while a map is being made. Edits and a second Generate are ignored until it's done.
  const [busy, setBusy] = useState(false)
  // Each edit, and each new map once it arrives, takes the next number. Only the newest one's
  // reply is shown, so a slow reply for an older map can't replace the current issues.
  const latest = useRef(0)
  // Bumped by Start over, so a map still being made for the old session is dropped.
  const current = useRef(0)

  async function handleGenerate(nextSpec: MapSpec) {
    if (busy) return
    const mine = current.current
    setBusy(true)
    setActionError(null)
    try {
      // Math.random only picks the seed; the backend generator is deterministic given it.
      const nextSeed = Math.floor(Math.random() * 2 ** 31)
      const result = await generate(nextSpec, nextSeed)
      if (mine !== current.current) return
      // Only now is the old map replaced, so a failed Generate keeps its pending replies.
      latest.current += 1
      setSpec(nextSpec)
      setSeed(nextSeed)
      setMap(result.map)
      setGeneration((n) => n + 1)
      setExplanations(result.explanations)
      setValidateError(null)
      setScreen('editor')
    } catch (e) {
      if (mine === current.current) setActionError(String(e))
    } finally {
      if (mine === current.current) setBusy(false)
    }
  }

  function startOver() {
    current.current += 1
    latest.current += 1 // Drops replies for the old map's edits.
    setSession((n) => n + 1)
    setScreen('interview')
    setSpec(null)
    setMap(null)
    setSeed(null)
    setExplanations([])
    setValidateError(null)
    setActionError(null)
    setBusy(false)
  }

  async function handleEdit(next: GameMap) {
    if (!spec || busy) return
    const request = (latest.current += 1)
    setMap(next)
    try {
      const result = await validate(spec, next)
      if (request !== latest.current) return
      setExplanations(result.explanations)
      setValidateError(null)
    } catch (e) {
      if (request === latest.current) setValidateError(String(e))
    }
  }

  async function handleExport() {
    if (!map) return
    setActionError(null)
    try {
      const tiled = await exportTiled(map)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([JSON.stringify(tiled, null, 2)]))
      a.download = 'map.tmj'
      a.click()
    } catch (e) {
      setActionError(String(e))
    }
  }

  return (
    <main className="app">
      <header className="topbar">
        <h1>TileMuse</h1>
        <nav className="steps" aria-label="Steps">
          <button
            aria-current={screen === 'interview' ? 'step' : undefined}
            onClick={() => setScreen('interview')}
          >
            1 · Interview
          </button>
          <button
            aria-current={screen === 'editor' ? 'step' : undefined}
            disabled={!map}
            onClick={() => setScreen('editor')}
          >
            2 · Edit
          </button>
        </nav>
        <button className="start-over" onClick={startOver}>
          Start over
        </button>
      </header>
      {actionError && <p role="alert">{actionError}</p>}
      {validateError && <p role="alert">{validateError}</p>}
      {/* Hidden, not unmounted, so going back keeps the chat and the draft. */}
      <div className="screen" hidden={screen !== 'interview'}>
        <Interview
          key={session}
          onGenerate={handleGenerate}
          generating={busy}
        />
      </div>
      {map && (
        <div className="screen editor-screen" hidden={screen !== 'editor'}>
          <p>Seed: {seed}</p>
          <MapEditor key={generation} map={map} onChange={handleEdit} />
          <button onClick={handleExport}>Export Tiled JSON</button>
          <ViolationList explanations={explanations} />
        </div>
      )}
    </main>
  )
}
