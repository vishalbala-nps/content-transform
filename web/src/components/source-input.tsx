import { useRef, useState, type KeyboardEvent } from "react"
import { FileText, FileUp, Link2, Type, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

// Where a job's source comes from: pasted text, an uploaded file or a link.
// Each tab keeps its own value; the job uses the tab that is showing.

export type SourceKind = "text" | "file" | "url"

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function DropZone({
  file,
  types,
  onFile,
}: {
  file: File | null
  types: string[] // accepted extensions, ".pdf"
  onFile: (file: File | null) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [refused, setRefused] = useState<string | null>(null)

  // The server checks the file too; this only answers sooner.
  function choose(f: File | undefined) {
    if (!f) return
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase()
    if (!types.includes(ext)) {
      setRefused(`${f.name} is not one of ${types.join(", ")}.`)
      return
    }
    setRefused(null)
    onFile(f)
  }

  return (
    <div className="space-y-2">
      <input
        ref={input}
        type="file"
        accept={types.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          choose(e.target.files?.[0])
          // Lets the same file be chosen again after removing it.
          e.target.value = ""
        }}
      />
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border p-3">
          <FileText className="size-8 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">
              {fileSize(file.size)}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => input.current?.click()}
          >
            Replace
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Remove file"
            onClick={() => onFile(null)}
          >
            <X />
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            choose(e.dataTransfer.files[0])
          }}
          className={cn(
            "flex min-h-48 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            dragging && "border-primary bg-muted/50"
          )}
        >
          <FileUp className="size-8 text-muted-foreground" />
          <span className="text-sm font-medium">
            Drop a file here, or click to choose one
          </span>
          <span className="text-xs text-muted-foreground">
            {types.join(", ")} · up to 20 MB
          </span>
        </button>
      )}
      {refused && (
        <p role="alert" className="text-sm text-destructive">
          {refused}
        </p>
      )}
    </div>
  )
}

export function SourceInput({
  kind,
  onKindChange,
  text,
  onTextChange,
  file,
  onFileChange,
  url,
  onUrlChange,
  fileTypes,
  onSubmit,
}: {
  kind: SourceKind
  onKindChange: (kind: SourceKind) => void
  text: string
  onTextChange: (text: string) => void
  file: File | null
  onFileChange: (file: File | null) => void
  url: string
  onUrlChange: (url: string) => void
  fileTypes: string[] // empty: uploading is unavailable
  onSubmit: () => void // ⌘/Ctrl+Enter
}) {
  function submitOnModEnter(e: KeyboardEvent) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      onSubmit()
    }
  }

  return (
    <Tabs
      value={kind}
      onValueChange={(v) => onKindChange(v as SourceKind)}
      className="gap-3"
    >
      <TabsList>
        <TabsTrigger value="text">
          <Type />
          Paste text
        </TabsTrigger>
        {fileTypes.length > 0 && (
          <TabsTrigger value="file">
            <FileUp />
            Upload file
          </TabsTrigger>
        )}
        <TabsTrigger value="url">
          <Link2 />
          Link
        </TabsTrigger>
      </TabsList>

      <TabsContent value="text" className="space-y-1">
        <Textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={submitOnModEnter}
          aria-label="Source text"
          placeholder="Paste an article, report, advisory or notice…"
          className="min-h-64"
        />
        <p className="text-right text-xs text-muted-foreground tabular-nums">
          {text.length.toLocaleString()} characters
        </p>
      </TabsContent>

      <TabsContent value="file">
        <DropZone file={file} types={fileTypes} onFile={onFileChange} />
      </TabsContent>

      <TabsContent value="url" className="space-y-2">
        <Input
          type="url"
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
          onKeyDown={submitOnModEnter}
          aria-label="Source link"
          placeholder="https://…"
        />
        <p className="text-xs text-muted-foreground">
          A web page, or a link straight to a PDF or Word document. Pages that
          only work with JavaScript cannot be read: paste their text, or save
          the page as a PDF and upload it.
        </p>
      </TabsContent>
    </Tabs>
  )
}
