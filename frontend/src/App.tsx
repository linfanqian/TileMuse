import { useRef, useState } from 'react'
import {
  exportMap,
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

const REVOKE_AFTER_MS = 60_000

// Composes the features. Features never import each other; shared state lives here.
export default function App() {
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

  async function handleIdea(idea: string) {
    if (busy) return
    setBusy(true)
    setActionError(null)
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
      setValidateError(null)
    } catch (e) {
      setActionError(String(e))
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
      setValidateError(null)
    } catch (e) {
      if (request === latest.current) setValidateError(String(e))
    }
  }

  async function handleExport() {
    if (!map || !spec) return
    setActionError(null)
    try {
      const url = URL.createObjectURL(await exportMap(spec, map))
      const a = document.createElement('a')
      a.href = url
      a.download = 'tilemuse-map.zip'
      a.click()
      // Some browsers, Safari among them, read the file after the click returns, so the URL
      // is freed a minute later instead of right away.
      setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS)
    } catch (e) {
      setActionError(String(e))
    }
  }

  return (
    <main>
      <h1>TileMuse</h1>
      <ChatPanel onSubmit={handleIdea} busy={busy} />
      {actionError && <p role="alert">{actionError}</p>}
      {validateError && <p role="alert">{validateError}</p>}
      {map && (
        <>
          <p>Seed: {seed}</p>
          <MapEditor key={generation} map={map} onChange={handleEdit} />
          <button onClick={handleExport}>Export for Tiled</button>
          <ViolationList explanations={explanations} />
        </>
      )}
    </main>
  )
}
