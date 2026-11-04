import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  interview,
  type MapSpec,
  type Question,
  type SpecDraft,
} from '../../api/client'
import { MAX_MESSAGE, trimHistory } from './fields'
import SpecPanel from './SpecPanel'
import './Interview.css'

type Turn =
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; question: Question | null }

type Props = {
  onGenerate: (spec: MapSpec) => void
  // True while App is making a map from the spec.
  generating: boolean
}

// The interview screen: the chat on the left, the design spec it fills in on the right.
export default function Interview({ onGenerate, generating }: Props) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState<SpecDraft>({})
  const [spec, setSpec] = useState<MapSpec | null>(null)
  // Claude's message so far while a turn is running, and null otherwise.
  const [streaming, setStreaming] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const composer = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLLIElement>(null)
  const running = useRef<AbortController | null>(null)

  // Leaving the screen for good (Start over) stops the turn in flight.
  useEffect(() => () => running.current?.abort(), [])

  // Keep the newest message in view as turns arrive and text streams in.
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [turns, streaming])

  const pending = streaming !== null
  const last = turns.at(-1)
  const question = last?.role === 'assistant' ? last.question : null

  async function send(text: string) {
    const content = text.trim()
    if (!content || pending) return
    const before = turns
    const asked: Turn[] = [...turns, { role: 'user', content }]
    const controller = new AbortController()
    running.current = controller
    setTurns(asked)
    setInput('')
    setError(null)
    setStreaming('')
    try {
      const history = asked.map(({ role, content }) => ({ role, content }))
      const done = await interview(
        trimHistory(history),
        draft,
        (piece) => setStreaming((s) => (s ?? '') + piece),
        controller.signal,
      )
      setTurns([
        ...asked,
        { role: 'assistant', content: done.message, question: done.question },
      ])
      setDraft(done.draft)
      setSpec(done.spec)
    } catch (e) {
      if (controller.signal.aborted) return
      // The turn didn't happen: take the answer back so it can be sent again.
      setTurns(before)
      setInput(content)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (!controller.signal.aborted) setStreaming(null)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  return (
    <div className="interview">
      <section className="chat" aria-label="Interview">
        <ol className="chat-log" role="log" aria-live="polite">
          {turns.length === 0 && (
            <li className="chat-intro">
              Describe the map you have in mind, even roughly. I'll ask a few
              questions to turn it into a design spec.
            </li>
          )}
          {turns.map((turn, i) =>
            turn.role === 'user' ? (
              <li key={i} className="bubble user">
                {turn.content}
              </li>
            ) : (
              <li key={i} className="bubble assistant">
                <p>{turn.content}</p>
                {turn.question && (
                  <QuestionChips
                    question={turn.question}
                    // The reply after this question, if any, to mark the chip that was chosen.
                    answer={turns[i + 1]?.content}
                    open={i === turns.length - 1 && !pending}
                    onPick={send}
                    onOther={() => composer.current?.focus()}
                  />
                )}
              </li>
            ),
          )}
          {pending && (
            <li className="bubble assistant pending">
              <p>{streaming || 'Thinking…'}</p>
            </li>
          )}
          <li ref={end} aria-hidden className="chat-end" />
        </ol>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            ref={composer}
            aria-label="Message"
            rows={1}
            maxLength={MAX_MESSAGE}
            placeholder={
              turns.length === 0
                ? 'e.g. A creepy abandoned library where the player sneaks past guards'
                : 'Pick an option or type your own answer…'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter adds a line.
              if (
                e.key === 'Enter' &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault()
                void send(input)
              }
            }}
          />
          <button
            type="submit"
            className="primary"
            disabled={pending || !input.trim()}
          >
            Send
          </button>
        </form>
      </section>
      <SpecPanel
        draft={draft}
        question={question}
        spec={spec}
        generating={generating}
        onGenerate={onGenerate}
      />
    </div>
  )
}

type ChipsProps = {
  question: Question
  answer: string | undefined
  // Only the latest question takes an answer, and not while a turn runs.
  open: boolean
  onPick: (answer: string) => void
  onOther: () => void
}

function QuestionChips({
  question,
  answer,
  open,
  onPick,
  onOther,
}: ChipsProps) {
  return (
    <>
      <p className="reason">{question.reason}</p>
      <div className="chips" role="group" aria-label="Suggested answers">
        {question.suggestions.map((s) => (
          <button
            key={s}
            type="button"
            className="chip"
            aria-pressed={answer === s}
            disabled={!open}
            onClick={() => onPick(s)}
          >
            {s}
          </button>
        ))}
        {open && (
          <button type="button" className="chip other" onClick={onOther}>
            Something else…
          </button>
        )}
      </div>
    </>
  )
}
