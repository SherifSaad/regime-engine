export function RegimeTimelineVisual() {
  return (
    <div className="relative h-[280px] w-full min-w-[320px] overflow-hidden rounded-xl border border-zinc-200 bg-gradient-to-b from-zinc-50 to-white p-4 sm:h-[320px]">
      <svg
        viewBox="0 0 400 280"
        className="h-full w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Baseline */}
        <line
          x1="40"
          y1="140"
          x2="360"
          y2="140"
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="4 4"
          className="text-zinc-300"
        />
        {/* Regime segments - abstract "stability" vs "instability" */}
        <path
          d="M 40 140 L 100 140 L 120 100 L 160 100 L 180 140 L 220 140 L 240 180 L 280 180 L 300 120 L 360 120"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-zinc-700"
        />
        {/* Escalation bands (shaded areas) */}
        <path
          d="M 120 100 L 160 100 L 180 140 L 140 140 Z"
          fill="currentColor"
          fillOpacity="0.08"
          className="text-amber-600"
        />
        <path
          d="M 240 180 L 280 180 L 300 120 L 260 140 Z"
          fill="currentColor"
          fillOpacity="0.08"
          className="text-amber-600"
        />
        {/* Labels */}
        <text x="200" y="260" className="fill-zinc-400 text-[10px]" textAnchor="middle">
          Regime timeline (illustrative)
        </text>
      </svg>
    </div>
  )
}
