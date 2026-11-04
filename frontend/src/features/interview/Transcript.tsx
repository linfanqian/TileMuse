import type { Question } from '../../api/client'
import './Interview.css'

export type Turn =
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; question: Question | null }

// The interview's chat, read-only, as it stood when the map was made.
export default function Transcript({ turns }: { turns: Turn[] }) {
  if (turns.length === 0) return <p className="chat-intro">No chat yet.</p>
  return (
    <ol className="transcript" aria-label="Chat">
      {turns.map((turn, i) => (
        <li key={i} className={`bubble ${turn.role}`}>
          <p>{turn.content}</p>
        </li>
      ))}
    </ol>
  )
}
