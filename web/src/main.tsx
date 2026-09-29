import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { AuthGate } from "@/components/auth-gate"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { TooltipProvider } from "@/components/ui/tooltip"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <TooltipProvider>
        <AuthGate>
          {(me, onSignedOut) => (
            <App key={me.email} me={me} onSignedOut={onSignedOut} />
          )}
        </AuthGate>
      </TooltipProvider>
    </ThemeProvider>
  </StrictMode>
)
