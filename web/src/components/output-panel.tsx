import { useState } from "react"
import { Check, Copy, Download } from "lucide-react"

import { PassageList } from "@/components/passage-list"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { artifactUrl } from "@/lib/api"
import { isFlagged } from "@/lib/grounding"
import { LANGUAGES } from "@/lib/settings"
import { cn } from "@/lib/utils"
import type {
  Artifact,
  ContentBrief,
  FormatResult,
  Grounding,
  Language,
} from "@/lib/types"

// One card per generated format. Knows nothing about any particular format:
// everything it shows comes from the Artifact fields, the adapter's warnings
// and the grounding report, whose passages are found from the payload.

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

// Text artifacts only; every artifact downloads from the header.
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

function GroundingSummary({ grounding }: { grounding: Grounding }) {
  const flagged = grounding.passages.filter(isFlagged)
  return (
    <p
      className={cn(
        "text-xs text-muted-foreground",
        (flagged.length > 0 || grounding.error) &&
          "text-amber-700 dark:text-amber-400"
      )}
    >
      {grounding.error ??
        `Grounding: ${flagged.length} of ${grounding.passages.length} passages need review`}
    </p>
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

function Body({
  jobId,
  result,
  brief,
  language,
  selectedPath,
  onSelect,
  onRevised,
}: {
  jobId: string
  result: FormatResult
  brief: ContentBrief
  language: Language
  selectedPath: string | null
  onSelect: (path: string | null) => void
  onRevised: (result: FormatResult) => void
}) {
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const text = result.artifacts
    .filter((a) => a.text !== null)
    .map((a) => <ArtifactBody key={a.filename} artifact={a} />)
  const grounding = result.grounding
  // Jobs from before grounding existed have only the text.
  if (!grounding) return text

  const flagged = grounding.passages.filter(isFlagged)
  // A passage just fixed or accepted stays in view while it is selected.
  const shown = flaggedOnly
    ? grounding.passages.filter((p) => isFlagged(p) || p.path === selectedPath)
    : grounding.passages
  // Review is always in English, the language the output was written and
  // checked in; the files and the Text tab are in the job's language.
  const translated = result.translation !== null && language !== "en"
  return (
    <Tabs defaultValue="review">
      <TabsList>
        <TabsTrigger value="review">
          {translated ? "Review (English)" : "Review"}
        </TabsTrigger>
        <TabsTrigger value="text">
          {translated ? `Text (${LANGUAGES[language].native})` : "Text"}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="review" className="space-y-2">
        {translated && (
          <p className="text-xs text-muted-foreground">
            Written and checked in English. Edits and regenerated passages are
            translated into {LANGUAGES[language].name} again; the files use the
            translation.
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <GroundingSummary grounding={grounding} />
          {flagged.length > 0 && (
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Checkbox
                checked={flaggedOnly}
                onCheckedChange={(on) => setFlaggedOnly(on === true)}
              />
              Flagged only
            </label>
          )}
        </div>
        <PassageList
          jobId={jobId}
          format={result.name}
          passages={shown}
          brief={brief}
          selectedPath={selectedPath}
          onSelect={onSelect}
          onRevised={onRevised}
        />
      </TabsContent>
      <TabsContent value="text" className="space-y-3">
        {text}
      </TabsContent>
    </Tabs>
  )
}

export function OutputPanel({
  jobId,
  result,
  brief,
  language,
  selectedPath,
  onSelect,
  onRevised,
}: {
  jobId: string
  result: FormatResult
  brief: ContentBrief
  language: Language
  selectedPath: string | null // the selected passage, if it is in this format
  onSelect: (path: string | null) => void
  onRevised: (result: FormatResult) => void // a passage was edited, accepted or regenerated
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
        {/* Everything to take away, before the long review list. */}
        {result.artifacts.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {artifact && <CopyButton text={artifact.text ?? ""} />}
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
          </div>
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
        <Body
          jobId={jobId}
          result={result}
          brief={brief}
          language={language}
          selectedPath={selectedPath}
          onSelect={onSelect}
          onRevised={onRevised}
        />
      </CardContent>
    </Card>
  )
}
