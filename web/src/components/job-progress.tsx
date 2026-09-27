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

// One row of steps: the brief, then each format. Pure view of the job's steps.
export function JobProgress({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
      {steps.map((step) => {
        const Icon = ICONS[step.status]
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
            <Icon
              className={cn(
                "size-4",
                step.status === "running" && "animate-spin",
                step.status === "done" &&
                  "text-emerald-600 dark:text-emerald-400"
              )}
              aria-hidden
            />
            {step.label}
            <span className="sr-only">: {step.status}</span>
          </li>
        )
      })}
    </ol>
  )
}
