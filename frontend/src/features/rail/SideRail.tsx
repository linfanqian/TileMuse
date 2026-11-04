import { useState, type ReactNode } from 'react'
import './SideRail.css'

type Tab = { name: string; content: ReactNode }

// A side panel with tabs. Only the open tab's content is shown.
export default function SideRail({
  label,
  tabs,
}: {
  label: string
  tabs: Tab[]
}) {
  const [open, setOpen] = useState(0)
  return (
    <aside className="side-rail" aria-label={label}>
      <div role="tablist" className="rail-tabs">
        {tabs.map((tab, i) => (
          <button
            key={tab.name}
            role="tab"
            id={`rail-tab-${i}`}
            aria-selected={i === open}
            aria-controls={`rail-panel-${i}`}
            onClick={() => setOpen(i)}
          >
            {tab.name}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`rail-panel-${open}`}
        aria-labelledby={`rail-tab-${open}`}
        className="rail-panel"
      >
        {tabs[open].content}
      </div>
    </aside>
  )
}
