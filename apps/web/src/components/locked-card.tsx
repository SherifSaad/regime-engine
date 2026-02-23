import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function LockedCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children?: React.ReactNode
}) {
  return (
    <Card className="relative overflow-hidden">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {subtitle ? (
          <div className="text-sm text-zinc-500">{subtitle}</div>
        ) : null}
      </CardHeader>

      <CardContent>
        <div className="pointer-events-none select-none blur-[3px] opacity-70">
          {children}
        </div>
      </CardContent>

      {/* Overlay */}
      <div className="absolute inset-0 flex items-center justify-center bg-white/55 backdrop-blur-[2px]">
        <div className="text-center">
          <div className="text-sm font-semibold">Locked • Pro</div>
          <div className="mt-1 text-xs text-zinc-600">
            Unlock full regime probabilities, consensus, and history.
          </div>
          <div className="mt-4">
            <Button size="sm">Upgrade to Pro</Button>
          </div>
        </div>
      </div>
    </Card>
  )
}
