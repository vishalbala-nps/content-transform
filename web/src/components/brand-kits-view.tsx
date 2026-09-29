import { BrandKitManager } from "@/components/brand-kit-manager"
import type { BrandKit } from "@/lib/types"

// Saved brand kits. For now the list is read-only and every change goes
// through the existing dialog.

export function BrandKitsView({
  kits,
  onKitsChange,
}: {
  kits: BrandKit[]
  onKitsChange: (kits: BrandKit[]) => void
}) {
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
        <BrandKitManager kits={kits} onChange={(next) => onKitsChange(next)} />
      </div>

      {kits.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No brand kits yet. Without one, files use the house style.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border text-sm">
          {kits.map((k) => (
            <li key={k.kit_id} className="flex items-center gap-3 px-3 py-2.5">
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
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
