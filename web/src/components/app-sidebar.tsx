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
import { useNow } from "@/hooks/use-now"
import { ago, fullTime } from "@/lib/time"
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
                                title={fullTime(j.created_at)}
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
