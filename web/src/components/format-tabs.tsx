import { TriangleAlert } from "lucide-react"
import { Tabs as TabsPrimitive } from "radix-ui"

import { StepIcon } from "@/components/job-progress"
import { isFlagged } from "@/lib/grounding"
import { cn } from "@/lib/utils"
import type { FormatResult, Step } from "@/lib/types"

// The job's formats as a row of pills, one shown at a time. Each pill
// carries what used to be visible on every card at once: its progress, how
// many passages need review, and whether it has warnings. Styled apart from
// the Review | Text tabs inside a format, so the two rows never read as one.

export function FormatTabList({
  steps,
  outputs,
  className,
}: {
  steps: Step[] // the job's format steps, in registry order
  outputs: FormatResult[]
  className?: string
}) {
  return (
    <TabsPrimitive.List
      aria-label="Formats"
      className={cn("flex flex-wrap gap-2", className)}
    >
      {steps.map((step) => {
        const result = outputs.find((o) => o.name === step.name)
        const flagged =
          result?.grounding?.passages.filter(isFlagged).length ?? 0
        const warnings = result?.warnings.length ?? 0
        const notes = [
          step.status,
          flagged > 0 &&
            `${flagged} passage${flagged === 1 ? "" : "s"} to review`,
          warnings > 0 && `${warnings} warning${warnings === 1 ? "" : "s"}`,
        ].filter(Boolean)
        return (
          <TabsPrimitive.Trigger
            key={step.name}
            value={step.name}
            title={notes.join(" · ")}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-full border bg-background px-3 text-sm font-medium whitespace-nowrap transition-colors",
              "hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              "data-[state=active]:border-foreground data-[state=active]:bg-foreground data-[state=active]:text-background",
              (step.status === "pending" || step.status === "skipped") &&
                "text-muted-foreground"
            )}
          >
            <StepIcon
              status={step.status}
              className={cn(
                step.status === "failed" && "text-destructive",
                // Green on the dark active pill is hard to see.
                "[[data-state=active]_&]:text-current"
              )}
            />
            {step.label}
            {flagged > 0 && (
              <span className="rounded-full bg-amber-100 px-1.5 text-xs text-amber-900 tabular-nums dark:bg-amber-900 dark:text-amber-100">
                {flagged}
              </span>
            )}
            {warnings > 0 && (
              <TriangleAlert className="size-3.5 text-amber-600 dark:text-amber-400 [[data-state=active]_&]:text-amber-400 dark:[[data-state=active]_&]:text-amber-600" />
            )}
            <span className="sr-only">: {notes.join(", ")}</span>
          </TabsPrimitive.Trigger>
        )
      })}
    </TabsPrimitive.List>
  )
}
