import { useState, type ReactNode } from "react"
import { Plus } from "lucide-react"

import { BrandKitDialog } from "@/components/brand-kit-dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { upsertKit } from "@/lib/kits"
import { CHOICES, LANGUAGES, type Choice } from "@/lib/settings"
import type { BrandKit, JobSettings, Language } from "@/lib/types"

// The choices a job applies to every format it generates, in three groups:
// who reads it, what comes out, and how it looks. Values mirror
// GenerationConfig in app/formats/base.py; the labels are only for the UI.

// Radix Select items cannot have an empty value.
const NO_KIT = "none"
const NEW_KIT = "new"

function Group({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      {children}
    </div>
  )
}

function Field({
  id,
  label,
  children,
}: {
  id: string
  label: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs font-normal text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  )
}

function ChoiceField({
  choice,
  value,
  onChange,
}: {
  choice: Choice
  value: JobSettings
  onChange: (settings: JobSettings) => void
}) {
  const c = CHOICES[choice]
  return (
    <Field id={`setting-${choice}`} label={c.label}>
      <Select
        value={value[choice]}
        onValueChange={(v) => onChange({ ...value, [choice]: v })}
      >
        <SelectTrigger id={`setting-${choice}`} className="w-full">
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
    </Field>
  )
}

export function JobSettingsFields({
  value,
  onChange,
  kits,
  onKitsChange,
}: {
  value: JobSettings
  onChange: (settings: JobSettings) => void
  kits: BrandKit[]
  onKitsChange: (update: (kits: BrandKit[]) => BrandKit[]) => void
}) {
  // "New kit…" opens the kit editor here, so making a kit does not mean
  // leaving the form. The kit it makes is chosen for this job.
  const [creating, setCreating] = useState(false)

  return (
    <div className="grid gap-x-8 gap-y-6 md:grid-cols-3">
      <Group title="Reader" hint="Who reads it, and what it should do">
        <ChoiceField choice="audience" value={value} onChange={onChange} />
        <ChoiceField choice="objective" value={value} onChange={onChange} />
        <ChoiceField choice="tone" value={value} onChange={onChange} />
      </Group>

      <Group title="Output" hint="How much, and in which language">
        <ChoiceField choice="detail_level" value={value} onChange={onChange} />
        <Field id="setting-language" label="Language">
          <Select
            value={value.language}
            onValueChange={(v) =>
              onChange({ ...value, language: v as Language })
            }
          >
            <SelectTrigger id="setting-language" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(LANGUAGES).map(([code, l]) => (
                <SelectItem key={code} value={code}>
                  {code === "en" ? l.name : `${l.native} · ${l.name}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        {value.language !== "en" && (
          <p className="text-xs text-muted-foreground">
            Written and checked in English, then translated. You review the
            English; the files use the translation.
          </p>
        )}
      </Group>

      <Group title="Brand" hint="How the files look and sound">
        <Field id="setting-brand-kit" label="Brand kit">
          <Select
            value={value.brand_kit_id ?? NO_KIT}
            onValueChange={(v) => {
              if (v === NEW_KIT) setCreating(true)
              else onChange({ ...value, brand_kit_id: v === NO_KIT ? null : v })
            }}
          >
            <SelectTrigger id="setting-brand-kit" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_KIT}>None (house style)</SelectItem>
              {kits.map((k) => (
                <SelectItem key={k.kit_id} value={k.kit_id}>
                  <span
                    className="size-2.5 rounded-full"
                    style={{ background: k.primary }}
                    aria-hidden
                  />
                  {k.org_name}
                </SelectItem>
              ))}
              <SelectSeparator />
              <SelectItem value={NEW_KIT}>
                <Plus />
                New kit…
              </SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field id="setting-style" label="Style (optional)">
          <Input
            id="setting-style"
            value={value.style ?? ""}
            maxLength={300}
            onChange={(e) => onChange({ ...value, style: e.target.value })}
            placeholder="e.g. British spelling, avoid jargon"
          />
        </Field>
      </Group>

      <BrandKitDialog
        open={creating}
        onOpenChange={setCreating}
        kit={null}
        onSaved={(kit) => {
          onKitsChange((list) => upsertKit(list, kit))
          onChange({ ...value, brand_kit_id: kit.kit_id })
        }}
        onDeleted={(id) =>
          onKitsChange((list) => list.filter((k) => k.kit_id !== id))
        }
      />
    </div>
  )
}
