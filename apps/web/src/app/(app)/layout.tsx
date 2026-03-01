import { AppShell } from "@/components/dashboard/AppShell"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>
}
