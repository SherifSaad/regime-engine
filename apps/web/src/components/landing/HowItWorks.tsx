import Link from "next/link"

const STEPS = [
  { num: 1, title: "Compute 11 regime metrics" },
  { num: 2, title: "Transform to percentiles" },
  { num: 3, title: "Era-condition + confidence scaling" },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl">
          How it works
        </h2>

        <div className="mt-12 flex flex-col gap-8 sm:flex-row sm:justify-center sm:gap-12">
          {STEPS.map((step) => (
            <div key={step.num} className="flex flex-col items-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-zinc-900 text-lg font-bold text-zinc-900">
                {step.num}
              </div>
              <p className="mt-3 max-w-[180px] text-sm font-medium text-zinc-700">
                {step.title}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center">
          <Link
            href="/methodology"
            className="text-sm font-medium text-zinc-600 underline-offset-4 hover:text-zinc-900"
          >
            Learn more
          </Link>
        </p>
      </div>
    </section>
  )
}
