import type { ComponentProps } from "react"

import { viewHref, type View } from "@/lib/view"

// A real link to a view, so it can be opened in a new tab or copied. A plain
// click switches the view in place instead of reloading the page.
export function NavLink({
  to,
  onNavigate,
  onClick,
  ...props
}: ComponentProps<"a"> & { to: View; onNavigate: (view: View) => void }) {
  return (
    <a
      href={viewHref(to)}
      onClick={(e) => {
        onClick?.(e)
        if (
          e.defaultPrevented ||
          e.button !== 0 ||
          e.metaKey ||
          e.ctrlKey ||
          e.shiftKey ||
          e.altKey
        ) {
          return
        }
        e.preventDefault()
        onNavigate(to)
      }}
      {...props}
    />
  )
}
