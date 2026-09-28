import { useRef, useState } from "react"
import { ImageUp, LoaderCircle, Plus, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  brandKitLogoUrl,
  deleteBrandKit,
  removeBrandKitLogo,
  saveBrandKit,
  uploadBrandKitLogo,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import type { BrandKit } from "@/lib/types"

// Create, edit and delete saved brand kits. The server checks every field
// (colours readable on white, a font name safe for CSS, a real PNG or JPEG
// logo) and its message is shown as is. A job keeps a copy of the kit it was
// made with, so nothing here changes an existing job.

interface Draft {
  org_name: string
  primary: string
  ink: string
  font: string
  banned: string // one phrase per line
}

const NEW_DRAFT: Draft = {
  org_name: "",
  primary: "#0b5cad",
  ink: "#1a1f2b",
  font: "",
  banned: "",
}

function draftOf(kit: BrandKit): Draft {
  return {
    org_name: kit.org_name,
    primary: kit.primary,
    ink: kit.ink,
    font: kit.font ?? "",
    banned: kit.banned_phrases.join("\n"),
  }
}

function ColourField({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={/^#[0-9a-f]{6}$/i.test(value) ? value : "#000000"}
          onChange={(e) => onChange(e.target.value)}
          aria-label={`${label}: pick`}
          className="h-8 w-10 cursor-pointer rounded border bg-transparent"
        />
        <Input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value.trim())}
          className="w-28 font-mono"
          maxLength={7}
        />
      </div>
    </div>
  )
}

