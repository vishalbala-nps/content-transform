import { useState, type FormEvent } from "react"
import { KeyRound, LoaderCircle, LogOut } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { changePassword, type Me } from "@/lib/api"

// Who is signed in, in the title bar: change password, sign out.

function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [again, setAgain] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [changed, setChanged] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (next !== again) {
      setError("The new passwords do not match.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await changePassword(current, next)
      setChanged(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (changed) {
    return (
      <>
        <DialogHeader>
          <DialogTitle>Password changed</DialogTitle>
          <DialogDescription>
            You stay signed in here. Anywhere else you were signed in, you will
            need to sign in again.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={onDone}>Done</Button>
        </DialogFooter>
      </>
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>Change password</DialogTitle>
        <DialogDescription>
          Signs you out everywhere else. At least 12 characters is best.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-1">
        <Label htmlFor="pw-current">Current password</Label>
        <Input
          id="pw-current"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          autoFocus
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="pw-new">New password</Label>
        <Input
          id="pw-new"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="pw-again">New password again</Label>
        <Input
          id="pw-again"
          type="password"
          autoComplete="new-password"
          value={again}
          onChange={(e) => setAgain(e.target.value)}
          required
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <DialogFooter>
        <Button type="submit" disabled={busy}>
          {busy && <LoaderCircle className="animate-spin" />}
          Change password
        </Button>
      </DialogFooter>
    </form>
  )
}

export function UserMenu({ me, onSignOut }: { me: Me; onSignOut: () => void }) {
  const [changing, setChanging] = useState(false)

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Account: ${me.email}`}
            title={me.email}
            className="rounded-full"
          >
            <span className="flex size-6 items-center justify-center rounded-full bg-foreground text-xs font-semibold text-background uppercase">
              {me.email[0]}
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-52">
          <DropdownMenuLabel className="font-normal">
            <span className="block text-xs text-muted-foreground">
              Signed in as
            </span>
            <span className="block truncate font-medium">{me.email}</span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setChanging(true)}>
            <KeyRound />
            Change password…
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onSignOut}>
            <LogOut />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={changing} onOpenChange={setChanging}>
        <DialogContent className="sm:max-w-sm">
          {/* Mounted only while open, so it starts empty each time. */}
          <ChangePasswordForm onDone={() => setChanging(false)} />
        </DialogContent>
      </Dialog>
    </>
  )
}
