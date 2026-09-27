import { useState } from "react"
import { LoaderCircle } from "lucide-react"

import { BriefPanel } from "@/components/brief-panel"
import { PostPanel } from "@/components/post-panel"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { generate } from "@/lib/api"
import type { GenerateResponse } from "@/lib/types"

export function App() {
  const [text, setText] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<GenerateResponse | null>(null)

  async function run() {
    if (!text.trim()) {
      setError("Paste some text first.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      setResult(await generate(text))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

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

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={loading}>
          {loading && <LoaderCircle className="animate-spin" />}
          Generate LinkedIn post
        </Button>
        <span role="status" className="text-sm text-muted-foreground">
          {loading
            ? "Analysing source, then writing post…"
            : result && !error
              ? `${result.brief.claims.length} claims · post ${result.post.length} characters`
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
          <PostPanel post={result.post} />
        </div>
      )}
    </main>
  )
}

export default App
