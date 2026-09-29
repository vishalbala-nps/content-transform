import { useState } from "react"
import { Plus } from "lucide-react"

import { BrandKitDialog } from "@/components/brand-kit-dialog"
import { Button } from "@/components/ui/button"
import { upsertKit } from "@/lib/kits"
import type { BrandKit } from "@/lib/types"

// Saved brand kits. Add opens the editor for a new kit; a row opens it for
// that kit.

// null: closed. { kit: null }: a new kit.
type Editing = { kit: BrandKit | null } | null

export function BrandKitsView({
  kits,
  onKitsChange,
}: {
  kits: BrandKit[]
  onKitsChange: (update: (kits: BrandKit[]) => BrandKit[]) => void
}) {
  const [editing, setEditing] = useState<Editing>(null)

  return (
    <div className="mx-auto max-w-5xl space-y-6">
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
        <p className="text-sm text-muted-foreground">
          No brand kits yet. Without one, files use the house style.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border text-sm">
          {kits.map((k) => (
            <li key={k.kit_id}>
              <button
                type="button"
                onClick={() => setEditing({ kit: k })}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-muted/60"
              >
                <span className="flex" aria-hidden>
                  <span
                    className="size-4 rounded-full ring-2 ring-background"
                    style={{ background: k.primary }}
                  />
                  <span
                    className="-ml-1 size-4 rounded-full ring-2 ring-background"
                    style={{ background: k.ink }}
                  />
                </span>
                <span className="font-medium">{k.org_name}</span>
                <span className="text-xs text-muted-foreground">
                  {[
                    k.font,
                    k.banned_phrases.length > 0 &&
                      `${k.banned_phrases.length} banned phrase${k.banned_phrases.length === 1 ? "" : "s"}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <BrandKitDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        kit={editing?.kit ?? null}
        onSaved={(kit) => onKitsChange((list) => upsertKit(list, kit))}
        onDeleted={(id) =>
          onKitsChange((list) => list.filter((k) => k.kit_id !== id))
        }
      />
    </div>
  )
}
