import type { Explanation, Violation } from '../../api/client'
import './ViolationList.css'

type Cell = { x: number; y: number }

type Props = {
  // One explanation per violation, in the same order, as the backend returns them.
  violations: Violation[]
  explanations: Explanation[]
  onShow: (cell: Cell) => void
}

// One card per issue: its rule, the explainer's text, and a way to find it on the map.
export default function ViolationList({
  violations,
  explanations,
  onShow,
}: Props) {
  return (
    <section className="issues" aria-labelledby="issues-title">
      <h2 id="issues-title">
        Issues{' '}
        <span className={`issue-count${explanations.length ? '' : ' none'}`}>
          {explanations.length}
        </span>
      </h2>
      {explanations.length === 0 ? (
        <p className="no-issues">No issues found.</p>
      ) : (
        <ul>
          {explanations.map((e, i) => {
            const v = violations[i]
            const hard = v?.blocking
            return (
              <li key={i} className={`issue ${hard ? 'hard' : 'spec'}`}>
                <h3>{e.code.replaceAll('_', ' ')}</h3>
                <p className="issue-kind">{hard ? 'Hard rule' : 'Spec rule'}</p>
                <p>{e.text}</p>
                {v?.x != null && v.y != null && (
                  <button
                    type="button"
                    className="link"
                    onClick={() => onShow({ x: v.x!, y: v.y! })}
                  >
                    Show on map
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
