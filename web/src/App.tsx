import { useEffect, useState } from "react"
import { LoaderCircle } from "lucide-react"

import { BriefPanel } from "@/components/brief-panel"
import { OutputPanel } from "@/components/output-panel"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { generate, listFormats } from "@/lib/api"
import type { FormatInfo, GenerateResponse } from "@/lib/types"

export function App() {
  const [text, setText] = useState("")
  const [formats, setFormats] = useState<FormatInfo[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GenerateResponse | null>(null)

  useEffect(() => {
    listFormats()
      .then((list) => {
        setFormats(list)
        setSelected(new Set(list.map((f) => f.name)))
      })
      .catch((err) => setError(`Could not load formats: ${err.message}`))
  }, [])

  function toggle(name: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (on) next.add(name)
      else next.delete(name)
      return next
    })
  }

  async function run() {
    if (!text.trim()) {
      setError("Paste some text first.")
      return
    }
    if (selected.size === 0) {
      setError("Choose at least one format.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      // Keep the server's order, which is the order the formats are listed in.
      const names = formats.map((f) => f.name).filter((n) => selected.has(n))
      setResult(await generate(text, names))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const failed = result?.outputs.filter((o) => o.error).length ?? 0

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <h1 className="text-xl font-semibold">Content Transform</h1>

      <div className="space-y-2">
        <Label htmlFor="source">Source text</Label>
        <Textarea
          id="source"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste an article, report or advisory…"
          className="min-h-56"
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Formats</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {formats.map((f) => (
            <div key={f.name} className="flex items-center gap-2">
              <Checkbox
                id={`format-${f.name}`}
                checked={selected.has(f.name)}
                onCheckedChange={(on) => toggle(f.name, on === true)}
              />
              <Label htmlFor={`format-${f.name}`} className="font-normal">
                {f.label}
              </Label>
            </div>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={loading || selected.size === 0}>
          {loading && <LoaderCircle className="animate-spin" />}
          Generate
        </Button>
        <span role="status" className="text-sm text-muted-foreground">
          {loading
            ? `Analysing source, then writing ${selected.size} format${selected.size === 1 ? "" : "s"}…`
            : result && !error
              ? `${result.brief.claims.length} claims · ${result.outputs.length - failed} of ${result.outputs.length} formats generated`
              : null}
        </span>
        {error && (
          <span role="alert" className="text-sm text-destructive">
            {error}
          </span>
        )}
      </div>

      {result && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <BriefPanel brief={result.brief} source={result.source} />
          <div className="space-y-6">
            {result.outputs.map((o) => (
              <OutputPanel key={o.name} result={o} />
            ))}
          </div>
        </div>
      )}
    </main>
  )
}

export default App
