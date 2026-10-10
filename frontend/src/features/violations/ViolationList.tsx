import type { Explanation } from '../../api/client'

type Props = {
  explanations: Explanation[]
}

export default function ViolationList({ explanations }: Props) {
  if (explanations.length === 0) return <p>No issues found.</p>
  return (
    <ul>
      {explanations.map((e, i) => (
        <li key={i}>{e.text}</li>
      ))}
    </ul>
  )
}
