import type { GenerationConfig, JobSettings, Language } from "@/lib/types"

// Mirrors the defaults of GenerationConfig in app/formats/base.py.
export const DEFAULT_SETTINGS: JobSettings = {
  audience: "general_public",
  tone: "neutral",
  detail_level: "standard",
  objective: "inform",
  language: "en",
  style: null,
  brand_kit_id: null,
}

// The fixed choices, with their UI labels, in the order the form shows them.
export type Choice = "audience" | "tone" | "detail_level" | "objective"

export const CHOICES: Record<
  Choice,
  { label: string; options: [string, string][] }
> = {
  audience: {
    label: "Audience",
    options: [
      ["general_public", "General public"],
      ["executive", "Executives"],
      ["technical", "Technical"],
      ["media", "Media"],
    ],
  },
  objective: {
    label: "Objective",
    options: [
      ["inform", "Inform"],
      ["warn", "Warn"],
      ["persuade", "Persuade"],
      ["instruct", "Instruct"],
      ["announce", "Announce"],
    ],
  },
  tone: {
    label: "Tone",
    options: [
      ["neutral", "Neutral"],
      ["formal", "Formal"],
      ["conversational", "Conversational"],
      ["urgent", "Urgent"],
    ],
  },
  detail_level: {
    label: "Detail",
    options: [
      ["brief", "Brief"],
      ["standard", "Standard"],
      ["detailed", "Detailed"],
    ],
  },
}

// Output languages: the English name, and the name in its own script.
export const LANGUAGES: Record<Language, { name: string; native: string }> = {
  en: { name: "English", native: "English" },
  hi: { name: "Hindi", native: "हिन्दी" },
  ta: { name: "Tamil", native: "தமிழ்" },
  ml: { name: "Malayalam", native: "മലയാളം" },
  kn: { name: "Kannada", native: "ಕನ್ನಡ" },
  te: { name: "Telugu", native: "తెలుగు" },
}

// An opened job fills the form with the settings it was made with.
export function settingsFromConfig(config: GenerationConfig): JobSettings {
  const { audience, tone, detail_level, objective, language, style } = config
  return {
    audience,
    tone,
    detail_level,
    objective,
    language,
    style,
    brand_kit_id: config.brand_kit?.kit_id ?? null,
  }
}

// The UI label of a chosen value: "executive" -> "Executives".
export function choiceLabel(choice: Choice, value: string): string {
  return CHOICES[choice].options.find(([v]) => v === value)?.[1] ?? value
}
