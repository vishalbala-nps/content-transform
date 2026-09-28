import { useState, type ReactNode } from "react"
import { Check, LoaderCircle, Pencil, RefreshCw, Undo2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { acceptPassage, editPassage, regeneratePassage } from "@/lib/api"
import type { FormatResult, Passage } from "@/lib/types"

// What a reviewer can do with the selected passage. Each action saves on the
// server and returns the format's new result, files included.
// - Edit: the reviewer's text replaces the passage and is trusted, not checked.
// - Regenerate: the model rewrites just this passage (always a new call,
//   never the dev cache), and it is checked again.
// - Accept: the flag is reviewed and kept as is; it can be undone.

type Action = "edit" | "regenerate" | "accept" | "unaccept"

export function PassageActions({
  jobId,
  format,
  passage,
  onRevised,
}: {
  jobId: string
  format: string
  passage: Passage
  onRevised: (result: FormatResult) => void
}) {
  const [draft, setDraft] = useState<string | null>(null) // null: not editing
  const [busy, setBusy] = useState<Action | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(action: Action, call: () => Promise<FormatResult>) {
    setBusy(action)
    setError(null)
    try {
      onRevised(await call())
      setDraft(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  function icon(action: Action, idle: ReactNode) {
    return busy === action ? <LoaderCircle className="animate-spin" /> : idle
  }

  const path = passage.path
  const errorLine = error && (
    <p role="alert" className="text-destructive">
      {error}
    </p>
  )

  if (draft !== null) {
    const text = draft.trim()
    return (
      <div className="space-y-2">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="New text for this passage"
          className="min-h-24 text-sm text-foreground"
          autoFocus
        />
        <p>
          Your text replaces the passage in every file of this output. It is not
          checked against the brief.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={busy !== null || !text || text === passage.text}
            onClick={() =>
              run("edit", () => editPassage(jobId, format, path, text))
            }
          >
            {icon("edit", <Check />)}
            Save
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy !== null}
            onClick={() => {
              setDraft(null)
              setError(null)
            }}
          >
            Cancel
          </Button>
        </div>
        {errorLine}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() => setDraft(passage.text)}
        >
          <Pencil />
          Edit
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          title="Ask the model to rewrite this passage"
          onClick={() =>
            run("regenerate", () => regeneratePassage(jobId, format, path))
          }
        >
          {icon("regenerate", <RefreshCw />)}
          Regenerate
        </Button>
        {passage.review === "accepted" ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={busy !== null}
            onClick={() =>
              run("unaccept", () => acceptPassage(jobId, format, path, false))
            }
          >
            {icon("unaccept", <Undo2 />)}
            Undo accept
          </Button>
        ) : (
          passage.reasons.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={busy !== null}
              title="Keep the passage as it is; the flag is marked as reviewed"
              onClick={() =>
                run("accept", () => acceptPassage(jobId, format, path, true))
              }
            >
              {icon("accept", <Check />)}
              Accept
            </Button>
          )
        )}
      </div>
      {errorLine}
    </div>
  )
}
