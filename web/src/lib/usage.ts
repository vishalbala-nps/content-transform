import type { Job, Usage } from "@/lib/types"

const ZERO: Usage = {
  calls: 0,
  cached_calls: 0,
  input_tokens: 0,
  cached_input_tokens: 0,
  output_tokens: 0,
  cost_usd: 0,
  unpriced_calls: 0,
}

// The sum of the parts that exist; null if none do (a job from before usage
// was recorded).
export function sumUsage(parts: (Usage | null | undefined)[]): Usage | null {
  const known = parts.filter((p): p is Usage => p != null)
  if (known.length === 0) return null
  return known.reduce(
    (a, b) => ({
      calls: a.calls + b.calls,
      cached_calls: a.cached_calls + b.cached_calls,
      input_tokens: a.input_tokens + b.input_tokens,
      cached_input_tokens: a.cached_input_tokens + b.cached_input_tokens,
      output_tokens: a.output_tokens + b.output_tokens,
      cost_usd: a.cost_usd + b.cost_usd,
      unpriced_calls: a.unpriced_calls + b.unpriced_calls,
    }),
    ZERO
  )
}

// Summed here rather than on the server: a revised passage replaces one
// output in the page, and the total has to follow it.
export function jobUsage(job: Job): Usage | null {
  return sumUsage([
    job.brief_usage,
    ...job.outputs.flatMap((o) =>
      o.usage
        ? [o.usage.generate, o.usage.ground, o.usage.translate, o.usage.revise]
        : []
    ),
  ])
}

export function formatTokens(n: number): string {
  return n < 1000 ? String(n) : `${(n / 1000).toFixed(1)}k`
}

// Small amounts keep enough digits to be told apart.
export function formatCost(usd: number): string {
  if (usd === 0) return "$0"
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`
}
