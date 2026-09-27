import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// Block ids a brief item cites. Hover or focus a chip to see the source text.
// Empty support is what grounding (S7) will flag, so it is shown, not hidden.
export function SupportChips({
  ids,
  blocks,
}: {
  ids: string[]
  blocks: Map<string, string>
}) {
  if (ids.length === 0) {
    return (
      <Badge
        variant="outline"
        className="ml-1.5 border-dashed border-amber-600 text-amber-700 dark:text-amber-400"
      >
        unsupported
      </Badge>
    )
  }
  return ids.map((id) => (
    <Tooltip key={id}>
      <TooltipTrigger asChild>
        <Badge
          variant="secondary"
          tabIndex={0}
          className="ml-1.5 cursor-help font-mono"
        >
          {id}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-pre-wrap">
        {blocks.get(id)}
      </TooltipContent>
    </Tooltip>
  ))
}
