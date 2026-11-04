import { useEffect, useRef, useState } from 'react'
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
import SpecView from './features/interview/SpecView'
import Transcript, { type Turn } from './features/interview/Transcript'
import MapEditor from './features/editor/MapEditor'
import SideRail from './features/rail/SideRail'
import SeedDialog from './features/seed/SeedDialog'
import { randomSeed } from './features/seed/seed'
import ViolationList from './features/violations/ViolationList'
import './App.css'

type Screen = 'interview' | 'editor'

const REVOKE_AFTER_MS = 60_000

// Names a violation by its rule, place, and object kind, but not its counts, so a hard-rule
// problem the map already had still matches after an edit changes how many objects are missing.
const sameProblem = (v: Violation) =>
  JSON.stringify([v.code, v.x, v.y, v.details.kind])

// A map before a kept edit, with the issues it had, so Undo can go back to it.
type Kept = {
  map: GameMap
  violations: Violation[]
  explanations: Explanation[]
}

// Composes the features. Features never import each other; shared state lives here.
export default function App() {
  const [screen, setScreen] = useState<Screen>('interview')
  // Start over remounts the interview with this key, so its chat and draft start empty.
  const [session, setSession] = useState(0)
  const [spec, setSpec] = useState<MapSpec | null>(null)
  const [map, setMap] = useState<GameMap | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  // True while the seed dialog is open, to regenerate the map with a chosen seed.
  const [seedOpen, setSeedOpen] = useState(false)
  // The interview chat that led to the map, shown in the editor's Chat tab.
  const [chat, setChat] = useState<Turn[]>([])
  // The cell an issue's "Show on map" points at. Cleared when the issues change.
  const [shown, setShown] = useState<{ x: number; y: number } | null>(null)
  // Counts generated maps. A new map remounts the editor, so no hover or selection carries over.
  const [generation, setGeneration] = useState(0)
  // The issues of the map on screen. An edit is checked against its violations.
  const [violations, setViolations] = useState<Violation[]>([])
  const [explanations, setExplanations] = useState<Explanation[]>([])
  // Why the last edit was undone. Cleared by the next edit or a new map.
  const [undone, setUndone] = useState<string | null>(null)
  // The maps before each kept edit, oldest first. Undo pops the newest. Cleared by a new map.
  const [kept, setKept] = useState<Kept[]>([])
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

  // From the interview, with its chat and a random seed. The seed dialog passes its seed and
  // no chat, so the old chat stays.
  async function handleGenerate(
    nextSpec: MapSpec,
    { turns, seed: chosen }: { turns?: Turn[]; seed?: number } = {},
  ) {
    if (busy) return
    const mine = current.current
    setBusy(true)
    setActionError(null)
    try {
      const nextSeed = chosen ?? randomSeed()
      const result = await generate(nextSpec, nextSeed)
      if (mine !== current.current) return
      // Only now is the old map replaced, so a failed Generate keeps its pending replies.
      latest.current += 1
      setChecking(false) // The old map's check no longer holds up edits.
      setSpec(nextSpec)
      setSeed(nextSeed)
      setMap(result.map)
      if (turns) setChat(turns)
      setShown(null)
      setGeneration((n) => n + 1)
      // A new map has no earlier map to go back to, so any hard-rule problem is listed here.
      // The generator keeps the hard rules unless the room is too full to join every door.
      setViolations(result.violations)
      setExplanations(result.explanations)
      setUndone(null)
      setKept([])
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
    setSeedOpen(false)
    setChat([])
    setShown(null)
    setViolations([])
    setExplanations([])
    setUndone(null)
    setKept([])
    setValidateError(null)
    setActionError(null)
    setBusy(false)
  }

  // Steps back to the map before the last kept edit, with its issues. Not while an edit is
  // being checked, since its reply would land on the restored map.
  function undo() {
    const last = kept.at(-1)
    if (!last || checking || busy) return
    setKept(kept.slice(0, -1))
    setMap(last.map)
    setViolations(last.violations)
    setExplanations(last.explanations)
    setShown(null)
    setUndone(null)
    setValidateError(null)
  }

  // Ctrl+Z, or Cmd+Z on macOS, undoes too. Text fields keep their own undo.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (screen !== 'editor' || e.shiftKey || e.altKey) return
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z') return
      const target = e.target
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))
      )
        return
      e.preventDefault()
      undo()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

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
        setKept((k) => [...k, { map: before, violations, explanations }])
        setViolations(result.violations)
        setExplanations(result.explanations)
        setShown(null) // The issue it pointed at may be gone.
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
        {screen === 'editor' && map && spec && (
          <div className="map-actions">
            <span className="seed">
              Seed{' '}
              <button
                className="seed-value"
                title="Change the seed to regenerate the map"
                aria-label={`Seed ${seed}. Change it to regenerate the map.`}
                onClick={() => setSeedOpen(true)}
                disabled={busy}
              >
                {seed}
              </button>
            </span>
            <button
              className="undo"
              title="Undo the last kept edit (Ctrl+Z)"
              onClick={undo}
              disabled={kept.length === 0 || checking || busy}
            >
              Undo
            </button>
            <button
              className="primary"
              onClick={handleExport}
              disabled={checking}
            >
              Export for Tiled
            </button>
          </div>
        )}
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
          onGenerate={(ready, turns) => void handleGenerate(ready, { turns })}
          generating={busy}
        />
      </div>
      {map && spec && (
        <div className="screen editor-screen" hidden={screen !== 'editor'}>
          <SideRail
            label="Map details"
            tabs={[
              { name: 'Chat', content: <Transcript turns={chat} /> },
              { name: 'Spec', content: <SpecView spec={spec} /> },
            ]}
          />
          <section className="workspace" aria-label="Map">
            <MapEditor
              key={generation}
              map={map}
              kit={spec.kit}
              onChange={handleEdit}
              highlight={shown}
            />
            {undone && (
              <p role="alert" className="toast">
                <strong>Edit undone.</strong> {undone}
              </p>
            )}
          </section>
          <aside className="issues-panel">
            <ViolationList
              violations={violations}
              explanations={explanations}
              onShow={setShown}
            />
          </aside>
        </div>
      )}
      {seedOpen && spec && seed !== null && (
        <SeedDialog
          seed={seed}
          onCancel={() => setSeedOpen(false)}
          onRegenerate={(chosen) => {
            setSeedOpen(false)
            void handleGenerate(spec, { seed: chosen })
          }}
        />
      )}
    </main>
  )
}
