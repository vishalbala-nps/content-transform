import type { BrandKit } from "@/lib/types"

// A saved kit into the list: replaced where it is, else added at the end.
export function upsertKit(list: BrandKit[], kit: BrandKit): BrandKit[] {
  return list.some((k) => k.kit_id === kit.kit_id)
    ? list.map((k) => (k.kit_id === kit.kit_id ? kit : k))
    : [...list, kit]
}
