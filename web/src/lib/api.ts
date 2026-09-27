import type { FormatInfo, GenerateResponse } from "@/lib/types"

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail)
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return body as T
}

export function listFormats(): Promise<FormatInfo[]> {
  return request("/api/formats")
}

export function generate(
  text: string,
  formats: string[]
): Promise<GenerateResponse> {
  return request("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, formats }),
  })
}
