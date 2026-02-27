export function ValidationTeaser() {
  return (
    <section id="validation" className="border-t border-zinc-200 bg-zinc-50/30 py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl">
          Validated across structural eras.
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-center text-zinc-600">
          We test whether high escalation is followed by wider future movement (both directions).
        </p>

        <div className="mx-auto mt-12 max-w-md overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50">
                <th className="px-4 py-3 font-semibold text-zinc-900">Condition</th>
                <th className="px-4 py-3 font-semibold text-zinc-900">P(large 20-bar move)</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-zinc-100">
                <td className="px-4 py-3 text-zinc-700">High escalation</td>
                <td className="px-4 py-3 font-medium text-zinc-900">~42%</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-700">Low escalation</td>
                <td className="px-4 py-3 font-medium text-zinc-900">~18%</td>
              </tr>
            </tbody>
          </table>
          <p className="border-t border-zinc-100 px-4 py-3 text-xs text-zinc-500">
            Results vary by era; we condition by era to prevent drift.
          </p>
        </div>
      </div>
    </section>
  )
}
