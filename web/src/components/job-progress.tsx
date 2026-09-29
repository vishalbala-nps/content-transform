import {
  CircleCheck,
  CircleDashed,
  CircleMinus,
  CircleX,
  LoaderCircle,
} from "lucide-react"

import { cn } from "@/lib/utils"
import type { Step } from "@/lib/types"

const ICONS: Record<Step["status"], typeof CircleCheck> = {
  pending: CircleDashed,
  running: LoaderCircle,
  done: CircleCheck,
  failed: CircleX,
  skipped: CircleMinus,
}

// A step's status as an icon: spinning while it runs, green when done.
export function StepIcon({
  status,
  className,
}: {
  status: Step["status"]
  className?: string
}) {
  const Icon = ICONS[status]
  return (
    <Icon
      className={cn(
        "size-4 shrink-0",
        status === "running" && "animate-spin",
        status === "done" && "text-emerald-600 dark:text-emerald-400",
        className
      )}
      aria-hidden
    />
  )
}

// The job's steps: the brief, then each format. Pure view of the job's steps.
export function JobProgress({
  steps,
  className,
}: {
  steps: Step[]
  className?: string
}) {
  return (
    <ol className={cn("flex flex-wrap gap-x-5 gap-y-1.5 text-sm", className)}>
      {steps.map((step) => {
        return (
          <li
            key={step.name}
            className={cn(
              "flex items-center gap-1.5",
              (step.status === "pending" || step.status === "skipped") &&
                "text-muted-foreground",
              step.status === "failed" && "text-destructive"
            )}
          >
            <StepIcon status={step.status} />
            {step.label}
            <span className="sr-only">: {step.status}</span>
          </li>
        )
      })}
    </ol>
  )
}
