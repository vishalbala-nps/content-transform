import { useEffect, useState } from "react"
import {
  CircleCheck,
  CircleDashed,
  CircleX,
  LoaderCircle,
  Palette,
  Plus,
} from "lucide-react"

import { NavLink } from "@/components/nav-link"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { sameView, type View } from "@/lib/view"
import type { JobStatus, JobSummary } from "@/lib/types"

// New job, brand kits, then every recent job, newest first. On a phone the
// sidebar is a sheet, closed again once something in it is chosen.

const STATUS_ICONS: Record<JobStatus, typeof CircleCheck> = {
  queued: CircleDashed,
  running: LoaderCircle,
  done: CircleCheck,
  failed: CircleX,
}

const TIME = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })

function ago(iso: string, now: number): string {
  const seconds = (new Date(iso).getTime() - now) / 1000
  const minutes = seconds / 60
  if (minutes > -1) return "just now"
  if (minutes > -60) return RELATIVE.format(Math.round(minutes), "minute")
  const hours = minutes / 60
  if (hours > -24) return RELATIVE.format(Math.round(hours), "hour")
  const days = hours / 24
  if (days > -7) return RELATIVE.format(Math.round(days), "day")
  return TIME.format(new Date(iso))
}

// Re-renders every minute so "5 minutes ago" keeps up.
function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [])
  return now
}

function Item({
  to,
  icon: Icon,
  label,
  active,
  onNavigate,
}: {
  to: View
  icon: typeof Plus
  label: string
  active: boolean
  onNavigate: (view: View) => void
}) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={label}>
        <NavLink to={to} onNavigate={onNavigate}>
          <Icon />
          <span>{label}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar({
  view,
  jobs,
  onNavigate,
}: {
  view: View
  jobs: JobSummary[]
  onNavigate: (view: View) => void
}) {
  const { isMobile, setOpenMobile } = useSidebar()
  const now = useNow()

  function go(to: View) {
    if (isMobile) setOpenMobile(false)
    onNavigate(to)
  }

  return (
    <Sidebar
      collapsible="icon"
      className="top-(--header-height) h-[calc(100svh-var(--header-height))]!"
    >
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <Item
                to={{ kind: "new" }}
                icon={Plus}
                label="New job"
                active={view.kind === "new"}
                onNavigate={go}
              />
              <Item
                to={{ kind: "kits" }}
                icon={Palette}
                label="Brand kits"
                active={view.kind === "kits"}
                onNavigate={go}
              />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Titles do not fit in the icon rail, so the list hides there. */}
        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>Jobs</SidebarGroupLabel>
          <SidebarGroupContent>
            {jobs.length === 0 ? (
              <p className="px-2 text-xs text-muted-foreground">
                No jobs yet. Jobs you run are listed here.
              </p>
            ) : (
              <SidebarMenu>
                {jobs.map((j) => {
                  const to: View = { kind: "job", id: j.id }
                  const Icon = STATUS_ICONS[j.status]
                  return (
                    <SidebarMenuItem key={j.id}>
                      <SidebarMenuButton
                        asChild
                        size="lg"
                        isActive={sameView(view, to)}
                      >
                        <NavLink to={to} onNavigate={go} title={j.title}>
                          <Icon
                            aria-hidden
                            className={cn(
                              "mt-0.5 self-start",
                              j.status === "running" && "animate-spin",
                              j.status === "failed"
                                ? "text-destructive"
                                : "text-muted-foreground"
                            )}
                          />
                          <span className="flex min-w-0 flex-col">
                            <span className="truncate">{j.title}</span>
                            <span className="truncate text-xs text-muted-foreground">
                              <span className="sr-only">{j.status} · </span>
                              {j.formats.length} format
                              {j.formats.length === 1 ? "" : "s"} ·{" "}
                              <time
                                dateTime={j.created_at}
                                title={TIME.format(new Date(j.created_at))}
                              >
                                {ago(j.created_at, now)}
                              </time>
                            </span>
                          </span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
