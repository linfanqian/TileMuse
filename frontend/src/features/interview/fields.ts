// Pure helpers for the interview: what the spec panel shows, and what history is sent.
import type { ChatMessage, Question, SpecDraft } from '../../api/client'

type Field = Question['field']
type Rule = NonNullable<SpecDraft['rules']>[number]

// Match MAX_MESSAGES and MAX_MESSAGE in backend/app/api.py and interview.py.
export const MAX_MESSAGES = 39
export const MAX_MESSAGE = 2000

export type Status = 'ready' | 'asking' | 'next'

export type Row = {
  label: string
  value: string
  status: Status
}

// One row per spec field, except width and height, which share the Size row.
const ROWS: { label: string; fields: Field[] }[] = [
  { label: 'Theme', fields: ['theme'] },
  { label: 'Mood', fields: ['mood'] },
  { label: 'Tile kit', fields: ['kit'] },
  { label: 'Size', fields: ['width', 'height'] },
  { label: 'Doors', fields: ['doors'] },
  { label: 'Objects', fields: ['objects'] },
  { label: 'Layout rules', fields: ['rules'] },
]

// Code names like player_spawn, shown as words.
const plain = (name: string) => name.replaceAll('_', ' ')

function describeRule(rule: Rule): string {
  if (rule.type === 'max_density')
    return `at most ${Math.round(rule.max * 100)}% of the floor filled`
  if (rule.a === rule.b) return `${plain(rule.a)}s ≥ ${rule.tiles} tiles apart`
  return `${plain(rule.a)} ≥ ${rule.tiles} tiles from ${plain(rule.b)}`
}

function describe(draft: SpecDraft, field: Field): string | null {
  switch (field) {
    case 'objects':
      if (!draft.objects) return null
      if (draft.objects.length === 0) return 'none'
      return draft.objects.map((o) => `${plain(o.kind)} ×${o.count}`).join(', ')
    case 'rules':
      if (!draft.rules) return null
      if (draft.rules.length === 0) return 'none'
      return draft.rules.map(describeRule).join('; ')
    default: {
      const value = draft[field]
      return value == null ? null : String(value)
    }
  }
}

const isSet = (draft: SpecDraft, field: Field) => draft[field] != null

/** The spec panel's rows. The field Claude is asking about is `asking`, even if already set. */
export function specRows(draft: SpecDraft, question: Question | null): Row[] {
  return ROWS.map(({ label, fields }) => {
    const value =
      label === 'Size'
        ? draft.width == null && draft.height == null
          ? null
          : `${draft.width ?? '?'} × ${draft.height ?? '?'}`
        : describe(draft, fields[0])
    const status: Status =
      question && fields.includes(question.field)
        ? 'asking'
        : fields.every((f) => isSet(draft, f))
          ? 'ready'
          : 'next'
    return { label, value: value ?? '—', status }
  })
}

/**
 * A short, plain-English summary of what is decided so far, or null if nothing is. Theme and
 * mood are free text Claude may write as phrases, so each stands as its own sentence.
 */
export function summary(draft: SpecDraft): string | null {
  const sentences: string[] = []
  if (draft.theme) sentences.push(draft.theme)
  if (draft.mood) sentences.push(`Mood: ${draft.mood}`)
  const layout: string[] = []
  if (draft.width != null && draft.height != null)
    layout.push(`${draft.width}×${draft.height} tiles`)
  if (draft.doors != null)
    layout.push(`${draft.doors} ${draft.doors === 1 ? 'door' : 'doors'}`)
  if (layout.length) sentences.push(layout.join(', '))
  if (sentences.length === 0) return null
  return sentences
    .map((t) => `${t[0].toUpperCase()}${t.slice(1).replace(/[.!]$/, '')}.`)
    .join(' ')
}

/**
 * The history to send. Over the cap, drops the oldest question and answer after the first
 * idea, as the backend asks, so the idea is never lost.
 */
export function trimHistory(messages: ChatMessage[]): ChatMessage[] {
  const kept = [...messages]
  while (kept.length > MAX_MESSAGES) kept.splice(1, 2)
  return kept
}
