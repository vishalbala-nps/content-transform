import { useEffect, useState, type FormEvent, type ReactNode } from "react"
import { LoaderCircle } from "lucide-react"

import { SpectraMark } from "@/components/app-header"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getMe, signIn, SIGNED_OUT_EVENT, type Me } from "@/lib/api"

// Nothing but the sign-in page until someone is signed in. The app is then
// mounted for that user, and unmounted when the session ends (signed out,
// expired, or the account disabled), so nothing of one user's is left on
// screen for the next. The URL is kept: after signing in again, the same
// page opens.

function SignInPage({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onSignedIn(await signIn(email, password))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-3">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <SpectraMark className="size-6" />
            Spectra
          </div>
          <div className="space-y-1">
            <CardTitle>Sign in</CardTitle>
            <CardDescription>
              Accounts are created by your administrator.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy && <LoaderCircle className="animate-spin" />}
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}

export function AuthGate({
  children,
}: {
  children: (me: Me, onSignedOut: () => void) => ReactNode
}) {
  // undefined: not known yet; null: signed out.
  const [me, setMe] = useState<Me | null | undefined>(undefined)

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setMe(null))
    const onSignedOut = () => setMe(null)
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut)
  }, [])

  if (me === undefined) {
    return (
      <main className="flex min-h-svh items-center justify-center">
        <LoaderCircle
          className="size-5 animate-spin text-muted-foreground"
          aria-label="Loading"
        />
      </main>
    )
  }
  if (me === null) return <SignInPage onSignedIn={setMe} />
  return children(me, () => setMe(null))
}
