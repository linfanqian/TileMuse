import { useState, type FormEvent } from 'react'

type Props = {
  onSubmit: (idea: string) => void
}

export default function ChatPanel({ onSubmit }: Props) {
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
      <button type="submit">Generate</button>
    </form>
  )
}
