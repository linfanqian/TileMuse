import { useRef, useState, type FormEvent } from 'react'
import { MAX_SEED, parseSeed, randomSeed } from './seed'
import './SeedDialog.css'

type Props = {
  seed: number
  onCancel: () => void
  onRegenerate: (seed: number) => void
}

// Change the seed, or roll a random one, and make the map again from the same spec.
export default function SeedDialog({ seed, onCancel, onRegenerate }: Props) {
  const [text, setText] = useState(String(seed))
  const next = parseSeed(text)
  // Where the last press began. A drag from the input that ends outside isn't a click outside.
  const pressedOutside = useRef(false)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== null) onRegenerate(next)
  }

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(e) =>
        (pressedOutside.current = e.target === e.currentTarget)
      }
      onClick={(e) => {
        if (pressedOutside.current && e.target === e.currentTarget) onCancel()
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="seed-dialog-title"
        className="dialog"
        onSubmit={submit}
        onKeyDown={(e) => e.key === 'Escape' && onCancel()}
      >
        <h2 id="seed-dialog-title">Regenerate the map</h2>
        <p>
          The same spec and seed always make the same map. Change the seed for a
          new layout. Edits to this map are lost.
        </p>
        <div className="seed-field">
          <label htmlFor="seed-dialog-input">Seed</label>
          <input
            id="seed-dialog-input"
            autoFocus
            inputMode="numeric"
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-invalid={next === null}
          />
          <button type="button" onClick={() => setText(String(randomSeed()))}>
            Random
          </button>
        </div>
        {next === null && (
          <p className="error">Use a whole number from 0 to {MAX_SEED}.</p>
        )}
        <div className="dialog-actions">
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={next === null}>
            Regenerate
          </button>
        </div>
      </form>
    </div>
  )
}
