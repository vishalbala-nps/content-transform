import { Moon, Sun } from "lucide-react"

import { NavLink } from "@/components/nav-link"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { UserMenu } from "@/components/user-menu"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { Me } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { View } from "@/lib/view"

// The title bar across the top of every view. The sidebar sits below it.

// One source in, a spread of outputs out: a small spectrum.
export function SpectraMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "size-5 shrink-0 rounded-md bg-[linear-gradient(135deg,#6366f1,#06b6d4_35%,#22c55e_60%,#f59e0b_80%,#ef4444)]",
        className
      )}
    />
  )
}

function isDark(theme: "dark" | "light" | "system"): boolean {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  }
  return theme === "dark"
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const dark = isDark(theme)
  const label = dark ? "Switch to light mode" : "Switch to dark mode"
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={label}
      title={label}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
}

export function AppHeader({
  me,
  onNavigate,
  onSignOut,
}: {
  me: Me
  onNavigate: (view: View) => void
  onSignOut: () => void
}) {
  return (
    <header className="sticky top-0 z-20 flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background px-3">
      <SidebarTrigger />
      <Separator
        orientation="vertical"
        className="mx-1 data-vertical:h-4 data-vertical:self-center"
      />
      <NavLink
        to={{ kind: "new" }}
        onNavigate={onNavigate}
        className="flex items-center gap-2 font-semibold"
      >
        <SpectraMark />
        Spectra
      </NavLink>
      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        <UserMenu me={me} onSignOut={onSignOut} />
      </div>
    </header>
  )
}
