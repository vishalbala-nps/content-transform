import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { JobSettings } from "@/lib/types"

// The choices a job applies to every format it generates. Values mirror
// GenerationConfig in app/formats/base.py; the labels are only for the UI.

type Choice = "audience" | "tone" | "detail_level" | "objective"

const CHOICES: { key: Choice; label: string; options: [string, string][] }[] = [
  {
    key: "audience",
    label: "Audience",
    options: [
      ["general_public", "General public"],
      ["executive", "Executives"],
      ["technical", "Technical"],
      ["media", "Media"],
    ],
  },
  {
    key: "objective",
    label: "Objective",
    options: [
      ["inform", "Inform"],
      ["warn", "Warn"],
      ["persuade", "Persuade"],
      ["instruct", "Instruct"],
      ["announce", "Announce"],
    ],
  },
  {
    key: "tone",
    label: "Tone",
    options: [
      ["neutral", "Neutral"],
      ["formal", "Formal"],
      ["conversational", "Conversational"],
      ["urgent", "Urgent"],
    ],
  },
  {
    key: "detail_level",
    label: "Detail",
    options: [
      ["brief", "Brief"],
      ["standard", "Standard"],
      ["detailed", "Detailed"],
    ],
  },
]

export function JobSettingsFields({
  value,
  onChange,
}: {
  value: JobSettings
  onChange: (settings: JobSettings) => void
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Settings</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-3">
        {CHOICES.map((c) => (
          <div key={c.key} className="space-y-1">
            <Label
              htmlFor={`setting-${c.key}`}
              className="text-xs font-normal text-muted-foreground"
            >
              {c.label}
            </Label>
            <Select
              value={value[c.key]}
              onValueChange={(v) => onChange({ ...value, [c.key]: v })}
            >
              <SelectTrigger id={`setting-${c.key}`} className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {c.options.map(([v, label]) => (
                  <SelectItem key={v} value={v}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
        <div className="min-w-64 flex-1 space-y-1">
          <Label
            htmlFor="setting-style"
            className="text-xs font-normal text-muted-foreground"
          >
            Style (optional)
          </Label>
          <Input
            id="setting-style"
            value={value.style ?? ""}
            maxLength={300}
            onChange={(e) => onChange({ ...value, style: e.target.value })}
            placeholder="e.g. British spelling, avoid jargon"
          />
        </div>
      </div>
    </fieldset>
  )
}
