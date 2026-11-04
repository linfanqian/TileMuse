import type { MapSpec, Question, SpecDraft } from '../../api/client'
import { allSet, specRows, summary } from './fields'

type Props = {
  draft: SpecDraft
  // The open question, so its field shows as `asking`.
  question: Question | null
  // Set once every field is set and they fit together. Only then can a map be made.
  spec: MapSpec | null
  generating: boolean
  onGenerate: (spec: MapSpec) => void
}

export default function SpecPanel({
  draft,
  question,
  spec,
  generating,
  onGenerate,
}: Props) {
  const rows = specRows(draft, question)
  const ready = rows.filter((r) => r.status === 'ready').length
  const text = summary(draft)

  let hint = 'Available once every field is ready'
  if (spec && question) hint = 'Ready now, or keep answering to refine it'
  else if (spec) hint = 'The spec is ready'
  else if (allSet(draft)) hint = "Some fields don't fit together yet"

  return (
    <aside className="spec-panel" aria-label="Design spec">
      <h2>Design spec</h2>
      <p className="spec-summary">
        {text ?? 'A summary appears here as you answer.'}
      </p>
      <progress value={ready} max={rows.length} aria-label="Fields ready" />
      <p className="spec-progress">
        {ready} of {rows.length} fields ready
      </p>
      <table className="spec-fields">
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>{row.value}</td>
              <td>
                <span className={`status status-${row.status}`}>
                  {row.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <details className="spec-json">
        <summary>View JSON</summary>
        <pre>{JSON.stringify(spec ?? draft, null, 2)}</pre>
      </details>
      <div className="spec-generate">
        <button
          className="primary"
          disabled={!spec || generating}
          onClick={() => spec && onGenerate(spec)}
        >
          {generating ? 'Generating…' : 'Generate map'}
        </button>
        <p>{hint}</p>
      </div>
    </aside>
  )
}