export function BrandKitManager({
  kits,
  onChange,
}: {
  kits: BrandKit[]
  onChange: (kits: BrandKit[], chosen?: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<string | null>(null) // kit id; null: a new kit
  const [draft, setDraft] = useState<Draft>(NEW_DRAFT)
  const [logo, setLogo] = useState<File | null>(null) // chosen, not yet uploaded
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const current = kits.find((k) => k.kit_id === editing) ?? null
  const logoUrl = current && brandKitLogoUrl(current)

  function edit(kit: BrandKit | null) {
    setEditing(kit?.kit_id ?? null)
    setDraft(kit ? draftOf(kit) : NEW_DRAFT)
    setLogo(null)
    setError(null)
    setConfirmDelete(false)
  }

  // `list` is passed in, not read from props: within one save the props
  // still hold the list from before it.
  function replace(list: BrandKit[], kit: BrandKit): BrandKit[] {
    return list.some((k) => k.kit_id === kit.kit_id)
      ? list.map((k) => (k.kit_id === kit.kit_id ? kit : k))
      : [...list, kit]
  }

  async function act(call: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await call()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const save = () =>
    act(async () => {
      let kit = await saveBrandKit(editing, {
        org_name: draft.org_name,
        primary: draft.primary,
        ink: draft.ink,
        font: draft.font.trim() || null,
        banned_phrases: draft.banned.split("\n"),
      })
      const isNew = editing === null
      // The kit is saved first, so a refused logo never loses its fields.
      setEditing(kit.kit_id)
      let list = replace(kits, kit)
      onChange(list, isNew ? kit.kit_id : undefined)
      if (logo) {
        kit = await uploadBrandKitLogo(kit.kit_id, logo)
        setLogo(null)
        list = replace(list, kit)
        onChange(list)
      }
      setDraft(draftOf(kit))
    })

  const removeLogo = () =>
    act(async () => {
      if (!current) return
      onChange(replace(kits, await removeBrandKitLogo(current.kit_id)))
    })

  const remove = () =>
    act(async () => {
      if (!current) return
      await deleteBrandKit(current.kit_id)
      onChange(kits.filter((k) => k.kit_id !== current.kit_id))
      edit(null)
    })

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o) edit(kits[0] ?? null)
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Manage…
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Brand kits</DialogTitle>
          <DialogDescription>
            Used by the PDFs and the slide deck: your organisation's name,
            colours, font and logo. Banned phrases are kept out of every format.
            Jobs already made keep the kit as it was.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-2">
          {kits.map((k) => (
            <Button
              key={k.kit_id}
              variant={k.kit_id === editing ? "secondary" : "ghost"}
              size="sm"
              onClick={() => edit(k)}
            >
              <span
                className="size-3 rounded-full"
                style={{ background: k.primary }}
                aria-hidden
              />
              {k.org_name}
            </Button>
          ))}
          <Button
            variant={editing === null ? "secondary" : "ghost"}
            size="sm"
            onClick={() => edit(null)}
          >
            <Plus />
            New kit
          </Button>
        </div>

        <div className="space-y-4 border-t pt-4">
          <div className="space-y-1">
            <Label htmlFor="kit-name">Organisation name</Label>
            <Input
              id="kit-name"
              value={draft.org_name}
              maxLength={80}
              onChange={(e) => setDraft({ ...draft, org_name: e.target.value })}
              placeholder="Shown in PDF headers and on the title slide"
            />
          </div>
          <div className="flex flex-wrap gap-6">
            <ColourField
              id="kit-primary"
              label="Main colour"
              value={draft.primary}
              onChange={(v) => setDraft({ ...draft, primary: v })}
            />
            <ColourField
              id="kit-ink"
              label="Text colour"
              value={draft.ink}
              onChange={(v) => setDraft({ ...draft, ink: v })}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="kit-font">Font (optional)</Label>
            <Input
              id="kit-font"
              value={draft.font}
              maxLength={60}
              onChange={(e) => setDraft({ ...draft, font: e.target.value })}
              placeholder="e.g. Georgia"
            />
            <p className="text-xs text-muted-foreground">
              PDFs need it installed on the server, decks on the computer that
              opens them; otherwise a standard sans-serif is used.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="kit-banned">Banned phrases (one per line)</Label>
            <Textarea
              id="kit-banned"
              value={draft.banned}
              onChange={(e) => setDraft({ ...draft, banned: e.target.value })}
              placeholder={"game-changer\nworld-class"}
              className="min-h-20"
            />
          </div>

          <div className="space-y-2">
            <Label>Logo (PNG or JPEG, up to 1 MB)</Label>
            <div className="flex flex-wrap items-center gap-3">
              {logo ? (
                <span className="text-sm">
                  {logo.name} (saved with the kit)
                </span>
              ) : logoUrl ? (
                <img
                  src={logoUrl}
                  alt={`${current?.org_name} logo`}
                  className="max-h-12 max-w-40 rounded border bg-white p-1"
                />
              ) : (
                <span className="text-sm text-muted-foreground">No logo</span>
              )}
              <input
                ref={fileInput}
                type="file"
                accept="image/png,image/jpeg"
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(e) => {
                  setLogo(e.target.files?.[0] ?? null)
                  e.target.value = ""
                }}
              />
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                <ImageUp />
                {logoUrl || logo ? "Replace" : "Choose"}
              </Button>
              {logo && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => setLogo(null)}
                >
                  <X />
                  Don't use
                </Button>
              )}
              {!logo && logoUrl && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={removeLogo}
                >
                  <X />
                  Remove
                </Button>
              )}
            </div>
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <div
            className={cn(
              "flex flex-wrap items-center gap-2",
              current && "justify-between"
            )}
          >
            <Button disabled={busy || !draft.org_name.trim()} onClick={save}>
              {busy && <LoaderCircle className="animate-spin" />}
              {editing ? "Save changes" : "Create kit"}
            </Button>
            {current &&
              (confirmDelete ? (
                <span className="flex flex-wrap items-center gap-2 text-sm">
                  Delete {current.org_name}? Jobs made with it keep their copy.
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={busy}
                    onClick={remove}
                  >
                    Delete
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmDelete(false)}
                  >
                    Cancel
                  </Button>
                </span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 />
                  Delete kit
                </Button>
              ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
