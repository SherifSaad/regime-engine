import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-sm">
        <h1 className="text-2xl font-bold tracking-tight">Log in</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Sign in to your account. (Placeholder — no auth yet.)
        </p>
        <div className="mt-8">
          <Button asChild className="w-full">
            <Link href="/app">Continue</Link>
          </Button>
          <p className="mt-4 text-center text-sm text-zinc-500">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-medium text-zinc-900 hover:underline">
              Sign up
            </Link>
          </p>
        </div>
    </div>
  )
}
