import type { GenerationConfig, JobSettings } from "@/lib/types"

// Mirrors the defaults of GenerationConfig in app/formats/base.py.
export const DEFAULT_SETTINGS: JobSettings = {
  audience: "general_public",
  tone: "neutral",
  detail_level: "standard",
  objective: "inform",
  style: null,
  brand_kit_id: null,
}

// An opened job fills the form with the settings it was made with.
export function settingsFromConfig(config: GenerationConfig): JobSettings {
  const { audience, tone, detail_level, objective, style } = config
  return {
    audience,
    tone,
    detail_level,
    objective,
    style,
    brand_kit_id: config.brand_kit?.kit_id ?? null,
  }
}
