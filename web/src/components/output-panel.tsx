import { useState } from "react"
import { Check, Copy, Download } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { artifactUrl } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Artifact, FormatResult } from "@/lib/types"

// One card per generated format. Knows nothing about any particular format:
// everything it shows comes from the Artifact fields and the adapter's warnings.

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Button variant="outline" size="sm" onClick={copy}>
      {copied ? <Check /> : <Copy />}
      {copied ? "Copied" : "Copy"}
    </Button>
  )
}

// Text artifacts only; binary ones are offered in the footer.
function ArtifactBody({ artifact }: { artifact: Artifact }) {
  if (artifact.parts.length === 0) {
    return <div className="whitespace-pre-wrap">{artifact.text}</div>
  }
  const limit = artifact.part_limit
  return (
    <ol className="space-y-3">
      {artifact.parts.map((part, i) => (
        <li key={i} className="rounded-md border p-3">
          <div className="whitespace-pre-wrap">{part}</div>
          <div
            className={cn(
              "mt-1.5 text-right text-xs text-muted-foreground tabular-nums",
              limit != null && part.length > limit && "text-destructive"
            )}
          >
            {part.length}
            {limit != null && ` / ${limit}`}
          </div>
        </li>
      ))}
    </ol>
  )
}

function describe(artifact: Artifact): string {
  if (artifact.parts.length > 0) return `${artifact.parts.length} parts`
  return `${artifact.text?.length ?? 0} characters`
}

const FILE_KINDS: Record<string, string> = {
  "text/markdown": "Markdown",
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation":
    "PowerPoint",
}

function fileKind(artifact: Artifact): string {
  return (
    FILE_KINDS[artifact.media_type] ??
    artifact.filename.split(".").pop()?.toUpperCase() ??
    artifact.filename
  )
}

export function OutputPanel({
  jobId,
  result,
}: {
  jobId: string
  result: FormatResult
}) {
  // The text artifact, if any, is what Copy and the description use.
  const artifact = result.artifacts.find((a) => a.text !== null)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{result.label}</CardTitle>
        <CardDescription>
          {result.error ? "Failed" : artifact && describe(artifact)}
        </CardDescription>
        {artifact && (
          <CardAction>
            <CopyButton text={artifact.text ?? ""} />
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-relaxed">
        {result.error && (
          <p role="alert" className="text-destructive">
            {result.error}
          </p>
        )}
        {result.warnings.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-5 text-amber-700 dark:text-amber-400">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
        {result.artifacts
          .filter((a) => a.text !== null)
          .map((a) => (
            <ArtifactBody key={a.filename} artifact={a} />
          ))}
      </CardContent>
      {result.artifacts.length > 0 && (
        <CardFooter className="flex flex-wrap gap-2">
          {result.artifacts.map((a) => (
            <Button key={a.filename} variant="outline" size="sm" asChild>
              <a
                href={artifactUrl(jobId, result.name, a.filename)}
                download={a.filename}
                title={a.filename}
              >
                <Download />
                {fileKind(a)}
              </a>
            </Button>
          ))}
        </CardFooter>
      )}
    </Card>
  )
}
