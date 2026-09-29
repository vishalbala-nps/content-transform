// Times as the UI shows them: "5 minutes ago" for recent ones, a date for
// older ones, and the full date and time on hover.

const TIME = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })

export function fullTime(iso: string): string {
  return TIME.format(new Date(iso))
}

export function ago(iso: string, now: number): string {
  const seconds = (new Date(iso).getTime() - now) / 1000
  const minutes = seconds / 60
  if (minutes > -1) return "just now"
  if (minutes > -60) return RELATIVE.format(Math.round(minutes), "minute")
  const hours = minutes / 60
  if (hours > -24) return RELATIVE.format(Math.round(hours), "hour")
  const days = hours / 24
  if (days > -7) return RELATIVE.format(Math.round(days), "day")
  return fullTime(iso)
}
