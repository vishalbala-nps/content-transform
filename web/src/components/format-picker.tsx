import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"
import type { FormatInfo } from "@/lib/types"

// One tile per registered format: its label and what it makes, both from
// GET /api/formats, so a new format needs no edit here.

export function FormatPicker({
  formats,
  selected,
  onChange,
}: {
  formats: FormatInfo[]
  selected: Set<string>
  onChange: (selected: Set<string>) => void
}) {
  function toggle(name: string, on: boolean) {
    const next = new Set(selected)
    if (on) next.add(name)
    else next.delete(name)
    onChange(next)
  }

  const all = formats.length > 0 && selected.size === formats.length
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="tabular-nums">
          {selected.size} of {formats.length} selected
        </span>
        <Button
          variant="link"
          size="xs"
          className="h-auto p-0 text-xs"
          onClick={() =>
            onChange(all ? new Set() : new Set(formats.map((f) => f.name)))
          }
        >
          {all ? "Clear all" : "Select all"}
        </Button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {formats.map((f) => {
          const on = selected.has(f.name)
          return (
            <label
              key={f.name}
              htmlFor={`format-${f.name}`}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50",
                on && "border-foreground/30 bg-muted/40"
              )}
            >
              <Checkbox
                id={`format-${f.name}`}
                checked={on}
                onCheckedChange={(v) => toggle(f.name, v === true)}
                className="mt-0.5"
              />
              <span className="space-y-0.5">
                <span className="block text-sm font-medium">{f.label}</span>
                <span className="block text-xs text-muted-foreground">
                  {f.description}
                </span>
              </span>
            </label>
          )
        })}
      </div>
    </div>
  )
}
