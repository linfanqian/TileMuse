import { useState, type FormEvent } from 'react'

type Props = {
  onSubmit: (idea: string) => void
  // True while a map is being made, so the idea can't be sent twice.
  busy?: boolean
}

export default function ChatPanel({ onSubmit, busy = false }: Props) {
  const [idea, setIdea] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!busy && idea.trim()) onSubmit(idea.trim())
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        aria-label="Map idea"
        placeholder="Describe your map idea"
        value={idea}
        onChange={(e) => setIdea(e.target.value)}
      />
      <button type="submit" disabled={busy}>
        {busy ? 'Generating…' : 'Generate'}
      </button>
    </form>
  )
}
