import { useState, type FormEvent } from 'react'

type Props = {
  onSubmit: (idea: string) => void
  busy?: boolean
}

export default function ChatPanel({ onSubmit, busy = false }: Props) {
  const [idea, setIdea] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (idea.trim()) onSubmit(idea.trim())
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
        Generate
      </button>
    </form>
  )
}
