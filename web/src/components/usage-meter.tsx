import type { Job, Usage } from "@/lib/types"
import { formatCost, formatTokens, jobUsage } from "@/lib/usage"

// What the job's model calls used and cost: one line, opening into a table
// by step (the brief, then each format's writing, checking and revisions).
// Costs are estimates from list prices at the time of each call.

function summary(u: Usage): string {
  const parts = [
    `${u.calls} model ${u.calls === 1 ? "call" : "calls"}`,
    `${formatTokens(u.input_tokens + u.output_tokens)} tokens`,
    `est. ${formatCost(u.cost_usd)}`,
  ]
  if (u.cached_calls) parts.push(`${u.cached_calls} from cache`)
  if (u.unpriced_calls) parts.push(`${u.unpriced_calls} with no known price`)
  return parts.join(" · ")
}

function Row({ label, usage }: { label: string; usage: Usage | null }) {
  const cell = "px-2 py-1 text-right tabular-nums"
  if (!usage) {
    return (
      <tr className="border-t">
        <td className="px-2 py-1">{label}</td>
        <td className={cell} colSpan={4}>
          not recorded
        </td>
      </tr>
    )
  }
  return (
    <tr className="border-t">
      <td className="px-2 py-1">{label}</td>
      <td className={cell}>
        {usage.calls}
        {usage.cached_calls > 0 && (
          <span className="text-muted-foreground">
            {" "}
            +{usage.cached_calls} cached
          </span>
        )}
      </td>
      <td className={cell}>{usage.input_tokens.toLocaleString()}</td>
      <td className={cell}>{usage.output_tokens.toLocaleString()}</td>
      <td className={cell}>{formatCost(usage.cost_usd)}</td>
    </tr>
  )
}

export function UsageMeter({ job }: { job: Job }) {
  const total = jobUsage(job)
  if (!total) return null // a job from before usage was recorded
  return (
    <details className="text-sm text-muted-foreground">
      <summary className="cursor-pointer select-none">
        Usage: {summary(total)}
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-md text-xs">
          <thead>
            <tr className="text-left">
              <th className="px-2 py-1 font-medium">Step</th>
              <th className="px-2 py-1 text-right font-medium">Calls</th>
              <th className="px-2 py-1 text-right font-medium">Input</th>
              <th className="px-2 py-1 text-right font-medium">Output</th>
              <th className="px-2 py-1 text-right font-medium">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            <Row label="Content brief" usage={job.brief_usage} />
            {job.outputs.map((o) => (
              <FormatRows key={o.name} label={o.label} usage={o.usage} />
            ))}
            <tr className="border-t font-medium text-foreground">
              <td className="px-2 py-1">Total</td>
              <td className="px-2 py-1 text-right tabular-nums">
                {total.calls}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {total.input_tokens.toLocaleString()}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {total.output_tokens.toLocaleString()}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {formatCost(total.cost_usd)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  )
}

function FormatRows({
  label,
  usage,
}: {
  label: string
  usage: Job["outputs"][number]["usage"]
}) {
  if (!usage) return <Row label={label} usage={null} />
  const revised = usage.revise.calls + usage.revise.cached_calls > 0
  return (
    <>
      <Row label={`${label}: writing`} usage={usage.generate} />
      <Row label={`${label}: checking`} usage={usage.ground} />
      {revised && <Row label={`${label}: revisions`} usage={usage.revise} />}
    </>
  )
}
