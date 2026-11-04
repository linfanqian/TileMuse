import type { MapSpec } from '../../api/client'
import { specRows, summary } from './fields'
import './Interview.css'

// The spec a map was made from, read-only. Same summary and rows as the interview's panel.
export default function SpecView({ spec }: { spec: MapSpec }) {
  return (
    <div className="spec-view">
      <p className="spec-summary">{summary(spec)}</p>
      <table className="spec-fields">
        <tbody>
          {specRows(spec, null).map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
