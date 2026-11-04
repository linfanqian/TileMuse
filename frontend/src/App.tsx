import { useRef, useState } from 'react'
import {
  exportMap,
  generate,
  validate,
  type Explanation,
  type GameMap,
  type MapSpec,
  type Violation,
} from './api/client'
import Interview from './features/interview/Interview'
import MapEditor from './features/editor/MapEditor'
import ViolationList from './features/violations/ViolationList'
import './App.css'

type Screen = 'interview' | 'editor'

const REVOKE_AFTER_MS = 60_000

// Names a violation by its rule, place, and object kind, but not its counts, so a hard-rule
// problem the map already had still matches after an edit changes how many objects are missing.
const sameProblem = (v: Violation) =>
  JSON.stringify([v.code, v.x, v.y, v.details.kind])

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
  // The issues of the map on screen. An edit is checked against its violations.
  const [violations, setViolations] = useState<Violation[]>([])
  const [explanations, setExplanations] = useState<Explanation[]>([])
  // Why the last edit was undone. Cleared by the next edit or a new map.
  const [undone, setUndone] = useState<string | null>(null)
  // Two kinds of error, so neither can hide or clear the other. A validation error belongs to
  // the map on screen. An action error belongs to the last Generate or export.
  const [validateError, setValidateError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  // True while a map is being made. Edits and a second Generate are ignored until it's done.
  const [busy, setBusy] = useState(false)
  // True while an edit is being checked. Edits wait for it, so each one is checked against a
  // map whose issues are known, and an undo never drops a later edit. Export waits too, so it
  // never saves an edit that may be undone. It is state, not a ref, so it turns false only
  // when the checked map is on screen.
  const [checking, setChecking] = useState(false)
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
      setChecking(false) // The old map's check no longer holds up edits.
      setSpec(nextSpec)
      setSeed(nextSeed)
      setMap(result.map)
      setGeneration((n) => n + 1)
      // A new map has no earlier map to go back to, so any hard-rule problem is listed here.
      // The generator keeps the hard rules, so there shouldn't be one.
      setViolations(result.violations)
      setExplanations(result.explanations)
      setUndone(null)
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
    setChecking(false)
    setSession((n) => n + 1)
    setScreen('interview')
    setSpec(null)
    setMap(null)
    setSeed(null)
    setViolations([])
    setExplanations([])
    setUndone(null)
    setValidateError(null)
    setActionError(null)
    setBusy(false)
  }

  // The edit shows at once. If it breaks a hard rule the map didn't already break, it is
  // undone and the toast says why. A problem the map already had doesn't block edits.
  async function handleEdit(next: GameMap) {
    if (!spec || !map || busy || checking) return
    const before = map
    const request = (latest.current += 1)
    setChecking(true)
    setMap(next)
    setUndone(null)
    try {
      const result = await validate(spec, next)
      if (request !== latest.current) return
      const known = new Set(
        violations.filter((v) => v.blocking).map(sameProblem),
      )
      const broken = result.violations.findIndex(
        (v) => v.blocking && !known.has(sameProblem(v)),
      )
      if (broken !== -1) {
        // Back to the map before the edit, whose issues are still the ones shown.
        setMap(before)
        setUndone(result.explanations[broken].text)
      } else {
        setViolations(result.violations)
        setExplanations(result.explanations)
      }
      setValidateError(null)
    } catch (e) {
      // An edit that can't be checked is undone too. Kept, it could break a hard rule that
      // later checks would take as new, and undo every edit after it.
      if (request !== latest.current) return
      setMap(before)
      setValidateError(`Edit undone, since it couldn't be checked. ${e}`)
    } finally {
      // A new map has already cleared it, and an edit on that map may be checking now.
      if (request === latest.current) setChecking(false)
    }
  }

  async function handleExport() {
    if (!map || !spec || checking) return
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
      {undone && <p role="alert">Edit undone. {undone}</p>}
      {/* Hidden, not unmounted, so going back keeps the chat and the draft. */}
      <div className="screen" hidden={screen !== 'interview'}>
        <Interview
          key={session}
          onGenerate={handleGenerate}
          generating={busy}
        />
      </div>
      {map && spec && (
        <div className="screen editor-screen" hidden={screen !== 'editor'}>
          <p>Seed: {seed}</p>
          <MapEditor
            key={generation}
            map={map}
            kit={spec.kit}
            onChange={handleEdit}
          />
          <button onClick={handleExport} disabled={checking}>
            Export for Tiled
          </button>
          <ViolationList explanations={explanations} />
        </div>
      )}
    </main>
  )
}
