import { useState } from "react"
import {
  EllipsisVertical,
  LoaderCircle,
  Palette,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react"

import { BrandKitDialog } from "@/components/brand-kit-dialog"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { brandKitLogoUrl, deleteBrandKit } from "@/lib/api"
import { upsertKit } from "@/lib/kits"
import type { BrandKit } from "@/lib/types"

// Saved brand kits. Add opens the editor for a new kit; a row opens it for
// that kit; a row's menu also deletes it, after a confirmation.

// null: closed. { kit: null }: a new kit.
type Editing = { kit: BrandKit | null } | null

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("")
}

// The logo on white, as the files show it; without one, the kit's initials
// on its main colour (saved kits are at least 3:1 against white).
function KitMark({ kit }: { kit: BrandKit }) {
  const logo = brandKitLogoUrl(kit)
  return logo ? (
    <img
      src={logo}
      alt=""
      className="size-12 shrink-0 rounded-md border bg-white object-contain p-1"
    />
  ) : (
    <span
      aria-hidden
      className="flex size-12 shrink-0 items-center justify-center rounded-md text-sm font-semibold text-white"
      style={{ background: kit.primary }}
    >
      {initials(kit.org_name)}
    </span>
  )
}

function Swatch({ label, colour }: { label: string; colour: string }) {
  return (
    <span className="flex items-center gap-1.5" title={label}>
      <span
        aria-hidden
        className="size-3.5 rounded-full ring-1 ring-foreground/15"
        style={{ background: colour }}
      />
      <span className="font-mono text-xs text-muted-foreground">
        <span className="sr-only">{label}: </span>
        {colour}
      </span>
    </span>
  )
}

function DeleteKitDialog({
  kit,
  onClose,
  onDeleted,
}: {
  kit: BrandKit | null
  onClose: () => void
  onDeleted: (kitId: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Stays open until the server answers, so a failure is shown here.
  async function remove() {
    if (!kit) return
    setBusy(true)
    setError(null)
    try {
      await deleteBrandKit(kit.kit_id)
      onDeleted(kit.kit_id)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AlertDialog
      open={kit !== null}
      onOpenChange={(open) => {
        if (!open && !busy) {
          setError(null)
          onClose()
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {kit?.org_name}?</AlertDialogTitle>
          <AlertDialogDescription>
            Jobs made with it keep their own copy, so their files do not change.
            This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <Button variant="destructive" disabled={busy} onClick={remove}>
            {busy ? <LoaderCircle className="animate-spin" /> : <Trash2 />}
            Delete
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function BrandKitsView({
  kits,
  onKitsChange,
}: {
  kits: BrandKit[]
  onKitsChange: (update: (kits: BrandKit[]) => BrandKit[]) => void
}) {
  const [editing, setEditing] = useState<Editing>(null)
  const [deleting, setDeleting] = useState<BrandKit | null>(null)

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Brand kits</h1>
          <p className="max-w-prose text-sm text-muted-foreground">
            Used by the PDFs and the slide deck: your organisation's name,
            colours, font and logo. Banned phrases are kept out of every format.
            Jobs already made keep the kit as it was.
          </p>
        </div>
        <Button onClick={() => setEditing({ kit: null })}>
          <Plus />
          Add
        </Button>
      </div>

      {kits.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-12 text-center">
          <Palette className="size-8 text-muted-foreground" />
          <p className="font-medium">No brand kits yet</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Without one, PDFs and decks use the Spectra house style.
          </p>
          <Button
            variant="outline"
            className="mt-2"
            onClick={() => setEditing({ kit: null })}
          >
            <Plus />
            Add a brand kit
          </Button>
        </div>
      ) : (
        <ul className="divide-y rounded-lg border">
          {kits.map((k) => {
            const banned = k.banned_phrases.length
            return (
              <li key={k.kit_id} className="flex items-center gap-2 pr-2">
                <button
                  type="button"
                  onClick={() => setEditing({ kit: k })}
                  className="flex min-w-0 flex-1 items-center gap-3 rounded-l-lg p-3 text-left hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <KitMark kit={k} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">
                      {k.org_name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {k.font ?? "Standard font"} ·{" "}
                      {banned === 0
                        ? "no banned phrases"
                        : `${banned} banned phrase${banned === 1 ? "" : "s"}`}
                    </span>
                  </span>
                  <span className="hidden shrink-0 gap-4 sm:flex">
                    <Swatch label="Main colour" colour={k.primary} />
                    <Swatch label="Text colour" colour={k.ink} />
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Actions for ${k.org_name}`}
                    >
                      <EllipsisVertical />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setEditing({ kit: k })}>
                      <Pencil />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={() => setDeleting(k)}
                    >
                      <Trash2 />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            )
          })}
        </ul>
      )}

      <BrandKitDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        kit={editing?.kit ?? null}
        onSaved={(kit) => onKitsChange((list) => upsertKit(list, kit))}
      />
      <DeleteKitDialog
        kit={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={(id) =>
          onKitsChange((list) => list.filter((k) => k.kit_id !== id))
        }
      />
    </div>
  )
}
