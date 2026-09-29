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
